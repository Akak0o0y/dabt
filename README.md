# Dabt / ضبط — Gulf Agent Compliance Layer

> **A regulatory compliance layer for AI agents in the Gulf.** Dabt sits in the
> path of an AI system and decides, before the fact, whether Saudi regulation
> permits what it is about to do. It is an engineering tool, not a regulatory
> determination.

**Open for companies.** Dabt is available under the GNU AGPL-3.0, and under a
commercial licence for organisations that cannot accept the AGPL's network
source-disclosure obligation. See [LICENSING.md](LICENSING.md).

Most AI governance tooling answers *who is this agent* and *what was it granted
at setup*. Dabt answers a different question, at a different moment: **does Saudi
regulation permit this specific action, on this specific content, right now?** It
carries the jurisdiction-specific content — PDPL, NDMO classification, NCA
ECC-2:2024, SAMA CSF — that identity platforms and enterprise search tools do not.

It gates two surfaces on one deterministic engine:

- **Data Retrieval Gate** — evaluates a payload before it reaches a model.
- **Agent Action Gate** — evaluates an MCP tool call before it executes, and its
  result before that result is disclosed back to the agent.

Both return one of four outcomes: `ALLOW`, `ALLOW_WITH_REDACTION`, `DENY`, or
`REVIEW`, with the decision, the transformed release state, and supporting
bilingual evidence in English and Arabic.

The Action Gate ships with an in-path harness. [`proxy/`](proxy/README.md) is a
stdio MCP server an agent attaches to instead of the real one: it evaluates each
tool call before it executes and each result before disclosure, so the claim
that an agent cannot act contrary to policy is observable rather than argued.
It is vendor-neutral — the gated server is named by a tool manifest, and a
manifest can be supplied from outside the package.

There is no model in the decision path. Detection is regex and checksums, rules
are a validated YAML map with verbatim citations, and evaluation is a pure
function with an injected clock — so a decision is reproducible on demand during
an audit, and explainable by rule ID and article rather than by a score.

Every rule, mapping, and classification inference is deliberately labelled with a confidence level and `requires_legal_review: true`. **Nothing in Dabt is an authoritative legal, regulatory, or classification determination.** A qualified Saudi legal or compliance professional must review the applicable facts, entity context, and source regulations before any regulatory reliance.

## What the current reference build does

| Capability | What a reviewer can observe |
|---|---|
| **Retrieval gate** | Runs a deterministic six-stage policy pipeline: detection, classification, policy evaluation, obligation resolution, redaction, and bilingual audit logging. |
| **Agent action gate** | Evaluates an MCP tool call before execution and its result before disclosure, returning the same four outcomes. Tool semantics come from a validated per-server manifest rather than name heuristics. Ships with a reconstructed CranL manifest whose entries are all `needs_verification`, so every action against it resolves to `REVIEW` until the published tool schema is transcribed. |
| **In-path MCP gate** | Sits between an agent and any MCP server, refusing a call before it reaches that server and withholding a result before it reaches the model. A refusal names the rule, article, and mapping confidence in both languages. Carries no vendor knowledge: `--server-id` selects a manifest and `--manifest` loads one from anywhere on disk. |
| **Manifest scaffolding** | Drafts a tool manifest from a live MCP server's own `tools/list`, inferring operations and parameter roles. Every drafted entry is `needs_verification`, so an unreviewed draft holds every call at `REVIEW` — an inaccurate draft cannot permit anything. |
| **Saudi data detection** | Detects Saudi National ID/Iqama patterns, Saudi IBANs, Saudi mobile numbers, Commercial Registration number formats, and selected PDPL Sensitive Data signals. Checksum failure lowers confidence; it does not silently suppress a finding. |
| **Policy outcomes** | Separates `ALLOW`, `ALLOW_WITH_REDACTION`, `DENY`, and `REVIEW`. A mapping marked `needs_verification` cannot issue a terminal `DENY`; it degrades to `REVIEW`. |
| **Evidence Vault** | Persists authenticated, owner-scoped, immutable evidence snapshots containing hashes, decision evidence, classification evidence, bilingual audit data, legal caveats, and policy-map version. It does **not** persist the source document or release payload. |
| **Reviewer decision** | Allows an administrator to seal one bilingual `approved` or `rejected` disposition for a `REVIEW` snapshot. It is bound to the selected snapshot's integrity hash and a second write returns a conflict. |
| **Classification reconciliation** | Displays a policy-inferred classification beside an optional qualified-reviewer classification. The comparison is explicitly non-authoritative and remains subject to professional review. |

## What Dabt explicitly does **not** do

| Out of scope | Clarification |
|---|---|
| **Identity issuance or verification** | Dabt does not issue identity credentials, authenticate citizens, verify a person's legal identity, or connect to government identity systems. |
| **RAG, search, or agent platform** | Dabt is not a search index, vector database, retrieval-augmented generation platform, document management system, or general-purpose AI agent. It is a retrieval-policy reference layer. |
| **Operational safety** | Dabt gates regulatory violations, not operational blast radius. A destructive call carrying no regulated data passes the gate. Platforms should keep their own confirmation step for destructive operations. |
| **Production gateway plumbing** | The bundled MCP gate is a reference harness. It handles `tools/list` and `tools/call`; MCP resources, prompts, and completions are not forwarded. Production deployments run a real gateway and call the same policy API. |
| **Legal advisory or regulatory certification** | Dabt does not provide legal advice, certify compliance, replace a data-protection assessment, or determine that a transfer, disclosure, or classification is lawful. |
| **Authoritative control mapping** | Current NCA ECC-2:2024 and SAMA CSF subdomain references are intentionally marked `needs_verification`; leaf-level ECC control IDs are not asserted as verified. |
| **Automatic release after review** | A reviewer decision seals evidence; it does not automatically release the source payload or create a legal authorization. |

## Standing legal-review caveat

> **English:** This engineering output requires qualified Saudi legal or compliance review before regulatory reliance.
>
> **العربية:** يتطلب هذا المخرج الهندسي مراجعة قانونية أو مراجعة امتثال مؤهلة في المملكة العربية السعودية قبل الاعتماد التنظيمي.

This caveat appears in every audit record. It applies to all policy rules, data-classification mappings, control references, reviewer dispositions, and comparison displays.

## Current compliance-map coverage

The current map version is `0.1.0-research-grounded`. The following table is a transparent inventory of the rules actually implemented in `dabt_python/dabt_core/data/compliance_map.yaml`; it is not a claim of complete regulatory coverage.

### PDPL and NDMO decision rules

| Rule ID | Framework reference | Current policy outcome | NCA ECC-2:2024 subdomains | SAMA CSF subdomains | Map confidence |
|---|---|---|---|---|---|
| `NDMO-TOP-SECRET-DENY` | NDMO §4.3, **Top Secret** | `DENY` | `2-7` | `3.3` | verified rule; mapped controls need verification |
| `PDPL-ART6-4-SENSITIVE-LEGITIMATE-INTEREST` | PDPL Art. 6(4) | `DENY` | `2-7`, `2-13` | `3.2` | verified rule; mapped controls need verification |
| `PDPL-ART15-6-SENSITIVE-DISCLOSURE` | PDPL Art. 15(6) | `DENY` | `2-7` | `3.3` | verified rule; mapped controls need verification |
| `PDPL-ART23-HEALTH-DATA-RESTRICTION` | PDPL Art. 23(1) | `REVIEW` | `2-2`, `2-7` | — | verified rule; mapped controls need verification |
| `PDPL-ART24-CREDIT-DATA-CONSENT` | PDPL Art. 24(1) | `REVIEW` | `2-7` | `3.2` | **inferred** rule; mapped controls need verification |
| `PDPL-ART29-2C-CROSSBORDER-MINIMISATION` | PDPL Art. 29(2)(c) | `ALLOW_WITH_REDACTION` | `2-7`, `4-2` | `3.4` | verified rule; mapped controls need verification |
| `PDPL-ART15-5-ANONYMISED-DISCLOSURE` | PDPL Art. 15(5) | `ALLOW_WITH_REDACTION` | `2-7`, `2-12` | — | verified rule; mapped controls need verification |
| `PDPL-ART11-3-MINIMISATION` | PDPL Art. 11(3) | `ALLOW_WITH_REDACTION` | `2-7` | — | verified rule; mapped controls need verification |
| `NDMO-SECRET-RESTRICTED-ACCESS` | NDMO §4.2, Principle 6 | `ALLOW_WITH_REDACTION` | `2-2`, `2-7` | — | verified rule; mapped controls need verification |
| `NDMO-PUBLIC-ALLOW` | NDMO §4.3, **Public** | `ALLOW` | `2-12` | — | verified rule; mapped controls need verification |

### NDMO classification references implemented

The four NDMO levels in the map are **Public**, **Confidential**, **Secret**, and **Top Secret**. The engine applies maximum-level aggregation across findings and supports a configurable sector default.

| Classification scope | Current level(s) | Confidence and review status |
|---|---|---|
| Saudi National ID, Iqama, Saudi IBAN, Saudi mobile | Confidential | verified; legal review required |
| Saudi Commercial Registration number | Confidential | inferred under NDMO §4.2 Principle 2; legal review required |
| Health, biometric, genetic, criminal, and credit sensitive-data signals | Secret | inferred, conservative automated-retrieval elevation under NDMO §4.2 Principle 2; legal review required |
| Other detected Sensitive Data | Confidential | inferred fallback; legal review required |
| Development-sector default | Public | verified; legal review required |
| Security and political-sector defaults | Top Secret | verified; legal review required |

For the sensitive-data elevations, the map records both English and Arabic rationale plus a citation to NDMO §4.2 Principle 2. It explicitly notes that NDMO's medical-file example is **Confidential** and that Dabt's Secret assignment is a conservative inference for a mixed or aggregated automated-retrieval context—not an authoritative NDMO classification.

### Current cyber-control references

| Framework | Referenced subdomains in the current map | Status |
|---|---|---|
| **NCA ECC-2:2024** | `2-2`, `2-7`, `2-12`, `2-13`, `4-2` | Every reference is at **subdomain** granularity and marked `needs_verification`; no leaf control ID is presented as verified. |
| **SAMA CSF** | `3.2`, `3.3`, `3.4` | Every reference is at **subdomain** granularity and marked `needs_verification`. |
| **NCA CSCC** | None | The current map has no NCA Critical Systems Cybersecurity Controls mappings. |

The map references **SAMA CSF**, not “SAMA CSCC.” CSCC refers to an NCA control framework and is outside the current map's implemented coverage.

## Architecture and repository guide

| Location | Purpose |
|---|---|
| `dabt_python/dabt_core/` | Pure-function Python policy kernel, detectors, classifier, redaction, bilingual audit record, and validated compliance map. |
| `dabt_python/dabt_api/` | FastAPI boundary for evaluation and read-only policy-map access. |
| `proxy/` | The in-path MCP gate, its manifest scaffolder, and a runnable demonstration. Depends on the kernel; the kernel does not depend on it. |
| `drizzle/` | Database schema and migrations for evidence snapshots and reviewer decisions. |
| `dabt_python/api/` | Hosting entrypoint. On a serverless host the FastAPI app *is* the function, so there is no subprocess. |
| `docs/` | Approved design, implementation plan, research notes with primary-source provenance, and the Arabic QA record. |

## Running it

Python 3.11 or later (the kernel uses `enum.StrEnum`).

```bash
cd dabt_python
pip install -e .
pytest -q                       # 192 tests
uvicorn dabt_api.main:app --port 8743
```

Four endpoints: `POST /v1/retrieval/evaluate`, `POST /v1/action/evaluate`,
`POST /v1/action/result`, and `GET /v1/compliance-map`. Every call requires an
explicit ISO 8601 `timestamp` with a UTC offset — the engine takes its clock
from the caller, and a decision that cannot say when it was made is not one
worth recording.

Set `DABT_MANIFEST_DIRS` to load tool manifests from outside the package, so an
organisation can gate its own MCP server without forking the kernel.

### Seeing a call get stopped

```bash
pip install -e ./dabt_python -e ./proxy
python proxy/demo/run_demo.py
```

The demonstration runs the gate as a real subprocess in front of a fixture MCP
server. An out-of-Kingdom provisioning call is refused before it reaches that
server; a database is created and its connection string is then withheld with
the refusal stating that the write itself stands; an environment listing is
released with only the regulated values masked. See
[`proxy/README.md`](proxy/README.md) for attaching an agent to it and for
onboarding a new organisation.

## Repositories

| | |
|---|---|
| **This repository** | The policy layer. Engine, compliance map, tool manifests, tests, and the research behind them. This is what an integrator calls. |
| [`Akak0o0y/dabt-demo`](https://github.com/Akak0o0y/dabt-demo) | The bilingual reference interface. Useful for showing a decision to a human; not required to use the layer. |

The two are separate because they are separate things. The demo talks to a
hosted engine over `DABT_BASE_URL` and carries no copy of it.

## References

[1] [Saudi Data & AI Authority, *Personal Data Protection Law* (English)](https://sdaia.gov.sa/en/SDAIA/about/Documents/Personal%20Data%20English%20V2-23April2023-%20Reviewed-.pdf)

[2] [National Data Management Office, *Data Classification Policy* (English)](https://sdaia.gov.sa/ndmo/Files/PoliciesEn.pdf)

[3] [National Cybersecurity Authority, *Essential Cybersecurity Controls (ECC-2:2024)*](https://nca.gov.sa/en/regulatory-documents/controls-list/ecc/)

[4] [Saudi Central Bank, *Cyber Security Framework*](https://rulebook.sama.gov.sa/en/cyber-security-framework-2)

## Licence

Dual-licensed. **GNU AGPL-3.0** by default ([`LICENSE`](LICENSE)), and a
**commercial licence** for use without the AGPL's source-disclosure obligation.
Full terms and what they do *not* cover — notably the quoted regulatory texts,
which are not ours to license — are in [LICENSING.md](LICENSING.md).

Copyright © 2026 Abdulaziz Al-Dhamri. Commercial licensing enquiries: <abdulazizaldhamri@gmail.com>.

