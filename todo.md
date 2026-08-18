# Dabt — Project TODO

Spec: `/home/ubuntu/dabt/docs/specs/2026-08-17-dabt-design.md`
Plan: `/home/ubuntu/dabt/docs/plans/2026-08-17-dabt-implementation.md`

## Phase A — Compliance map + schema validation

- [x] `dabt_core/schema.py` defines Rule/MappedControl/ComplianceMap dataclasses with `confidence_level` and `requires_legal_review` mandatory
- [x] Schema validation runs at LOAD time and raises on any entry missing `confidence_level`
- [x] Schema validation raises on any entry missing `requires_legal_review: true`
- [x] Schema validation raises on any rule missing `rationale_ar` or `rationale_en`
- [x] Schema validation raises on any `citation.quote` that is empty
- [x] `compliance_map.yaml` contains PDPL Art. 6(4) sensitive-data deny rule with verbatim quote
- [x] `compliance_map.yaml` contains PDPL Art. 15(6) disclosure sensitive-data deny rule with verbatim quote
- [x] `compliance_map.yaml` contains PDPL Art. 15(5) redaction-permits-disclosure rule with verbatim quote
- [x] `compliance_map.yaml` contains PDPL Art. 29(2)(c) cross-border minimisation rule with verbatim quote
- [x] `compliance_map.yaml` contains PDPL Art. 23 health-data access-restriction rule
- [x] `compliance_map.yaml` contains NDMO Top Secret hard-deny rule
- [x] Every rule carries NCA ECC-2:2024 mapped controls at subdomain granularity
- [x] Every rule carries a `sama_maturity_contribution` value
- [x] No leaf-level ECC control ID is asserted as verified anywhere in the map

## Phase B — Detectors

- [x] `detectors/national_id.py` matches 10 digits with leading 1 (National ID) or 2 (Iqama)
- [x] National ID detector applies Luhn as a confidence BOOST, never as a suppressor
- [x] National ID detector emits `format_detected` vs `checksum_verified` as two distinct tiers
- [x] `detectors/iban.py` matches 24-char SA IBAN and validates MOD-97
- [x] IBAN detector emits the two confidence tiers
- [x] `detectors/mobile.py` matches `05XXXXXXXX` and `+9665XXXXXXXX`
- [x] `detectors/commercial_registration.py` matches 10 digits with known region prefixes, confidence `inferred`
- [x] `detectors/sensitive.py` flags PDPL Art. 1(11) Sensitive Data categories (health, biometric, genetic, religious, ethnic, political, criminal)
- [x] Every detector has a positive test case
- [x] Every detector has a negative test case
- [x] Every checksum-bearing detector has a checksum-failure test proving the finding SURVIVES

## Phase C — Classifier

- [x] `classifier.py` maps finding types to NDMO levels via the compliance map
- [x] Principle 4 aggregation implemented: document level = MAX across findings
- [x] Principle 1 sector default configurable, floor applied when no findings
- [x] "Restricted" accepted as an input synonym for "Confidential"
- [x] Canonical output label is always "Confidential", never "Restricted"
- [x] Test proves aggregation picks maximum, not average or first

## Phase D — Policy engine

- [x] `engine.py` runs the six stages in order: detection, classification, policy, obligations, redaction, audit
- [x] Rules evaluated in priority order, first terminal rule wins
- [x] All fired rules recorded, including non-determinative ones
- [x] Four outcomes implemented: ALLOW / ALLOW_WITH_REDACTION / DENY / REVIEW
- [x] A `needs_verification` rule CANNOT produce a terminal DENY, it degrades to REVIEW
- [x] Test proves the `needs_verification` to REVIEW degradation
- [x] Engine is a pure function: no network, no I/O, injected timestamp
- [x] Determinism test: same input twice yields byte-identical output

## Phase E — Obligations + redaction

- [x] `obligations.py` resolves redaction spans from fired rules
- [x] `redactor.py` applies spans preserving document structure and offsets
- [x] Redaction is idempotent (test)
- [x] Overlapping spans merge correctly (test)

## Phase F — Bilingual audit log

- [x] `audit.py` emits Arabic and English simultaneously in one record
- [x] Every record includes mapped control IDs with per-mapping confidence
- [x] Every record includes the legal-review disclaimer in BOTH languages
- [x] Test asserts the disclaimer is present in both languages on every record
- [x] Test asserts no record claims authoritative status

## Phase G — FastAPI service

- [x] `POST /v1/retrieval/evaluate` returns a full decision
- [x] `POST /v1/action/evaluate` returns a documented not-implemented response for the Agent Action Gate
- [x] `GET /v1/compliance-map` returns the map with confidence levels intact
- [x] Every API response carries the legal-review caveat
- [x] Service starts and is reachable from the demo

## Phase H — Demo UI (blueprint aesthetic)

- [x] tRPC proxy procedures call the Python service
- [x] Document paste area
- [x] Findings panel distinguishes format-detected from checksum-verified visually
- [x] NDMO classification badge
- [x] Redacted output view
- [x] Decision outcome display with colour coding for all four outcomes
- [x] Bilingual audit log panel with inline confidence flags
- [x] Arabic renders right-to-left with correct typography
- [x] Blueprint aesthetic: deep royal blue ground, faint precise grid, white CAD-style line work, dimension markers
- [x] Bold white sans-serif type hierarchy
- [x] No mapping presented as authoritative anywhere in the UI
- [x] Legal-review disclaimer visible in the UI

## Phase I — Verification

- [x] Every rule has a firing test AND a non-firing boundary test
- [x] Full Python suite passes
- [x] Vitest suite passes for the tRPC proxy layer
- [x] Arabic output verified as correct, not merely present
- [x] Screenshots confirm the rendered UI

## Follow-up integrity refinement

- [x] Refactor `classifier.py` to derive finding-type → NDMO level mappings from the validated `compliance_map.yaml` classification section, with tests proving map configuration affects classification behavior
- [x] Refactor `resolve_obligations` to derive redaction spans from fired-rule outputs rather than the final decision alone, with tests proving rules can produce distinct obligation strategies
- [x] Add a global FastAPI 500 handler and test proving unexpected errors include the bilingual legal-review caveat
- [x] Ensure a DENY result never exposes the original payload in the release-output field, with a regression test
- [x] Add a deploy-compatible Dockerfile that includes the Python runtime needed by the FastAPI service
- [x] Review all user-facing Arabic copy for correctness and natural phrasing, then document that QA review
- [x] Commit the verified Dabt Core v0.1 implementation and push it to the configured GitHub repository
- [x] Independently verify and provide the requested National ID detector and compliance-map source files
- [x] Add cited English and Arabic rationale to each inferred PDPL Sensitive Data → NDMO Secret classification mapping, and enforce those fields at map-load time
- [x] Render explicit BLOCKED and AWAITING HUMAN REVIEW release states in the UI without exposing the source payload
- [x] Expose the selected NDMO classification mapping’s confidence and cited rationale in the policy result and demo UI
- [x] Make classification-evidence rendering resilient to a stale API response and restart the local FastAPI process before live verification
- [x] Commit and push the completed classification-inference and protected-release hardening updates to GitHub
- [x] Add Python bytecode exclusions to `.gitignore` and remove all tracked `__pycache__` and `*.pyc` artifacts
- [x] Persist immutable audit evidence snapshots with decision, classification evidence, bilingual audit record, and policy-map version
- [x] Provide a durable evidence-register view that retrieves persisted audit snapshots through tRPC
- [x] Disable the evaluation control while an authenticated persistence mutation is pending to prevent duplicate audit snapshots
- [x] Let an owner select a persisted snapshot and replay its stored bilingual audit record and classification evidence through `evidenceGet`
- [x] Add regression coverage proving a persisted snapshot can be retrieved as a full evidence record, not only listed as metadata
- [x] Commit and push the durable evidence and Python bytecode cleanup update to GitHub
- [x] Directly verify that the evidence snapshot schema and database write path cannot retain source or release payload text
- [x] Test an authenticated persisted snapshot end to end when a signed-in session is available, and report only observed results
- [x] Add reviewer approval for REVIEW snapshots with reviewer identity, timestamp, bilingual rationale, and immutable approval evidence
- [x] Synchronize the reviewer-approval milestone to GitHub immediately after verification
- [x] Scope reviewer-decision retrieval to the snapshot owner before displaying review status in the Evidence Vault
- [x] Run the authenticated health-data retrieval and directly inspect persisted UI and tRPC fields for source/release payload absence
- [x] Exercise immutable reviewer approval on a real REVIEW snapshot and verify a second write is rejected
- [x] Build a comparison view that distinguishes inferred classification from an approved reviewer disposition without presenting either mapping as authoritative
- [x] Record an optional qualified-reviewer-approved NDMO classification with every immutable approval, while retaining the legal-review caveat
- [x] Return a tRPC CONFLICT response, rather than an internal-error response, when an immutable reviewer decision is resubmitted
- [x] Push the classification compare-view milestone as a discrete GitHub commit
- [x] Document Dabt’s plain-language purpose, implemented capabilities, explicit non-capabilities, legal caveat, and current verified framework coverage in the README
- [x] Re-run the complete test suite and production build without modifying engine or compliance-map behavior
- [x] Confirm the stable deployed demo URL reflects the final documentation checkpoint
- [x] Verify a production deploy signal that maps the stable demo URL to the final documentation checkpoint or Git commit (checkpoint `9b13792a` auto-published; production root returned HTTP 200 with `Last-Modified: Mon, 17 Aug 2026 14:50:59 GMT`)
- [ ] Add and verify a non-invasive app-visible build version signal that maps the production demo to the final Git commit
- [ ] Commit and push the final documentation-and-stability wrap-up as one discrete GitHub commit
