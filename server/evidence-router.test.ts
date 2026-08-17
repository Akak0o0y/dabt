import { beforeEach, describe, expect, it, vi } from "vitest";
import type { TrpcContext } from "./_core/context";

const evaluateDabt = vi.fn();
const persistAuditEvidence = vi.fn();
const listAuditEvidence = vi.fn();
const getAuditEvidence = vi.fn();

vi.mock("./dabt", () => ({
  evaluateDabt,
  getDabtComplianceMap: vi.fn(),
}));

vi.mock("./evidence", () => ({
  persistAuditEvidence,
  listAuditEvidence,
  getAuditEvidence,
}));

const { appRouter } = await import("./routers");

const evaluation = {
  decision: "DENY",
  decision_rule_id: "PDPL-ART6-4-SENSITIVE-LEGITIMATE-INTEREST",
  classification: "Secret",
  policy_map_version: "0.1.0",
  classification_evidence: {},
  audit: {},
  legal_review_disclaimer_en: "Legal review required.",
  legal_review_disclaimer_ar: "تتطلب مراجعة قانونية.",
};

function authenticatedContext(): TrpcContext {
  return {
    user: {
      id: 7,
      openId: "evidence-owner",
      name: "Evidence Owner",
      email: "owner@example.test",
      loginMethod: "manus",
      role: "user",
      createdAt: new Date(),
      updatedAt: new Date(),
      lastSignedIn: new Date(),
    },
    req: {} as TrpcContext["req"],
    res: {} as TrpcContext["res"],
  };
}

function anonymousContext(): TrpcContext {
  return { user: null, req: {} as TrpcContext["req"], res: {} as TrpcContext["res"] };
}

describe("durable evidence tRPC procedures", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    evaluateDabt.mockResolvedValue(evaluation);
    persistAuditEvidence.mockResolvedValue({ id: "evidence_001", integrityHash: "a".repeat(64), createdAt: new Date() });
    listAuditEvidence.mockResolvedValue([]);
    getAuditEvidence.mockResolvedValue({
      id: "evidence_001",
      auditJson: JSON.stringify({ decision_rule_id: "PDPL-ART6-4-SENSITIVE-LEGITIMATE-INTEREST" }),
      classificationEvidenceJson: JSON.stringify({ mapping_key: "sensitive_data.health" }),
    });
  });

  it("evaluates and persists server-produced evidence for the authenticated owner", async () => {
    const caller = appRouter.createCaller(authenticatedContext());
    const result = await caller.dabt.evaluateAndPersist({ document: "sensitive payload", lawfulBasis: "consent" });

    expect(evaluateDabt).toHaveBeenCalledWith(expect.objectContaining({ document: "sensitive payload" }));
    expect(persistAuditEvidence).toHaveBeenCalledWith(7, "sensitive payload", evaluation);
    expect(result.snapshot.id).toBe("evidence_001");
    expect(result.evaluation).toEqual(evaluation);
  });

  it("lists only the authenticated owner’s evidence records", async () => {
    const caller = appRouter.createCaller(authenticatedContext());
    await caller.dabt.evidenceList({ limit: 10 });
    expect(listAuditEvidence).toHaveBeenCalledWith(7, 10);
  });

  it("rejects anonymous persistence attempts", async () => {
    const caller = appRouter.createCaller(anonymousContext());
    await expect(caller.dabt.evaluateAndPersist({ document: "sensitive payload" })).rejects.toMatchObject({
      code: "UNAUTHORIZED",
    });
    expect(persistAuditEvidence).not.toHaveBeenCalled();
  });

  it("retrieves a full evidence record only for its authenticated owner", async () => {
    const caller = appRouter.createCaller(authenticatedContext());
    const result = await caller.dabt.evidenceGet({ id: "evidence_001" });
    expect(getAuditEvidence).toHaveBeenCalledWith(7, "evidence_001");
    expect(result?.auditJson).toContain("PDPL-ART6-4-SENSITIVE-LEGITIMATE-INTEREST");
    expect(result?.classificationEvidenceJson).toContain("sensitive_data.health");
  });
});
