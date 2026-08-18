# Dabt (ضبط) — Project Handoff v3

**Date:** 18 August 2026
**Repository:** `github.com/Akak0o0y/dabt`, branch `main`, tip `3401447`
**Live demo:** `dabt-demo-krxybfjz.manus.space` — **stale, do not cite** (see §5)

This supersedes Handoff v2 (18 August 2026, 09:23 +03). Changes from v2 are
marked **[NEW]** or **[CORRECTED]**. Everything unmarked carries forward
unchanged.

> **Standing legal caveat.** Every regulatory mapping in this project is an
> engineering artifact, not legal advice. Each carries `requires_legal_review:
> true` without exception. Nothing here may be relied upon in a regulatory audit
> until a qualified Saudi legal or compliance professional has signed it off.

---

## 1. What Dabt Is, In One Sentence

A real-time regulatory policy enforcement layer that sits on top of whatever
identity engine or search/RAG system a customer already runs, and answers,
synchronously at the moment of action: "Does Saudi regulation permit this
specific data retrieval, right now?"

It is not an identity provider, not a search/RAG engine, and not a legal
advisory service. It is the missing layer between those systems and Saudi
regulatory reality — PDPL, NDMO classification, NCA ECC-2:2024, and SAMA CSF.

**[NEW] The product thesis, stated by the founder and previously understated in
this document:** Dabt is intended to sit *on top of agentic systems*, so that an
agent cannot take an action contrary to the Kingdom's policy. Data retrieval is
one class of action and the one proven first. The intended delivery route is a
partnership with a Saudi PaaS provider that already runs MCP-based agent
deployment and has local legal presence but no compliance layer — Dabt supplies
that layer. Every prior revision of this handoff, including §4.1 below,
described the Agent Action Gate as a deferred second surface. Against this
thesis it is not a deferral: it is the product, and the retrieval gate is the
half that proves the machinery works. §9 is re-ordered accordingly.

Working name: "Dabt" (ضبط — Arabic for "control"). Not final branding.

---

## 2. Strategic Positioning

Carried forward from v2 unchanged. The market figures, competitor set, and
funding numbers in this section come from the project's own research pass
(Feb–Aug 2026) and have **not been independently re-verified** in this revision.
Treat them as of that date.

- The global AI-agent identity/governance market raised $8.1B in 2026, with
  well-funded players (Oak, NewCore, Oasis Security, Arcade.dev, Astrix, Clutch,
  Aembit, Willow, Alien) — none with Gulf/Arabic regulatory content.
- Microsoft Agent 365 and the KPMG–Anthropic alliance both build the same
  general mechanism (identity + audit + compliance mapping) but map only to
  Western frameworks — zero Saudi/Gulf content in public documentation.
- Enterprise search/RAG permission tooling (Glean, Microsoft 365 Copilot) solves
  "who can see this document" using source-system ACLs — neither applies NDMO
  classification nor Saudi-specific PII redaction (National ID, Iqama, Saudi
  IBAN) that generic DLP misses.
- The gap Dabt fills is the intersection none of them cover: actual Saudi
  regulatory content + real-time inline enforcement + self-serve pricing for
  mid-market rather than Big-Four consulting fees.

**The strongest legal argument, and it should lead the pitch:** PDPL Art. 1(5)
defines "retrieving" as Processing; Art. 29(2)(c) requires cross-border
transfers be "limited to the minimum amount of Personal Data needed." Every call
to a foreign-hosted LLM over Saudi personal data is therefore a regulated
Transfer today — redaction-before-transfer is not hardening, it is the
compliance mechanism itself.

---

## 3. What Has Actually Been Built

### 3.1 The core policy engine — built, tested, verified

A pure-function Python engine (`dabt_python/dabt_core/`), deterministic, zero
I/O, six-stage pipeline (detection → classification → policy evaluation →
obligation resolution → redaction → bilingual audit). Five Saudi-specific
detectors, NDMO four-level classification with Principle 4 max-aggregation, and
a four-outcome decision model (`ALLOW` / `ALLOW_WITH_REDACTION` / `DENY` /
`REVIEW`) required because PDPL's minimisation provisions do not fit a binary.

Independently verified: checksum-failure behaviour lowers confidence and never
suppresses a finding. All seven cited PDPL articles confirmed verbatim against
the official SDAIA PDF.

### 3.2 The compliance map — built, research-grounded, verified

`compliance_map.yaml` — every rule carries a verbatim citation, bilingual
rationale, `confidence_level`, and `requires_legal_review: true`, enforced by
schema validation at load time. Framework corrections applied: SAMA CSF and NCA
CSCC treated as separate regulator frameworks; target edition ECC-2:2024;
NDMO's third tier canonically "Confidential" with "Restricted" as synonym; all
NCA ECC mappings capped at subdomain granularity and marked
`needs_verification`.

**10 rules ship against 11 planned.** See §6.1.

### 3.3 The demo application — built, tested, verified

React 19 + tRPC 11 + Drizzle. **[CORRECTED]** The database is **MySQL**
(`drizzle-orm/mysql-core`, `mysql2` driver) — v2 said Postgres, which was wrong.
Bilingual (AR/EN, RTL-correct) UI. Includes:

- **Evidence Vault:** durable, immutable, owner-scoped snapshots. Verified
  directly — no column exists for source document text or release payload; only
  hashes and evidence fields are persisted.
- **Reviewer approval workflow:** admin-only, bound to the snapshot's integrity
  hash, immutable after first decision (a second write returns `CONFLICT`).
- **Compare view:** inferred vs. reviewer-approved classification, explicitly
  non-authoritative.
- **Release-state logic:** `DENY`/`REVIEW` block the payload panel entirely.

### 3.4 **[NEW]** Five correctness fixes — commit `574f21f`

Five implementation defects found by external review and fixed without changing
any policy semantics. No rule, decision, classification level, obligation
directive, or compliance-map entry was modified.

| Defect | Behaviour before | Behaviour after |
|---|---|---|
| Sensitive detector matched bare substrings | "bracelet" → ethnic finding; "healthy" → health finding; benign text classified **Secret** | Latin terms word-bounded with plural tolerance; Arabic uses a per-token affix envelope with Arabic-letter lookarounds |
| Redaction masked the trigger keyword | `ALLOW_WITH_REDACTION` blacked out the word "medical" and left the diagnosis in clear text | Findings carry a redaction span distinct from the detection span, covering the sentence holding the content; keyword-triggered content always masked in full |
| Audit timestamp hardcoded | Every sealed audit record attested to `2026-08-17T00:00:00Z` | Real evaluation time |
| Commercial Registration absent from personal-data set | CR classified Confidential but never redacted | CR now triggers minimisation rules |
| Demo default state unreachable | Default sample + lawful basis could only resolve to `DENY` or `REVIEW`, both of which withhold the payload — Art. 29(2)(c) redaction was unreachable without editing the sample | Default preset resolves to `ALLOW_WITH_REDACTION` under `PDPL-ART29-2C-CROSSBORDER-MINIMISATION`; second preset demonstrates the prohibited case |

**On Arabic specifically:** a bare regex word boundary is the wrong tool, not
merely insufficient. Python treats Arabic letters as word characters, so
`\bصحي\b` rejects every attached form — and attachment (definite article,
conjunction and preposition proclitics) is how the word is normally written.
Verified: bare `\b` matched `صحي` but missed `الصحية`, `وبالصحية`, and
`بيانات صحية`. The shipped affix envelope matches all four and still rejects an
unrelated word sharing letters (`مصباح`). **Known limitation:** tashkeel is not
normalised, so a fully vowelled document may not match.

Verification: 103 Python tests pass (95 baseline + 8 regression tests added),
`pnpm check` exits 0, `pnpm build` succeeds, `pnpm test` passes 21 of 22 — the
one failure is a pre-existing `python3`-resolution issue on Windows, proven
identical against unmodified `HEAD`.

### 3.5 **[NEW]** Documentation recovered into version control — commit `3401447`

`README.md` line 91 advertised a `docs/` directory that had never existed in git
across 19 commits. The files lived only on the Manus build sandbox. They are now
committed verbatim, byte-identical to the recovered originals:

| Path | Contents |
|---|---|
| `docs/specs/2026-08-17-dabt-design.md` | Approved design specification |
| `docs/plans/2026-08-17-dabt-implementation.md` | Task-level implementation plan |
| `docs/research/pdpl_identifiers.md` | PDPL article-level findings + Saudi identifier formats |
| `docs/research/ndmo_sama.md` | NDMO classification + SAMA CSF research |
| `docs/research/nca_ecc.md` | NCA ECC-2:2024 structure and caveats |
| `docs/qa/2026-08-17-arabic-copy-qa.md` | Arabic copy QA record |

The research notes are the most consequential recovery: they carry the
provenance for every confidence flag, including the finding that a widely cited
secondary ECC source sums its own Domain 1 subdomain counts to 50 against a
stated 35. That inconsistency is *why* leaf controls are marked
`needs_verification`. That reasoning previously existed nowhere in the
repository.

### 3.6 What "built" means here, precisely

All of the above is a standalone reference implementation. It proves the policy
logic works and is legally grounded. It does not yet intercept traffic from any
real external system. You paste document text and declare a lawful basis;
nothing is pulled automatically from a real search engine or agent framework.

---

## 4. What Has NOT Been Built — Deliberate

Unchanged from v2 and still correct.

**4.1 No identity-engine integration.** The Agent Action Gate
(`POST /v1/action/evaluate`) returns a documented `501`. Validating one surface
before building the second was the plan; building an Oak-specific integration
before a customer confirms they use Oak is speculative engineering.

**4.2 No search/RAG adapter.** The engine is surface-agnostic by design. The
missing piece is middleware in front of Glean's or Copilot's retrieval call.
Deferred for the same reason as 4.1.

**4.3 No legal sign-off.** Every mapping is flagged `requires_legal_review:
true` without exception. This is a permanent standing constraint, not a task
with an end date.

**4.4 No production IAM, secrets handling, or multi-tenancy.** Single-tenant,
one authenticated owner scope. Should not exist until there is a paying
customer.

---

## 5. **[NEW]** Current State of Record

This section replaces v2 §5 entirely.

### 5.1 v2 §5 is resolved — and its diagnosis was partly wrong

v2 flagged that the production checkpoint check had never passed at
`dabt.complianceMap`. It has now been checked directly.

- `dabt.buildInfo` returns `documentationCheckpoint: "9b13792a"`, HTTP 200. The
  route's mere existence proves the deployed backend includes `57e0297`, the
  commit that added it.
- `dabt.complianceMap` **also** returns the checkpoint, nested under a
  `buildInfo` key. v2's stated reason — "the wrong endpoint, the checkpoint was
  never on that route" — was true of the *repository* and false of *production*,
  for the reason in §5.3.
- `/dabt-build.json` returns HTTP 200 `application/json`, so the `todo.md` item
  claiming static manifest routes fall through to the client 404 page is stale.

Cite `dabt.buildInfo` going forward: it is the route that exists in version
control.

### 5.2 Production is two commits behind

Verified against the live URL on 18 August 2026:

```
document: "The bracelet traced a graceful arc. Our loaner fleet is healthy."
→ findings: 5   classification: Secret   decision: REVIEW
→ audit.timestamp: 2026-08-17T00:00:00Z
```

Production predates `574f21f`. All five fixes in §3.4 are committed, pushed, and
verified — and inert.

### 5.3 Production is running code that exists in no commit

Two source files were modified on the Manus sandbox, deployed, and never pushed:

| File | Un-pushed change | Live? |
|---|---|---|
| `server/dabt.ts` | `getDabtComplianceMap()` merges `buildInfo` into the response | Yes |
| `server/_core/index.ts` | Express route `GET /api/build-info` | Yes |

Neither exists at `57e0297` or on `origin/main`. **The deployed artifact does
not correspond to any revision of this repository.** For a regulatory-facing
system, "what code produced this decision?" currently has no answer.

### 5.4 The compounding risk

The Manus sandbox copy of `server/dabt.ts` still contains
`timestamp: "2026-08-17T00:00:00Z"` — the exact line `574f21f` replaced. Any
merge resolved toward that copy silently reverts the audit-timestamp fix.

Separately: every authenticated evaluation run against current production writes
a permanent evidence snapshot whose sealed audit record carries the frozen
timestamp while its own `createdAt` column carries the real one. The Evidence
Vault is immutable by design — those records cannot be corrected, and reviewer
decisions seal themselves to their integrity hashes. Exposure grows with usage.

### 5.5 Consequence, stated plainly

**Do not point anyone at the live demo — prospect, partner, or regulator — until
it is redeployed.** The entire proposition is epistemic integrity. A public demo
that classifies "bracelet" as ethnic-origin data and stamps every audit record
with the same instant undercuts that harder than having no demo at all.

The repository is correct and complete. The shop window is wrong. That is
survivable only while the window stays closed.

---

## 6. **[NEW]** Known Gaps and Open Decisions

### 6.1 `PDPL-ART16-ABSOLUTE-PROHIBITION` was planned and never shipped

Implementation plan Task A3 specifies it as a verified `DENY` at priority 110,
covering Article 16's absolute disclosure prohibitions — threats to security,
harm to the Kingdom's reputation, interests, or relations with another state,
prevention of crime detection, compromise of individual safety. The map ships
10 rules against 11 planned.

This is the hard-deny tier above ordinary lawful-basis analysis. Nothing in the
engine currently covers it except reaching Top Secret classification by another
route. **Decision required:** implement it, or record why it was dropped. If
implemented, the map requires a *verbatim* citation quote — the research notes
carry only a paraphrase of Article 16, so the exact text must be pulled from the
official SDAIA PDF. Paraphrase in a `quote` field is defined as a defect by
design spec §7.

### 6.2 Rule priority ordering diverged from the plan

The plan orders the PDPL denials (100, 100, 110) ahead of `NDMO-TOP-SECRET-DENY`
(120). The shipped map inverts this (10 vs 20, 30). Both paths still deny, so no
outcome changes — but the rule cited as the decision basis in the audit record
differs for a document satisfying both. For an evidence artifact whose value is
naming the governing article, that is a real difference.

### 6.3 The Commercial Registration inference lives in the wrong place

`saudi_commercial_registration` was added to `Finding.is_personal_data`, which
functions as "triggers PDPL minimisation obligations." A CR number identifies a
company, not a natural person — it is personal data only for a sole
proprietorship. The effect is conservative (more redaction, never less), but in
a system where every inference carries `confidence_level`, bilingual rationale,
and citation, this one currently lives as a Python set membership rather than a
compliance-map entry. **Decision required:** move it into the map, which means
adding a concept to the map schema (which finding types carry personal-data
obligations).

### 6.4 Lesser items

- Arabic tashkeel is not normalised in the sensitive-data detector.
- The public unauthenticated `dabt.evaluate` procedure accepts 100,000-character
  documents with no rate limit.
- Substantial dead Manus scaffold remains: `ComponentShowcase.tsx` (1,437
  lines), `Map.tsx`, `AIChatBox.tsx`, `imageGeneration.ts`,
  `voiceTranscription.ts`, `storageProxy.ts`.
- `server/dabt.ts` spawns the Python service via `spawn("python3", …)` with a
  hardcoded binary name, no restart, and no backoff. It fails on any host where
  `python3` does not resolve.

---

## 7. Future Vision

### 7.1 Near term — only after external validation signals it is needed

- Build the Glean or Microsoft 365 Copilot retrieval adapter — whichever a real
  prospect actually uses.
- Build the Agent Action Gate integration with whichever identity engine a real
  prospect actually uses.
- Add per-agent/per-operation usage metering, since the business model is
  usage-based.

### 7.2 Medium term — the moat-building phase

- Submit to the SDAIA Regulatory Sandbox and, if a fintech pilot materialises,
  the SAMA Regulatory Sandbox in parallel. Sandbox standing is the credibility
  asset no foreign competitor can replicate quickly — it requires Saudi legal
  presence and a real repeated relationship with the regulator, not capital.
- Get the compliance map formally reviewed and signed off, converting every
  `needs_verification` and `inferred` flag into a confirmed mapping or an
  explicitly documented limitation.
- Land one lighthouse customer and turn it into a public case study.

### 7.3 Long term — the platform-partnership path

A Saudi PaaS provider with local legal presence and an MCP-based AI deployment
server, but no compliance layer, remains a live integration option alongside
building Dabt as an independent product. Both paths deliberately left open.

### 7.4 Commercial model, once validated

Two-module, usage-based B2B SaaS: Data Retrieval Gate and Agent Action Gate sold
as separable add-ons on the same core engine, priced per agent/action gated or
per retrieval event classified per month. Target customers: Saudi
banks/fintechs (especially SAMA sandbox participants), mid-market companies
running Glean/Copilot, and government-adjacent entities under NCA obligations.

---

## 8. Risks

**8.1 Competitive.** If a global vendor adds Gulf-specific compliance content
before Dabt achieves sandbox standing and a real customer relationship, the
technical moat disappears — the code is rebuildable by any competent team. The
durable asset is accumulated legal validation and regulatory relationships.

**8.2 Mapping accuracy.** If the compliance map's mappings turn out substantively
wrong on legal review, the credibility proposition collapses. This is why
`requires_legal_review: true` is enforced structurally rather than treated as a
formality.

**8.3 [NEW] Platform dependency on Manus.** Three distinct manifestations
observed:

- **Artifact loss.** The approved design spec, implementation plan, research
  notes, and QA record existed only on the build sandbox and were nearly lost.
  They are now in git (§3.5). The two un-pushed source files in §5.3 remain at
  the same risk today.
- **Sovereignty optics. [CORRECTED 18 Aug]** An earlier draft of this section
  claimed the production page loads a Manus debug collector. That is wrong: the
  collector is gated off in production (`vite.config.ts` returns the HTML
  unmodified when `NODE_ENV === "production"`), and the live page confirms it is
  absent. What the live page *does* load, all injected by the hosting platform
  rather than by anything in this repository:
  `files.manuscdn.com/manus-space-dispatcher/spaceEditor-*.js`, Umami analytics
  (`manus-analytics.com/umami`), Plausible analytics (`plausible.io`), an
  injected `amplitudeKey` and `apiHost: 'https://api.manus.im'`, and Google
  Fonts. These are page-level analytics; there is no evidence any of them
  capture the contents of the evaluation textarea, and this is not a claimed
  data leak. It is, however, three third-party telemetry services and a foreign
  platform script on the demo page of a data-sovereignty product — a question
  worth not having to answer. All of it disappears on any other host, because
  none of it is in the repository.
- **Execution reliability.** A detailed remediation request was delivered to the
  Manus agent and not carried out; the agent transcribed its four tasks into
  `todo.md` as unchecked items and exported an archive instead.

**Mitigation available without a rewrite.** The engine is pure functions with no
I/O, an injected timestamp, injected detectors, and a validated map — it is
already extraction-ready. The `Dockerfile` (node:22-slim + python3) runs the
whole stack on any container host. The public gate (`evaluate`,
`complianceMap`, `buildInfo`) requires no authentication and would work
immediately elsewhere; only the Evidence Vault login depends on Manus OAuth.

---

## 9. Immediate Next Actions

Ordered. Items 1–3 are engineering and can be done today; items 4–5 have the
longest lead time and no engineering dependency.

1. **Commit the two un-pushed production files** (§5.3) so the repository is a
   faithful record of everything live. This de-risks the Manus sandbox
   disappearing and removes the merge hazard in §5.4. Minutes of work.
2. **Resolve deployment.** This is the only hard blocker on the engineering
   column. Either redeploy from Manus, or move hosting — the existing Dockerfile
   runs anywhere. Then verify behaviourally, not via `DABT_BUILD_INFO`, which is
   a hand-maintained constant that proves nothing:
   - benign-text probe returns 0 findings / `Public` / `ALLOW`
   - `audit.timestamp` is the current time
   - default preset resolves to `ALLOW_WITH_REDACTION`
3. **Decide §6.1 and §6.3** — ART16, and where the CR inference lives. Both are
   regulatory-content decisions, not code cleanups, and should not be delegated
   to an agent working from a task list.
4. **Draft the SDAIA Regulatory Sandbox application.** The evidence package is
   materially stronger than it was: approved spec, task-level plan, research
   notes with primary-source provenance, Arabic QA record, 103 passing engine
   tests — all now in version control. Pull the actual current application
   criteria rather than assuming them.
5. **Start legal review of the compliance map.** Longest lead time, no
   engineering dependency, can begin the moment the map stops moving.

Do not build either integration adapter speculatively (§4.1, §4.2). Do not
rebuild the codebase — the valuable part is already separable; what would be
replaced is scaffold.
