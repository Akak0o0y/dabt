import { spawn, type ChildProcess } from "child_process";
import path from "path";
import { DABT_BUILD_INFO } from "./buildInfo";

export type DabtEvaluateInput = {
  document: string;
  agentId?: string;
  purpose?: string;
  lawfulBasis?: string;
  crossBorder?: boolean;
  sector?: string;
  eventType?: string;
  agentAuthorised?: boolean;
  requiresMinimisation?: boolean;
};

type DabtPayload = Record<string, unknown>;
type FetchLike = typeof fetch;

const DABT_PORT = Number(process.env.DABT_INTERNAL_PORT ?? "8743");
// The gate fails closed, so a service that cannot start takes every gated
// action down with it. Resolve the interpreter instead of assuming one name:
// Debian images expose python3, Windows and some slim images expose python.
const PYTHON_CANDIDATES = process.env.DABT_PYTHON
  ? [process.env.DABT_PYTHON]
  : ["python3", "python"];
const DABT_BASE_URL = `http://127.0.0.1:${DABT_PORT}`;
let apiProcess: ChildProcess | null = null;
let startupPromise: Promise<void> | null = null;

export class DabtApiError extends Error {
  payload: DabtPayload;

  constructor(message: string, payload: DabtPayload) {
    super(message);
    this.name = "DabtApiError";
    this.payload = payload;
  }
}

async function isReady(fetchImpl: FetchLike = fetch): Promise<boolean> {
  try {
    const response = await fetchImpl(`${DABT_BASE_URL}/v1/compliance-map`);
    return response.ok;
  } catch {
    return false;
  }
}

function startPolicyService(binary: string): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const pythonDir = path.resolve(process.cwd(), "dabt_python");
    const child = spawn(
      binary,
      ["-m", "uvicorn", "dabt_api.main:app", "--host", "127.0.0.1", "--port", String(DABT_PORT)],
      {
        cwd: pythonDir,
        env: { ...process.env, PYTHONPATH: pythonDir },
        stdio: "ignore",
      },
    );
    apiProcess = child;

    let settled = false;
    const settle = (fn: () => void) => {
      if (settled) return;
      settled = true;
      fn();
    };

    child.once("error", error => settle(() => reject(error)));
    child.once("exit", code => {
      if (code !== 0) settle(() => reject(new Error(`${binary} exited with code ${code}`)));
    });

    let attempts = 0;
    const probe = async () => {
      if (settled) return;
      if (await isReady()) {
        settle(resolve);
        return;
      }
      attempts += 1;
      if (attempts >= 40) {
        settle(() => reject(new Error(`${binary} did not become ready in time`)));
        return;
      }
      setTimeout(probe, 75);
    };
    void probe();
  });
}

async function ensureDabtService(): Promise<void> {
  if (await isReady()) return;
  if (startupPromise) return startupPromise;

  startupPromise = (async () => {
    let lastError: Error | null = null;
    for (const binary of PYTHON_CANDIDATES) {
      try {
        await startPolicyService(binary);
        return;
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
        if (apiProcess && !apiProcess.killed) apiProcess.kill("SIGTERM");
        apiProcess = null;
      }
    }
    startupPromise = null;
    throw new Error(
      `The Dabt Python service did not become ready (tried ${PYTHON_CANDIDATES.join(", ")}). ` +
        `Set DABT_PYTHON to the interpreter path. Last error: ${lastError?.message ?? "unknown"}`,
    );
  })();
  return startupPromise;
}

export async function callDabtApi<T extends DabtPayload = DabtPayload>(
  apiPath: string,
  method: "GET" | "POST",
  body?: DabtPayload,
  fetchImpl: FetchLike = fetch,
): Promise<T> {
  const response = await fetchImpl(`${DABT_BASE_URL}${apiPath}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = (await response.json()) as DabtPayload;
  if (!response.ok) {
    throw new DabtApiError(
      String(payload.detail_en ?? `Dabt API request failed with ${response.status}`),
      payload,
    );
  }
  return payload as T;
}

export async function evaluateDabt(input: DabtEvaluateInput): Promise<DabtPayload> {
  await ensureDabtService();
  return callDabtApi("/v1/retrieval/evaluate", "POST", {
    document: input.document,
    agent_id: input.agentId ?? "demo-agent",
    purpose: input.purpose ?? "retrieval",
    lawful_basis: input.lawfulBasis ?? "consent",
    cross_border: input.crossBorder ?? false,
    sector: input.sector ?? "development",
    event_type: input.eventType ?? "disclosure",
    agent_authorised: input.agentAuthorised ?? true,
    requires_minimisation: input.requiresMinimisation ?? true,
    // The engine is pure and takes its clock from the caller. This must be the
    // real evaluation instant: it is sealed verbatim into the audit record.
    timestamp: new Date().toISOString(),
  });
}

export async function getDabtComplianceMap(): Promise<DabtPayload> {
  await ensureDabtService();
  const complianceMap = await callDabtApi("/v1/compliance-map", "GET");
  return { ...complianceMap, buildInfo: DABT_BUILD_INFO };
}

export function shutdownDabtServiceForTests(): void {
  if (apiProcess && !apiProcess.killed) {
    apiProcess.kill("SIGTERM");
  }
  apiProcess = null;
  startupPromise = null;
}
