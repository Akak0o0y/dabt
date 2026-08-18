# Dabt Agent Action Gate — Design Specification

**Date:** 18 August 2026
**Status:** Awaiting review
**Surface:** Second enforcement surface on the existing Dabt policy engine
**Concrete integration target:** CranL hosted PaaS MCP server (16 tools)

> **Standing legal caveat.** Every regulatory mapping described here is an
> engineering artifact, not legal advice. Each carries `requires_legal_review:
> true` without exception. Nothing here may be relied upon in a regulatory audit
> until a qualified Saudi legal or compliance professional has signed it off.

---

## 1. Purpose

The Data Retrieval Gate decides whether a payload may cross a boundary toward a
model. The Agent Action Gate decides whether an agent may **execute a tool
call**, and whether the **result of that call** may be disclosed back to it.

It sits in-path: the agent cannot act until the gate answers. It is not
advisory, because an advisory gate an agent can ignore does not support the
claim that an agent cannot act contrary to the Kingdom's policy.

Per the landscape research of 18 August 2026, Dabt is the **policy brain**, not
the interception plumbing. Identity is solved elsewhere (Entra Agent ID, Oak).
MCP gateways are solved elsewhere (TrueFoundry, Permit.io, IBM ContextForge,
Microsoft AGT). What none of them carry is jurisdiction-specific regulatory
content. That is the whole of Dabt's contribution here.

## 2. Scope boundary

**In scope:** regulatory violations under PDPL, NDMO, NCA ECC, and SAMA CSF, as
mapped in `compliance_map.yaml`.

**Out of scope: operational blast radius.** `delete_database(name="production")`
carries no Saudi personal data and breaches no mapped provision. Dabt will not
stop it and must not pretend to. Destructive-operation control is generic
scope/allowlist policy belonging to the MCP gateway layer. Claiming otherwise
would be the same overreach as citing Article 29 for an action that transferred
nothing.

This boundary is load-bearing. §6 specifies the rule that makes it true rather
than aspirational.

**State the guarantee at its true width.** In a partner conversation the claim
is: *Dabt guarantees no action executes that violates Saudi data protection,
classification, or cross-border transfer law. It does not evaluate operational
safety such as accidental data loss, and the platform should keep its own
confirmation step for destructive operations.* Do not let "policy layer" round
up to "the agent cannot do anything wrong" in the room. That gap is exactly
where a partner's trust breaks the first time a clean `delete_database` passes
`ALLOW` and something bad happens operationally.

## 3. Architecture

```
dabt_python/dabt_core/
  manifest.py      NEW   load + validate a tool manifest, strict like schema.py
  action.py        NEW   ActionRequest / ActionResult / ActionEngine
  rules.py         NEW   rule_matches() lifted verbatim from engine.py
  engine.py              TWO CHANGES: import rule_matches from rules.py,
                         and set context["surface"] = "retrieval"
  detectors/  classifier.py  redactor.py  audit.py    unchanged, reused

dabt_python/dabt_api/main.py    /v1/action/evaluate and /v1/action/result
dabt_python/data/manifests/cranl.yaml    NEW
proxy/                                   NEW  ~150-line reference MCP passthrough
```

`ActionEngine.evaluate()` runs the same six stages. Two differences: detection
runs over argument and response *values* rather than one document, and redaction
rewrites those values rather than spans in text. Classification, rule
evaluation, obligation resolution, and bilingual audit are untouched — an action
inherits NDMO Principle 4 aggregation and the legal-review caveat for free.

`engine.py` is **not** unchanged, and an earlier draft of this spec wrongly said
it was. It takes two edits: the `rules.py` import, and one line injecting
`surface` into its context dict. Without that second line the `surface`
condition added to `NDMO-PUBLIC-ALLOW` in §6.3 would silently stop matching,
because `rule_matches()` returns False for an absent key — and every genuinely
Public document would fall through to the `REVIEW` default. See §9.1.

Lifting `rule_matches` into `rules.py` is the other change to existing code. Both
engines must match conditions identically or the surfaces drift; sharing one
function makes that structural rather than conventional. Pure move, no behaviour
change, covered by existing tests.

### 3.1 Two legs

- `POST /v1/action/evaluate` — **request leg.** Gates the act. This is the only
  place a side effect can be prevented.
- `POST /v1/action/result` — **response leg.** Gates the disclosure. Runs the
  existing detectors over declared response fields.

These are not interchangeable and neither is redundant. A tool can need both:
`create_database` performs an irreversible write *and* returns a connection
string. Denying the response does not unwind the database, but it still stops a
live credential reaching the model — a separate event worth stopping.

**Therefore: any tool whose response can carry sensitive content declares a
`returns` section, regardless of whether its operation is a read or a write.**
Scoping `returns` to read operations would reopen precisely the blind spot it
exists to close.

`/v1/retrieval/evaluate` is unchanged and still serves the plain-document case.

## 4. Tool manifest

Loaded and validated with the same strictness as the compliance map: a missing
field is a hard failure at load, never a runtime default.

```yaml
version: "0.1.0-cranl"
server:
  id: cranl
  description: "CranL hosted PaaS MCP server"
tools:
  create_database:
    operation: create
    resource_type: database
    persists_data: true
    confidence_level: verified          # read from CranL's published tool schema
    requires_legal_review: true
    parameters:
      region: { role: deployment_region, maskable: false }
      name:   { role: resource_name,     maskable: false }
    returns:
      connection_string:
        role: credential
        declared_sensitive: true
        maskable: true

  set_env_var:
    operation: update
    resource_type: configuration
    persists_data: true
    confidence_level: verified
    requires_legal_review: true
    parameters:
      key:   { role: resource_name,  maskable: false }
      value: { role: opaque_payload, maskable: true }

  get_logs:
    operation: read
    resource_type: log
    persists_data: false
    confidence_level: verified
    requires_legal_review: true
    parameters:
      app_id: { role: resource_reference, maskable: false }
    returns:
      entries:
        role: opaque_payload
        inspect_content: true
        collection: true
        maskable: true

  list_env_vars:
    operation: read
    resource_type: configuration
    persists_data: false
    confidence_level: verified
    requires_legal_review: true
    returns:
      variables:
        role: opaque_payload
        inspect_content: true
        collection: true
        maskable: true
```

### 4.1 Field semantics

| Field | Meaning |
|---|---|
| `operation` | `create` / `read` / `update` / `delete` / `execute` |
| `persists_data` | Whether the action causes data to come to rest somewhere |
| `role` (request) | `deployment_region`, `opaque_payload`, `resource_name`, `resource_reference`, `credential_reference` |
| `role` (response) | `credential`, `opaque_payload`, `resource_metadata` |
| `declared_sensitive` | The manifest asserts this field carries a secret. No detection required. |
| `inspect_content` | Run detectors over this field's value |
| `collection` | The field holds many values; inspect each independently |
| `maskable` | Whether masking preserves the field's meaning |

`role` answers how Dabt knows `region` determines residency and `value` may carry
personal data. `credential_reference` is distinct from `resource_name`: a `db_id`
is not itself sensitive, but it is the key to something that is, which lets a
rule treat *reading credentials* as privileged independent of content.

`maskable` is what makes `ALLOW_WITH_REDACTION` honest. Masking `value` preserves
the call's meaning; masking `region` produces nonsense. Where masking cannot
preserve meaning, the outcome degrades to `DENY` or `REVIEW` rather than silently
mangling the call.

A manifest entry carries `confidence_level` and `requires_legal_review` because a
manifest is a claim about someone else's software, and that deserves the same
epistemic treatment as a claim about a regulation.

> **The tool names above are illustrative and unverified.** The landscape
> research establishes that CranL exposes 16 MCP tools covering app deployment,
> database creation, environment variables, and logs. It does not enumerate their
> names or signatures. `create_database`, `set_env_var`, `get_logs`, and
> `list_env_vars` are plausible reconstructions used here to fix the manifest
> *shape*, not its contents. No entry may carry `confidence_level: verified`
> until someone has read CranL's published tool schema and transcribed it. Until
> then every entry is `needs_verification`, and by §4 an unmanifested or
> unverified tool resolves to `REVIEW` — so an inaccurate reconstruction fails
> safe. Reading the real schema and manifesting all 16 tools is the first task of
> implementation.

`requires_legal_review` is caveat metadata only. Verified against the code: it
appears in `audit.py:60,81` and `engine.py:172` for emission into evidence, and
`rule_matches()` iterates `rule.condition` exclusively. It is never a gating
condition, so its mandatory-true value cannot produce an unconditional `REVIEW`.

### 4.2 Region residency data

`deployment_region_in_kingdom` is a condition key with no source defined
elsewhere in this spec. It is derived by comparing the value of the parameter
whose `role` is `deployment_region` against a residency table in
`compliance_map.yaml`:

```yaml
residency:
  in_kingdom_regions:
    - { id: "me-central-1", provider: aws,   confidence_level: inferred, requires_legal_review: true }
    - { id: "saudiarabia",  provider: azure, confidence_level: inferred, requires_legal_review: true }
```

The table belongs in the compliance map rather than the manifest, because "this
region identifier denotes infrastructure inside the Kingdom" is a jurisdictional
claim, not a fact about CranL's API. Every entry is `inferred` at best: mapping a
provider's region code to a legal jurisdiction is an inference, and providers
have changed region semantics before.

A region identifier absent from the table is treated as **not** in the Kingdom.
That is the conservative direction — an unrecognised region triggers the
residency rule and lands on `REVIEW` rather than passing unexamined.

## 5. Request and result contract

```jsonc
POST /v1/action/evaluate
{ "server_id": "cranl", "tool": "create_database",
  "arguments": { "region": "eu-west-1", "name": "customers" },
  "agent_id": "claude-code-7f2a", "purpose": "provision storage",
  "sector": "financial", "agent_authorised": true, "timestamp": "…" }

POST /v1/action/result
{ "server_id": "cranl", "tool": "get_logs",
  "result": { "entries": ["…", "…"] }, /* same context fields */ }
```

Both return one shape:

```jsonc
{ "decision": "ALLOW_WITH_REDACTION",
  "decision_rule_id": "PDPL-ART11-3-MINIMISATION",
  "classification": "Confidential",
  "classification_evidence": { … },
  "findings":    [ { "element": "variables[3]", "type": "saudi_iban", … } ],
  "fired_rules": [ … ],
  "obligations": [ { "element": "variables[3]", "strategy": "full" } ],
  "released_arguments": { … },   // or released_result; ABSENT on DENY/REVIEW
  "rewritten": true,
  "audit": { … },
  "policy_map_version": "…", "manifest_version": "…",
  "legal_review_disclaimer_en": "…", "legal_review_disclaimer_ar": "…" }
```

Three deliberate choices:

1. `released_*` is **absent**, not empty, on `DENY` and `REVIEW` — mirroring how
   `redacted_document` never carries source text on a denial.
2. `rewritten` is explicit, so the proxy can tell the agent its call was altered.
   Without it, an agent proceeds believing it wrote a value it did not.
3. `manifest_version` sits beside `policy_map_version`. Both are versioned
   claims and an audit record must name which of each produced the decision.

## 6. Rules

New condition keys: `surface`, `operation`, `resource_type`, `persists_data`,
`deployment_region_in_kingdom`, `response_declared_credential`,
`tool_manifested`.

### 6.1 Reused without modification

`PDPL-ART6-4`, `PDPL-ART15-6`, `PDPL-ART15-5`, `PDPL-ART11-3`, `PDPL-ART23`,
`PDPL-ART24`, `NDMO-SECRET-RESTRICTED-ACCESS`, and `NDMO-TOP-SECRET-DENY` all
key on `contains_personal_data` / `contains_sensitive_data` /
`contains_sensitive_category` / `classification`, which `ActionEngine` populates
identically. An IBAN in an environment variable fires Article 11(3) minimisation
with no new rule code. This is the payoff of one engine and two surfaces.

### 6.2 New rules

| Rule ID | Decision | Confidence | Basis |
|---|---|---|---|
| `PDPL-ART29-2C-INFERRED-RESIDENCY` | `REVIEW` | `needs_verification` | Provisioning outside the Kingdom, extended from Art. 29(2)(c) transfer language. Explicitly inferred: provisioning transfers nothing yet, and Dabt cannot know whether personal data will later land there. The schema structurally forbids a `needs_verification` rule from issuing a terminal `DENY`. |
| `NCA-ECC-CREDENTIAL-DISCLOSURE` | `REVIEW` | `needs_verification` | A manifest-declared credential heading toward a model. Anchored at ECC subdomain 2-2, which the map cites only at subdomain granularity from a secondary source and therefore cannot carry a verbatim quote. |
| `ACTION-DEFAULT-ALLOW-NO-FINDING` | `ALLOW` | `verified` | See §6.3. |

Both `needs_verification` rules reach `REVIEW` by design rather than by accident,
and both convert to stronger outcomes once primary-source research lands.

### 6.3 The action ALLOW path, and surface scoping

Without an explicit ALLOW rule for actions, every action would land on `REVIEW`
by omission — including regulatorily clean ones — which would contradict §2 by
holding a clean destructive operation for human review on blast-radius grounds.

`NDMO-PUBLIC-ALLOW` cannot serve as that path. Its condition is
`classification: Public`, and an action whose arguments contain no Saudi
identifiers classifies as Public, so `delete_database(name="production")` would
be permitted *because there was no PII in the argument* — the right answer for
the wrong reason, and the wrong answer for a tool that does carry PII in a field
the detectors miss.

The fix is declarative rather than engine-level. Both engines set `surface` in
context, and the map scopes itself:

```yaml
- id: NDMO-PUBLIC-ALLOW
  condition: { classification: Public, surface: retrieval }   # one key added

- id: ACTION-DEFAULT-ALLOW-NO-FINDING
  priority: 950
  decision: ALLOW
  framework: NDMO
  citation:
    article: "Section 4.3 — Data Classification Levels"
    quote: "Data shall be classified as 'Public', if unauthorized access to or
      disclosure of such data or its content has no impact on: National Interest,
      or Organizations, or Individuals, or Environment."
    source_url: "https://sdaia.gov.sa/ndmo/Files/PoliciesEn.pdf"
  condition:
    surface: action
    tool_manifested: true
    contains_personal_data: false
    contains_sensitive_data: false
    response_declared_credential: false
  rationale_en: "No mapped rule objected. The tool is declared in a validated
    manifest, no personal or sensitive data was detected in its arguments or
    declared response, and no credential is declared. This records the absence
    of a mapped objection. It is not a determination that the action is lawful,
    safe, or authorised, and makes no claim about operational consequences such
    as data loss."
  confidence_level: verified
  requires_legal_review: true
```

`confidence_level: verified` is correct because the claim is "no mapped rule
objected," which is true by construction, not an assertion about what the law
requires. The rationale states this explicitly so the audit record cannot be read
as positive authorisation.

Putting the guard in the map rather than in engine code keeps it visible to a
reviewer reading `compliance_map.yaml`, which is where every other policy
decision in this project lives.

Adding a condition to an existing rule also invalidates its hand-built test
context. `tests/test_rule_boundaries.py` holds
`"NDMO-PUBLIC-ALLOW": {"classification": "Public"}`, which stops matching once
the rule requires `surface`. That entry must gain `"surface": "retrieval"`. The
failure is the harness working correctly, but it is a required edit rather than
a surprise.

### 6.4 Collection granularity

**Redaction applies per element. Classification aggregates across all elements.**

These are different questions with different correct answers. Classification is
what the payload *is*, and NDMO Principle 4 requires aggregated data to take the
maximum level — one health value makes the whole response `Secret`. Redaction is
what must be removed, and only elements carrying findings need masking.

So nine clean environment variables return intact, the tenth returns masked, and
the decision is `ALLOW_WITH_REDACTION`. If aggregation reaches a level whose rule
denies, the entire response is withheld: aggregate decision, per-element masking
beneath it.

## 7. Failure mode

**The gate fails closed.** If `ActionEngine` raises, the manifest fails to load,
or the proxy cannot reach the service, the outcome is `DENY` with a bilingual
service-error reason — never a pass-through.

This follows from the product thesis. A gate that fails open is defeated by
making it unavailable, which reduces "an agent cannot act contrary to policy" to
"an agent cannot act contrary to policy while the gate happens to be up."

This is deliberately a different outcome from an unmanifested tool, which
resolves to `REVIEW`. The distinction is between a *known* state Dabt can
describe — this tool is not declared, a human should decide — and a *failure* in
which Dabt cannot describe anything at all. Only the second is a denial, because
only the second leaves the gate unable to say why.

The operational cost is real and stated plainly: if Dabt is down, CranL tool
calls through the proxy stop. That is the correct trade for an enforcement point
and the wrong trade for an observability tool, and Dabt is the former.

**Prerequisite, not a parallel improvement.** Fail-closed makes Dabt a hard
dependency for every gated agent action, and the reference implementation still
spawns the policy service with a hardcoded `python3`, no restart, no backoff
after a crash, and no rate limiting. Shipping fail-closed as a guarantee to a
partner before that is fixed means the partner's entire agent surface freezes on
Dabt's first crash. Hardening the subprocess lifecycle is therefore a
precondition for pitching fail-closed as a feature. "Yes, and here is how we
prevent that" needs a real answer before the conversation, not an honest
acknowledgement during it.

## 8. Reference proxy

Roughly 150 lines. Deliberately a demonstration harness, not a product-grade
gateway — production deployments use TrueFoundry, Permit.io, ContextForge, or
Microsoft AGT and call the same API.

Flow: intercept `tools/call` → `POST /v1/action/evaluate` → on `DENY`/`REVIEW`
return an MCP error carrying the cited reason, never executing → on
`ALLOW`/`ALLOW_WITH_REDACTION` forward the (possibly rewritten) call to CranL →
`POST /v1/action/result` with the response → return the (possibly redacted)
result, annotated when `rewritten` is true.

The demonstration it enables: ask Claude Code to fetch database credentials from
CranL and watch the secret stop at the boundary with a cited reason, in Arabic
and English.

## 9. Testing

### 9.1 Regression proof for the `surface` change

The end-to-end proof already exists and needs no new test:
`tests/test_decisions.py::test_public_document_allows` runs a real document
through the real engine and asserts `decision_rule_id == "NDMO-PUBLIC-ALLOW"`.
It fails immediately if `engine.py` omits the `surface` injection. It must pass
unchanged after the change — that is the before/after proof that retrieval
behaviour did not shift.

Two edits to existing tests are required, not optional:

1. `_MATCHING_CONTEXTS["NDMO-PUBLIC-ALLOW"]` gains `"surface": "retrieval"`.
2. Entries are added for `PDPL-ART29-2C-INFERRED-RESIDENCY`,
   `NCA-ECC-CREDENTIAL-DISCLOSURE`, and `ACTION-DEFAULT-ALLOW-NO-FINDING`.

**And a gap in the existing harness must be closed.** Both boundary tests
parametrize over `_MATCHING_CONTEXTS`, not over the compliance map. A rule added
to the map with no dictionary entry is silently untested and the suite stays
green. Add `test_every_map_rule_has_boundary_coverage`, asserting every rule id
in the loaded map appears in `_MATCHING_CONTEXTS`, so the completeness gate the
project claims in its design spec §8 is actually enforced.

### 9.2 New tests

Following the existing discipline: every rule gets a firing test and a
non-firing boundary test; every behavioural claim in this spec gets a named
test.

| Test | Proves |
|---|---|
| `test_manifested_action_with_no_findings_allows` | §2 and §6.3 — a clean `delete_database` reaches `ALLOW`, not `REVIEW` by omission |
| `test_public_retrieval_allow_does_not_fire_on_actions` | §6.3 — the `surface` guard holds |
| `test_unmanifested_tool_reviews` | §4 — an undeclared tool is never `ALLOW` |
| `test_undeclared_response_field_reviews` | §10 — undeclared response content is never `ALLOW` |
| `test_write_tool_response_disclosure_is_gated` | §3.1 — the write completes, the credential is still withheld |
| `test_collection_redacts_only_flagged_elements` | §6.4 — nine clean values survive |
| `test_collection_classification_aggregates_to_maximum` | §6.4 — Principle 4 across elements |
| `test_collection_deny_withholds_every_element` | §6.4 — aggregate denial |
| `test_denied_action_releases_no_arguments` | §5 — `released_*` absent, not empty |
| `test_rewritten_flag_set_when_arguments_altered` | §5 — no silent divergence |
| `test_residency_rule_cannot_terminally_deny` | §6.2 — `needs_verification` degrades |
| `test_engine_fails_closed_on_manifest_error` | §7 |
| `test_action_evaluation_is_deterministic` | Parity with the retrieval determinism guarantee |
| `test_rule_matches_shared_by_both_engines` | §3 — no drift between surfaces |

## 10. Known limitations

Stated in the manner of `needs_verification` mappings — explicit, not implicit.

1. **No generic credential detection.** Only manifest-declared credentials are
   caught. A secret in an undeclared field — a password a customer logged into
   their own application output — is caught only insofar as the PII detectors
   reach it, which for an opaque secret is not at all. A credential detector is a
   separate research track requiring NCA ECC 2-2 and 2-8 grounding, entropy
   heuristics, and false-positive tuning. Deliberately deferred.
2. **Undeclared response fields are not inspected**, and resolve to `REVIEW`.
3. **The residency rule has no verified primary-source anchor.** Marked
   `needs_verification` pending research into NCA CCC and any CST cloud
   framework.
4. **Manifest accuracy is asserted, not verified.** Dabt believes what
   `cranl.yaml` says a tool does. If CranL changes a tool's behaviour without a
   manifest update, the gate reasons from a stale model. `manifest_version` in
   every audit record makes that auditable after the fact, not preventable.
5. **Arabic tashkeel is not normalised** in the sensitive-data detector,
   inherited from the retrieval surface.

## 11. Out of scope

Agent identity issuance or verification. Production-grade MCP gateway plumbing.
Operational blast-radius control. Any framework beyond PDPL, NDMO, NCA ECC, and
SAMA CSF. Legal advice or certification of any kind.
