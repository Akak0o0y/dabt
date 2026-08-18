# Dabt MCP Gate

A stdio MCP server that sits in front of another MCP server. It evaluates every
`tools/call` against Saudi regulatory policy **before** the call executes, and
evaluates the result **before** that result is disclosed back to the agent.

No vendor is built in. Which server it gates is decided by a tool manifest, and
a manifest can be supplied from anywhere on disk — so gating a new
organisation's MCP server means writing a YAML file, not forking the engine.

> **Standing caveat.** Every regulatory mapping here is an engineering artifact,
> not legal advice. A qualified Saudi legal or compliance professional must
> review the applicable facts before any regulatory reliance.

## What it does

```
agent ──tools/call──▶ dabt-proxy ──▶ POST /v1/action/evaluate   (request leg)
                          │              DENY / REVIEW ─▶ refused, cited, bilingual
                          │                               upstream never called
                          ▼
                     upstream MCP server
                          │
                          ▼
                      POST /v1/action/result                    (response leg)
                          DENY / REVIEW ─▶ disclosure withheld
                          ALLOW_WITH_REDACTION ─▶ masked values released
```

The request leg is the only place a side effect can be prevented. The response
leg cannot unwind a write that already ran, but it can still stop a live
credential reaching the model — a separate event worth stopping, so a refusal
there says explicitly that the side effect stands.

## Install

Requires Python 3.11+ (`dabt_core` uses `enum.StrEnum`).

```bash
uv venv --python 3.12 .venv
uv pip install -e ./dabt_python -e ./proxy
```

## Try it

Runs the gate as a real subprocess against a fixture PaaS MCP server:

```bash
python proxy/demo/run_demo.py
```

You should see an out-of-Kingdom provisioning call refused before it reaches the
server, a database created whose connection string is then withheld, and an
environment-variable listing released with only the regulated values masked.

## Attach an agent to it

In an MCP client's server configuration:

```json
{
  "mcpServers": {
    "acme-gated": {
      "command": "dabt-proxy",
      "args": [
        "gate",
        "--server-id", "acme",
        "--manifest", "/etc/dabt/acme.yaml",
        "--upstream-http", "https://mcp.acme.example/mcp"
      ]
    }
  }
}
```

Or spawn a local upstream instead:

```bash
dabt-proxy gate --server-id acme --manifest ./acme.yaml \
  --upstream-stdio "npx -y @acme/mcp-server" --upstream-env ACME_TOKEN=...
```

Useful flags: `--sector financial` (sets the NDMO classification floor),
`--audit-log ./audit.jsonl`, and `--policy-url http://127.0.0.1:8743` to
evaluate against a running Dabt service instead of in-process.

## Onboarding a new organisation

1. **Draft a manifest** from the server's own tool list:

   ```bash
   dabt-proxy scaffold --server-id acme --upstream-http https://mcp.acme.example/mcp > acme.yaml
   ```

2. **Review every line.** Operation, resource type, roles and maskability are
   inferred from naming and JSON Schema shape. They are guesses.

3. **Raise entries to `verified`** once their semantics are confirmed against
   the vendor's documentation.

Until step 3, every call resolves to `REVIEW`: the action ALLOW rule requires
`tool_confidence: verified`, so an unreviewed draft cannot permit anything. An
inaccurate draft fails safe.

## Two ways to reach the engine

| | In-process (default) | `--policy-url` |
|---|---|---|
| Path | imports `ActionEngine` | HTTP to the FastAPI service |
| If the service is down | unaffected | every call denied |
| Custom manifests | `--manifest` | `DABT_MANIFEST_DIRS` on the service |

In-process is the default because it makes "fails closed" structurally true
rather than true while a service happens to be up. HTTP exists because it is the
integration pattern a production gateway (TrueFoundry, Permit.io, ContextForge)
would follow. Both parse the same payload shape, so they cannot drift.

## What it deliberately does not do

- **Operational blast radius.** A clean `delete_database` carries no Saudi
  personal data and breaches no mapped provision, so it passes. Keep your own
  confirmation step for destructive operations.
- **Generic credential detection.** Only manifest-declared credentials are
  caught. An undeclared secret in an opaque field is not detected.
- **Resources, prompts, completions.** Only `tools/list` and `tools/call` are
  handled. Other MCP capabilities are not forwarded.

## Known limitations

1. **Nested arguments lose their type when masked.** Arguments are stringified
   for scanning; an unmasked argument is returned exactly as received, but a
   masked structured argument comes back as a string. Declare `maskable: false`
   for structured parameters where that matters.
2. **Uninspectable content is held, not scanned.** A response carrying image or
   audio blocks resolves to `REVIEW`, because the detectors cannot read it.
3. **Manifest accuracy is asserted, not verified.** If a vendor changes a tool's
   behaviour without a manifest update, the gate reasons from a stale model.
   `manifest_version` in every audit record makes that auditable after the fact,
   not preventable.
4. **Arabic tashkeel is not normalised**, inherited from the retrieval surface.

## Audit records

Every decision is written as one JSON line to stderr, and to `--audit-log` if
given. `stdout` carries MCP protocol framing only.

A record states the decision, the rule, the citation, and the finding *types*
and element paths. It never contains the value that was withheld — a gate whose
log holds the secret it just refused has moved the leak rather than closed it.

## Tests

```bash
cd proxy && python -m pytest
```
