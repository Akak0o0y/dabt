# Dabt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use subagent-driven-development or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure-function Python policy engine that evaluates Saudi regulatory compliance for AI data retrieval, exposed via FastAPI and demonstrated through a bilingual React UI.

**Architecture:** `dabt-core` is a dependency-light, I/O-free Python package: detectors produce findings, a classifier assigns an NDMO level, a rule engine loaded from a validated YAML compliance map produces one of four decisions with obligations, a redactor applies those obligations, and an audit module emits a bilingual record. A thin FastAPI layer wraps it. A React demo in `/home/ubuntu/dabt-demo` calls the service through tRPC proxy procedures.

**Tech Stack:** Python 3.11, PyYAML, pytest, FastAPI, Uvicorn; React 19, Tailwind 4, tRPC 11, Vitest.

**Spec:** `/home/ubuntu/dabt/docs/specs/2026-08-17-dabt-design.md`

## Global Constraints

These apply to every task below without restatement.

- Python 3.11. `dabt_core` performs **no network calls and no file I/O outside explicit map loading**.
- The engine is a **pure function**: identical input yields byte-identical output. Timestamps are injected, never read from the clock inside the engine.
- **Every** compliance map entry carries `confidence_level` (one of `verified` / `inferred` / `needs_verification`) and `requires_legal_review: true`. Validation runs at **load time**, not evaluation time, and fails hard.
- **Every** rule carries both `rationale_ar` and `rationale_beam`… (see task A2 for exact field list) — Arabic and English are both mandatory.
- `citation.quote` contains **verbatim source text only**. Paraphrase is a defect.
- A rule whose `confidence_level` is `needs_verification` **cannot** produce a terminal `DENY`; it degrades to `REVIEW`.
- A failed checksum **lowers a finding's confidence tier but never suppresses the finding**.
- **No leaf-level NCA ECC control ID may be asserted as verified.** Map to subdomain granularity and mark `needs_verification`. Do not backfill a plausible-looking leaf ID under any circumstances, including temporarily.
- Arabic renders right-to-left with correct typography in the UI.
- **No mapping is presented as authoritative** in any UI surface or API response. The legal-review disclaimer appears in every audit record, in both languages.
- TDD throughout: write the failing test, watch it fail, write minimal code, watch it pass, commit.

---

### Task A1: Package scaffold and schema types

**Files:**
- Create: `/home/ubuntu/dabt/dabt_core/__init__.py`
- Create: `/home/ubuntu/dabt/dabt_core/schema.py`
- Create: `/home/ubuntu/dabt/tests/test_schema.py`
- Create: `/home/ubuntu/dabt/pyproject.toml`

**Steps:**
- [ ] Write `tests/test_schema.py::test_rule_requires_confidence_level` asserting a `SchemaError` when the field is absent
- [ ] Run it, confirm it fails on import (module does not exist yet)
- [ ] Write `schema.py` with frozen dataclasses: `Citation`, `MappedControl`, `Rule`, `ComplianceMap`, and enums `ConfidenceLevel`, `Decision`, `NdmoLevel`, `Framework`
- [ ] Run the test, confirm it passes
- [ ] Add `test_rule_requires_legal_review_true` — must reject both absence and `false`
- [ ] Add `test_rule_requires_both_languages`
- [ ] Add `test_citation_quote_must_be_nonempty`
- [ ] Add `test_needs_verification_rule_cannot_declare_terminal_deny` — schema-level rejection at load
- [ ] Run all, confirm green

**Verification:** `pytest tests/test_schema.py -v` all green; every mandatory-field omission produces a distinct, readable error.

---

### Task A2: Compliance map loader with load-time validation

**Files:**
- Create: `/home/ubuntu/dabt/dabt_core/loader.py`
- Create: `/home/ubuntu/dabt/tests/test_loader.py`
- Create: `/home/ubuntu/dabt/tests/fixtures/invalid_missing_confidence.yaml`
- Create: `/home/ubuntu/dabt/tests/fixtures/invalid_missing_legal_review.yaml`
- Create: `/home/ubuntu/dabt/tests/fixtures/valid_minimal.yaml`

**Rule field list (authoritative):** `id`, `priority`, `decision`, `framework`, `citation{article,quote,source_url}`, `condition`, `rationale_en`, `rationale_ar`, `mapped_controls[]{framework,control_id,granularity,confidence_level}`, `sama_maturity_contribution`, `confidence_level`, `requires_legal_review`.

**Steps:**
- [ ] Write `test_load_rejects_missing_confidence_level` against the invalid fixture
- [ ] Confirm it fails
- [ ] Implement `load_compliance_map(path)` raising `SchemaError` with the offending rule id in the message
- [ ] Confirm pass
- [ ] Add `test_load_rejects_missing_legal_review`
- [ ] Add `test_load_rejects_duplicate_rule_ids`
- [ ] Add `test_load_accepts_valid_minimal`
- [ ] Add `test_validation_happens_at_load_not_evaluation` — construct an engine and assert the raise occurred before any evaluate call
- [ ] Run all, green

**Verification:** validation provably occurs at load; error messages name the offending rule.

---

### Task A3: The compliance map content

**Files:**
- Create: `/home/ubuntu/dabt/dabt_core/data/compliance_map.yaml`
- Create: `/home/ubuntu/dabt/tests/test_compliance_map_content.py`

Each rule below uses the verbatim quote captured in the research notes. Sources: PDPL English text V2 23 April 2023, NDMO National Data Governance Interim Regulations, SAMA CSF Circular 381000091275, NCA ECC-2:2024.

**Steps:**
- [ ] Write `test_every_rule_has_verbatim_quote` and `test_every_rule_requires_legal_review` over the real map
- [ ] Confirm they fail (map absent)
- [ ] Author `PDPL-ART6-4-SENSITIVE-LEGITIMATE-INTEREST` — DENY, priority 100, `confidence_level: verified`
- [ ] Author `PDPL-ART15-6-SENSITIVE-DISCLOSURE` — DENY, priority 100, verified
- [ ] Author `PDPL-ART16-ABSOLUTE-PROHIBITION` — DENY, priority 110, verified
- [ ] Author `NDMO-TOP-SECRET-DENY` — DENY, priority 120, verified
- [ ] Author `PDPL-ART29-2C-CROSSBORDER-MINIMISATION` — ALLOW_WITH_REDACTION, priority 200, verified
- [ ] Author `PDPL-ART15-5-ANONYMISED-DISCLOSURE` — ALLOW_WITH_REDACTION, priority 210, verified
- [ ] Author `PDPL-ART11-3-MINIMISATION` — ALLOW_WITH_REDACTION, priority 220, verified
- [ ] Author `PDPL-ART23-HEALTH-DATA-RESTRICTION` — REVIEW, priority 150, verified
- [ ] Author `PDPL-ART24-CREDIT-DATA-CONSENT` — REVIEW, priority 160, `confidence_level: inferred`
- [ ] Author `NDMO-SECRET-RESTRICTED-ACCESS` — ALLOW_WITH_REDACTION, priority 230, verified
- [ ] Author `NDMO-PUBLIC-ALLOW` — ALLOW, priority 900, verified
- [ ] Attach ECC-2:2024 subdomain mappings (`2-2`, `2-7`, `2-12`, `2-13`, `4-2`) with `granularity: subdomain` and `confidence_level: needs_verification` on each leaf claim
- [ ] Attach `sama_maturity_contribution: 3` to enforcement rules, `5` to logging rules
- [ ] Run content tests, green
- [ ] Add `test_no_leaf_control_claimed_verified` asserting no mapped control with `granularity: control` carries `verified`

**Verification:** map loads clean; every rule has a verbatim quote and both languages; no leaf ECC ID claimed verified.

---

### Task B1: National ID / Iqama detector

**Files:**
- Create: `/home/ubuntu/dabt/dabt_core/detectors/__init__.py`
- Create: `/home/ubuntu/dabt/dabt_core/detectors/base.py`
- Create: `/home/ubuntu/dabt/dabt_core/detectors/national_id.py`
- Create: `/home/ubuntu/dabt/tests/test_detector_national_id.py`

**Steps:**
- [ ] Write `test_detects_national_id_leading_1` and `test_detects_iqama_leading_2`
- [ ] Confirm failing
- [ ] Implement `base.py` with the `Finding` dataclass (`type`, `start`, `end`, `value`, `confidence_tier`, `confidence_level`, `checksum_result`) and a `Detector` protocol
- [ ] Implement `national_id.py` matching `\b[12]\d{9}\b`
- [ ] Confirm pass
- [ ] Add `test_luhn_valid_yields_checksum_verified_tier`
- [ ] Add `test_luhn_invalid_still_yields_finding_at_format_detected_tier` — **the critical asymmetry test**
- [ ] Add `test_ignores_9_and_11_digit_numbers`
- [ ] Add `test_ignores_leading_3_through_9`
- [ ] Add `test_reports_correct_span_offsets`
- [ ] Run all, green

**Verification:** checksum failure demonstrably preserves the finding and only lowers the tier.

---

### Task B2: Saudi IBAN detector

**Files:**
- Create: `/home/ubuntu/dabt/dabt_core/detectors/iban.py`
- Create: `/home/ubuntu/dabt/tests/test_detector_iban.py`

**Steps:**
- [ ] Write `test_detects_valid_sa_iban` using `SA0380000000608010167519`
- [ ] Confirm failing
- [ ] Implement matcher for `SA` + 22 alphanumerics, tolerating spaces in print format
- [ ] Implement MOD-97-10 per ISO 13616
- [ ] Confirm pass
- [ ] Add `test_mod97_valid_yields_checksum_verified_tier`
- [ ] Add `test_mod97_invalid_still_yields_finding`
- [ ] Add `test_normalises_print_format_with_spaces`
- [ ] Add `test_ignores_non_sa_iban`
- [ ] Run all, green

---

### Task B3: Mobile and Commercial Registration detectors

**Files:**
- Create: `/home/ubuntu/dabt/dabt_core/detectors/mobile.py`
- Create: `/home/ubuntu/dabt/dabt_core/detectors/commercial_registration.py`
- Create: `/home/ubuntu/dabt/tests/test_detector_mobile.py`
- Create: `/home/ubuntu/dabt/tests/test_detector_cr.py`

**Steps:**
- [ ] Write mobile tests for `05XXXXXXXX` and `+9665XXXXXXXX`, plus a negative for `04...`
- [ ] Implement, confirm pass
- [ ] Write CR tests for `1010`, `4030`, `2050` prefixes and a negative for an unknown prefix
- [ ] Implement with `confidence_level: inferred` on every CR finding
- [ ] Confirm pass; assert the inferred level in the test

---

### Task B4: Sensitive-data detector (PDPL Art. 1(11))

**Files:**
- Create: `/home/ubuntu/dabt/dabt_core/detectors/sensitive.py`
- Create: `/home/ubuntu/dabt/tests/test_detector_sensitive.py`

Categories from Art. 1(11): racial or ethnic origin, religious/intellectual/political belief, security criminal convictions and offences, biometric or genetic data for identification, health data, and unknown parentage.

**Steps:**
- [ ] Write one positive test per category, Arabic and English keyword sets
- [ ] Confirm failing
- [ ] Implement keyword and pattern matching, emitting `sensitive_category` on the finding
- [ ] Confirm pass
- [ ] Add `test_bilingual_keywords_detected` covering Arabic terms
- [ ] Add a negative test for benign text
- [ ] Document explicitly in the module docstring that recall is imperfect and this is not exhaustive

---

### Task C1: NDMO classifier

**Files:**
- Create: `/home/ubuntu/dabt/dabt_core/classifier.py`
- Create: `/home/ubuntu/dabt/tests/test_classifier.py`

**Steps:**
- [ ] Write `test_pii_finding_classifies_confidential` (NDMO lists PII under Confidential)
- [ ] Confirm failing
- [ ] Implement finding-type to level mapping sourced from the compliance map
- [ ] Confirm pass
- [ ] Add `test_principle_4_aggregation_takes_maximum` with mixed Public and Confidential findings
- [ ] Add `test_principle_4_not_average_not_first` explicitly
- [ ] Add `test_sector_default_applies_when_no_findings`
- [ ] Add `test_security_sector_defaults_to_top_secret` per Principle 1
- [ ] Add `test_restricted_accepted_as_input_synonym_for_confidential`
- [ ] Add `test_canonical_output_label_is_confidential_never_restricted`
- [ ] Run all, green

---

### Task D1: Policy engine core

**Files:**
- Create: `/home/ubuntu/dabt/dabt_core/engine.py`
- Create: `/home/ubuntu/dabt/tests/test_engine.py`

**Steps:**
- [ ] Write `test_six_stages_execute_in_order` using a stage recorder
- [ ] Confirm failing
- [ ] Implement `evaluate(request, map, now)` running detection, classification, policy, obligations, redaction, audit
- [ ] Confirm pass
- [ ] Add `test_rules_evaluated_in_priority_order`
- [ ] Add `test_first_terminal_rule_wins`
- [ ] Add `test_all_fired_rules_recorded_including_non_determinative`
- [ ] Add `test_needs_verification_rule_degrades_deny_to_review` — **the integrity test**
- [ ] Add `test_determinism_same_input_byte_identical_output`
- [ ] Add `test_engine_makes_no_network_calls` (monkeypatch socket to raise)
- [ ] Run all, green

---

### Task D2: The four decision paths, end to end

**Files:**
- Create: `/home/ubuntu/dabt/tests/test_decisions.py`

**Steps:**
- [ ] `test_public_document_allows` → ALLOW
- [ ] `test_pii_crossborder_allows_with_redaction` → ALLOW_WITH_REDACTION citing Art. 29(2)(c)
- [ ] `test_sensitive_data_under_legitimate_interest_denies` → DENY citing Art. 6(4)
- [ ] `test_top_secret_denies` → DENY
- [ ] `test_health_data_reviews` → REVIEW citing Art. 23
- [ ] For each, assert the fired rule id, the cited article, and the mapped control appear in the result
- [ ] Add a non-firing boundary test for each rule authored in A3

**Verification:** every rule in the map has both a firing and a non-firing test. This is the spec's completeness gate.

---

### Task E1: Obligations and redactor

**Files:**
- Create: `/home/ubuntu/dabt/dabt_core/obligations.py`
- Create: `/home/ubuntu/dabt/dabt_core/redactor.py`
- Create: `/home/ubuntu/dabt/tests/test_redactor.py`

**Steps:**
- [ ] Write `test_redacts_span_preserving_length_and_structure`
- [ ] Confirm failing
- [ ] Implement obligation resolution from fired rules, then span application
- [ ] Confirm pass
- [ ] Add `test_redaction_is_idempotent`
- [ ] Add `test_overlapping_spans_merge`
- [ ] Add `test_offsets_remain_reconcilable_for_caller`
- [ ] Add `test_partial_masking_preserves_last_four_where_configured`

---

### Task F1: Bilingual audit log

**Files:**
- Create: `/home/ubuntu/dabt/dabt_core/audit.py`
- Create: `/home/ubuntu/dabt/tests/test_audit.py`

**Steps:**
- [ ] Write `test_record_contains_both_languages`
- [ ] Confirm failing
- [ ] Implement the record emitter
- [ ] Confirm pass
- [ ] Add `test_legal_review_disclaimer_present_in_english`
- [ ] Add `test_legal_review_disclaimer_present_in_arabic`
- [ ] Add `test_every_mapped_control_carries_its_own_confidence`
- [ ] Add `test_no_record_claims_authoritative_status` scanning for forbidden assertive phrasing
- [ ] Add `test_record_is_json_serialisable`

---

### Task G1: FastAPI service

**Files:**
- Create: `/home/ubuntu/dabt/dabt_api/main.py`
- Create: `/home/ubuntu/dabt/tests/test_api.py`

**Steps:**
- [ ] Write `test_retrieval_evaluate_returns_decision` via TestClient
- [ ] Confirm failing
- [ ] Implement `POST /v1/retrieval/evaluate`
- [ ] Confirm pass
- [ ] Implement `POST /v1/action/evaluate` returning a documented 501 describing the designed-not-implemented Agent Action Gate
- [ ] Implement `GET /v1/compliance-map` preserving confidence levels
- [ ] Add `test_every_response_carries_legal_caveat`
- [ ] Add `test_map_endpoint_exposes_confidence_levels`
- [ ] Add `test_invalid_request_returns_422_not_500`
- [ ] Start the service, confirm reachable

---

### Task H1: tRPC proxy layer

**Files:**
- Modify: `/home/ubuntu/dabt-demo/server/routers.ts`
- Create: `/home/ubuntu/dabt-demo/server/dabt.ts`
- Create: `/home/ubuntu/dabt-demo/server/dabt.test.ts`

**Steps:**
- [ ] Write a Vitest spec asserting the proxy forwards and shapes the response
- [ ] Implement `server/dabt.ts` calling the Python service
- [ ] Register `dabt.evaluate` and `dabt.complianceMap` procedures
- [ ] Add a test asserting the legal caveat survives the proxy
- [ ] Run `pnpm test`, green

---

### Task H2: Blueprint design system

**Files:**
- Modify: `/home/ubuntu/dabt-demo/client/src/index.css`
- Modify: `/home/ubuntu/dabt-demo/client/index.html`

**Steps:**
- [ ] Set the dark theme with a deep royal blue ground in OKLCH
- [ ] Add the faint precise grid as a CSS background layer
- [ ] Add CAD-style rule/frame utilities and dimension-marker components
- [ ] Load a bold technical sans via Google Fonts, plus an Arabic face with correct shaping
- [ ] Verify contrast on every text surface

---

### Task H3: Demo UI

**Files:**
- Create: `/home/ubuntu/dabt-demo/client/src/pages/Gate.tsx`
- Create: `/home/ubuntu/dabt-demo/client/src/components/FindingsPanel.tsx`
- Create: `/home/ubuntu/dabt-demo/client/src/components/DecisionBadge.tsx`
- Create: `/home/ubuntu/dabt-demo/client/src/components/AuditLog.tsx`
- Create: `/home/ubuntu/dabt-demo/client/src/components/ConfidenceFlag.tsx`
- Modify: `/home/ubuntu/dabt-demo/client/src/pages/Home.tsx`
- Modify: `/home/ubuntu/dabt-demo/client/src/App.tsx`

**Steps:**
- [ ] Build the paste area with worked sample documents
- [ ] Build the findings panel rendering `format_detected` and `checksum_verified` as **visually distinct tiers**
- [ ] Build the NDMO classification badge with all four levels
- [ ] Build the redacted-output view with before and after
- [ ] Build the decision badge colour-coded across all four outcomes
- [ ] Build the audit log with inline confidence flags and RTL Arabic
- [ ] Surface the legal-review disclaimer prominently, never dismissible
- [ ] Screenshot desktop and mobile, verify

---

### Task I1: Final verification

**Steps:**
- [ ] Run the full pytest suite, confirm green, record the count
- [ ] Run `pnpm test`, confirm green
- [ ] Confirm every A3 rule has firing and non-firing coverage
- [ ] Have Arabic output checked for correctness, not mere presence
- [ ] Re-read `todo.md`, mark completed items
- [ ] Screenshot the deployed demo
- [ ] Save the checkpoint
