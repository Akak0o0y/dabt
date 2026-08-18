# Dabt — Design Specification

**Working name:** Dabt (ضبط — "control"). Placeholder, not final branding.
**Version:** 1.0
**Date:** 17 August 2026
**Author:** Manus AI
**Status:** Awaiting review

> **Legal caveat, applies to this entire document.** Every regulatory mapping described here is an *engineering artifact*, not legal advice. Each carries `requires_legal_review: true` without exception. No mapping in this system may be relied upon in a regulatory audit until a qualified Saudi legal or compliance professional has signed it off. Dabt's own output states this on every decision it emits.

## 1. What is being built

Dabt is a **regulatory policy enforcement layer**: a Policy Enforcement Point (PEP) that answers one question synchronously, at the moment of action — *does Saudi regulation permit this specific operation, on this specific data, by this specific agent, right now?*

This specification covers the **core policy engine**, the **compliance map**, and the **Data Retrieval Gate** as the working reference surface, plus a **deployed demonstration interface**. The Agent Action Gate is designed for but not implemented in this phase, per the roadmap's recommendation to validate one surface first.

What Dabt is **not**: it does not issue agent identities, does not build a search or RAG engine, does not provide legal advisory services, and does not replace any layer of existing infrastructure. It is inline enforcement on top of whatever the customer already runs.

## 2. The strategic reframing this spec adopts

The v3.0 product documentation argues Dabt's value as *Saudi-specific regulatory content delivered in real time*. Research into the primary sources supports a considerably stronger argument, and this spec adopts it as the product's central claim.

**Redaction before transfer is not a hardening measure. It is the compliance mechanism itself.**

Three provisions of the Personal Data Protection Law establish this, quoted verbatim from SDAIA's official English text [1]:

> **Article 1(5) — Processing:** "Any operation carried out on Personal Data by any means, whether manual or automated, including collecting, recording, saving, indexing, organizing, formatting, storing, modifying, updating, consolidating, **retrieving**, using, disclosing, transmitting, publishing, sharing, linking, blocking, erasing and destroying data."

Retrieval is enumerated as Processing. Every RAG lookup touching personal data is therefore a regulated Processing event, not a neutral database read. This is the statutory basis for the Data Retrieval Gate existing at all.

> **Article 6(4):** "If the Processing is necessary for the purpose of legitimate interest of the Controller, without prejudice to the rights and interests of the Data Subject, **and provided that no Sensitive Data is to be processed**."

> **Article 15(6):** "The Disclosure is necessary to achieve legitimate interests of the Controller, without prejudice to the rights and interests of the Data Subject, **and provided that no Sensitive Data is to be processed**."

The proviso is absolute. Legitimate interest can never lawfully cover Sensitive Data, which Article 1(11) defines as data revealing racial or ethnic origin, religious, intellectual or political belief, security criminal convictions and offences, biometric or genetic data used for identification, health data, or data indicating that one or both of an individual's parents are unknown. This yields a hard deny rule that can be implemented exactly rather than approximated.

> **Article 29(2)(c):** "The Transfer or Disclosure shall be **limited to the minimum amount of Personal Data needed**."

Article 29 governs transfer of personal data outside the Kingdom. A call to a foreign-hosted large language model is such a transfer. Condition (c) therefore imposes a minimisation duty on every prompt sent to OpenAI, Anthropic, Google, or any non-resident inference endpoint. Combined with Article 11(3) ("limited to the minimum amount necessary") and Article 15(5), which permits disclosure where processing occurs "in a form that makes it impossible to directly or indirectly identify the Data Subject," the law does not merely tolerate redaction — it points at redaction as the compliant path.

The commercial consequence: **any organisation in the Kingdom using a foreign-hosted LLM over internal data has an Article 29 exposure today**, and the mechanism that closes it is exactly what Dabt does. This is a broader and more urgent market than "mid-market companies wanting Gulf compliance content," and it should lead the pitch.

## 3. Corrections to the v3.0 documentation, now binding

| v3.0 said | Correct position | Consequence |
|---|---|---|
| "SAMA CSCC" | **SAMA CSF** (Cyber Security Framework), Circular 381000091275, 24/5/2017G, in force [2]. **NCA CSCC** (Critical Systems Cybersecurity Controls) is a *separate* NCA framework | Two regulators, two frameworks. SAMA CSF is the primary financial-sector framework; NCA CSCC is optional, layered for critical-systems scope |
| NCA ECC (edition unstated, structure implies ECC-1:2018) | **ECC-2:2024** superseded ECC-1:2018 in October 2024. 4 domains, 28 subdomains, 108 main controls, 92 sub-controls [3] | All ECC mappings use 2024 numbering |
| NDMO levels "1-4" | **Top Secret / Secret / Confidential / Public**, per SDAIA's official policy [4] | "Restricted" accepted as an input synonym for Confidential; "Confidential" is canonical |

## 4. Regulatory foundation

### 4.1 NDMO data classification

SDAIA's National Data Governance Interim Regulations define four levels by impact severity [4]:

| Level | Code | Impact | Trigger |
|---|---|---|---|
| Top Secret | TS | High | Unauthorised disclosure "adversely and exceptionally affects in a way that is difficult to resolve" national interest, KSA organisational functionality, individual health and safety at massive scale, or causes catastrophic environmental damage |
| Secret | S | Medium | Adversely affects national interest, causes financial loss leading to bankruptcy, causes significant harm to individual life, or long-term environmental damage |
| Confidential | C | Low | Contained negative effect on entity operations or the economy, damage to entity assets with limited loss, negative effect on individuals' interests |
| Public | P | None | No impact on national interest, organisations, individuals, or environment |

Confidential subdivides by breadth of impact: **Category (A)** at sector or general-economic-activity scale, **Category (B)** across multiple entities or a group of individuals, **Category (C)** for a single entity or a specific individual.

Critically, the official text places personally identifiable information squarely at Confidential, listing among its examples "Personally Identifiable Information (PII) such as name, address, social security numbers, phone numbers, and account numbers, license numbers, biometric identifiers," alongside individual medical files, detailed individual transaction statements, and employee salary information. This is the anchor mapping for the Data Retrieval Gate.

Two of NDMO's seven classification principles are directly implementable rather than advisory:

> **Principle 4 — Highest Level of Protection:** "If information includes an integrated set of data with different classification levels, the highest classification level should be applied to the aggregated data."

This becomes the engine's aggregation rule: a document's classification is the maximum of its constituent findings, never an average.

> **Principle 1 — Open by Default:** open by default in development sectors unless nature or sensitivity requires higher; **Top Secret by default in the political and security sectors** unless nature or sensitivity requires lower.

This becomes a configurable sector default rather than a hardcoded one — the correct default inverts depending on the customer's sector.

Principles 6 (Need to Know) and 7 (Least Privilege) justify the engine's deny-by-default posture on unclassified data.

### 4.2 NCA ECC-2:2024

Four domains, hierarchical `Domain-Subdomain-Control` identifiers such as `2-7-1`, with sub-controls extending a further level [3]. Domain 1 covers Cybersecurity Governance across 10 subdomains, Domain 2 Cybersecurity Defense across 15, Domain 3 Cybersecurity Resilience in a single subdomain, and Domain 4 Third-Party and Cloud Computing Cybersecurity across 2. The subdomains relevant to Dabt are `2-2` Identity and Access Management, `2-7` Data and Information Protection, `2-12` Cybersecurity Event Logs and Monitoring Management, `2-13` Cybersecurity Incident and Threat Management, and `4-2` Cloud Computing and Hosting Cybersecurity.

An important integrity constraint: secondary sources give **inconsistent per-subdomain control counts** — one widely cited listing sums its own Domain 1 subdomain counts to 50 against a stated total of 35. Domain and subdomain identifiers and titles are consistent across sources and are treated as `verified`. **Individual leaf control identifiers below the subdomain level are marked `needs_verification` and must be reconciled against the official NCA PDF before customer reliance.** The engine maps to subdomain granularity where the leaf is unverified, and says so.

### 4.3 SAMA CSF

Four domains — Cyber Security Leadership and Governance, Cyber Security Risk Management and Compliance, Cyber Security Operations and Technology, and Third Party Cyber Security — each subdivided into subdomains stating a principle, an objective, and control considerations, numbered as `3.X.Y` with considerations beneath [2].

Two facts shape Dabt's go-to-market. First, the framework's scope of application explicitly names the **Regulatory Sandbox** alongside the banking sector, finance sector, payment service providers, and credit bureaus — meaning Dabt's stated primary customers are directly bound. Second, the maturity model runs 0 (Non-existent) to 5 (Adaptive), and member organisations "should at least operate at maturity level 3 or higher," where level 3 requires that "the implementation of cyber security controls can be demonstrated," while level 5 expects controls "supported with automated real-time monitoring."

Dabt's decision log is therefore **evidence toward SAMA maturity level 3, and its inline automation is a level 5 characteristic**. Every policy rule carries a `sama_maturity_contribution` field. This converts a compliance cost into a measurable maturity gain, which is a materially better sales argument than risk avoidance.

### 4.4 Saudi identifiers

| Identifier | Format | Validation | Confidence |
|---|---|---|---|
| Saudi National ID | 10 digits, leading `1` | Luhn-style mod-10 over first 9 digits | Format `verified` (named in PDPL Art. 1(4) and NDMO definitions); checksum algorithm `needs_verification` — no primary government specification located |
| Iqama (residency) | 10 digits, leading `2` | As above | As above |
| Saudi IBAN | `SA` + 2 check digits + 2-digit bank code + 18-character account, 24 total | ISO 13616 MOD-97-10 | `verified` |
| Saudi mobile | `05XXXXXXXX` or `+9665XXXXXXXX` | Format only | `verified` |
| Commercial Registration | 10 digits, region-prefixed (`1010` Riyadh, `4030` Jeddah, `2050` Dammam) | Prefix heuristic | `inferred` |

A deliberate design decision governs checksums: **a failed checksum lowers confidence but never suppresses a finding.** In a compliance gate a false negative leaks regulated data while a false positive merely over-redacts. The asymmetry is not close, and the engine is tuned accordingly.

This is also where the competitive claim becomes testable. Global data-loss-prevention tooling ships detectors for US Social Security numbers, EU passports, and UK NHS numbers; Saudi National ID and Iqama numbers, Saudi IBAN bank-code semantics, and Commercial Registration numbers are absent or low-confidence in default rule sets. That gap is demonstrable in a side-by-side test, which is precisely the wedge the go-to-market plan calls for.

## 5. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Demo UI (React, deployed)                                   │
│  paste document → see findings, classification, redaction,    │
│  decision, bilingual audit log, confidence flags inline      │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTP/JSON
┌───────────────────────────▼──────────────────────────────────┐
│  dabt-api (FastAPI)                                          │
│  POST /v1/retrieval/evaluate                                 │
│  POST /v1/action/evaluate      (designed, stub)              │
│  GET  /v1/compliance-map                                     │
└───────────────────────────┬──────────────────────────────────┘
┌───────────────────────────▼──────────────────────────────────┐
│  dabt-core  (pure Python, no I/O, the handoff artifact)      │
│                                                              │
│   detectors/ ──> findings ──> classifier ──> policy engine   │
│                                    │              │          │
│                              NDMO level      decision +      │
│                                               obligations    │
│                                    │              │          │
│                              redactor <──────────┘          │
│                                    │                         │
│                              audit log (AR + EN)             │
│                                                              │
│   compliance_map.yaml  ← the regulatory content              │
└──────────────────────────────────────────────────────────────┘
```

The engine is a **pure function**: identical input yields identical output, with no network calls, no clock dependence beyond an injected timestamp, and no hidden state. This is a requirement rather than a preference, because a compliance decision must be reproducible on demand during an audit. It also makes the engine exhaustively testable and shippable as a library to a partner.

### 5.1 The evaluation pipeline

A retrieval request carries the document text, an agent identity with declared purpose and lawful basis, a destination (in-Kingdom or cross-border, named model), and the customer's sector. Evaluation proceeds in six deterministic stages.

**Detection** runs every registered Saudi and general detector over the text, producing findings with a type, span, matched value, checksum result, and per-finding confidence.

**Classification** maps findings to NDMO levels via the compliance map, then applies Principle 4: the document level is the maximum across findings, with the sector default from Principle 1 as the floor when no finding is present.

**Policy evaluation** walks the rule set in priority order. Rules are ordered so that hard statutory prohibitions are evaluated before conditional permissions, and the first terminal rule wins. Every rule that fires is recorded, including those that did not determine the outcome, so the reasoning is auditable rather than a bare verdict.

**Obligation resolution** collects what must happen for a permitted-with-conditions outcome, chiefly which spans to redact and at what strength.

**Redaction** applies obligations to produce the transformed payload, preserving document structure and offsets so the caller can reconcile.

**Audit logging** emits a decision record in Arabic and English simultaneously, with mapped control identifiers, the rules that fired, the confidence level of each, and the legal-review flag.

### 5.2 Decision model

Four outcomes, not two. A binary allow/deny cannot express the law's actual structure, since Articles 15(5) and 29(2)(c) describe a middle path where processing becomes lawful precisely *because* it has been minimised.

| Decision | Meaning |
|---|---|
| `ALLOW` | Permitted as requested; no obligations |
| `ALLOW_WITH_REDACTION` | Permitted only in transformed form; obligations attached. The Article 15(5) and 29(2)(c) path |
| `DENY` | Prohibited; no transformation makes it lawful under the declared basis |
| `REVIEW` | The engine cannot decide with sufficient confidence; escalate to a human. Emitted when the governing rule is `needs_verification` or inputs are incomplete |

`REVIEW` exists because a compliance engine that silently guesses is worse than one that admits uncertainty. A rule whose confidence is `needs_verification` cannot produce a terminal `DENY` on its own authority — it produces `REVIEW` and names what needs verifying.

### 5.3 Compliance map schema

Every entry carries provenance, confidence, and the legal-review flag. No exceptions, enforced by schema validation at load time.

```yaml
rules:
  - id: PDPL-ART6-4-SENSITIVE-LEGITIMATE-INTEREST
    priority: 100
    decision: DENY
    framework: PDPL
    citation:
      article: "Article 6(4)"
      quote: "If the Processing is necessary for the purpose of legitimate
        interest of the Controller, without prejudice to the rights and
        interests of the Data Subject, and provided that no Sensitive Data
        is to be processed."
      source_url: "https://sdaia.gov.sa/en/SDAIA/about/Documents/Personal%20Data%20English%20V2-23April2023-%20Reviewed-.pdf"
    condition:
      lawful_basis: legitimate_interest
      contains_sensitive_data: true
    rationale_en: "Legitimate interest cannot lawfully cover Sensitive Data..."
    rationale_ar: "لا يمكن للمصلحة المشروعة أن تغطي البيانات الحساسة..."
    mapped_controls:
      - framework: NCA_ECC_2_2024
        control_id: "2-7"
        confidence_level: verified
      - framework: SAMA_CSF
        control_id: "3.3.x"
        confidence_level: needs_verification
    sama_maturity_contribution: 3
    confidence_level: verified
    requires_legal_review: true
```

The distinction between a rule's own `confidence_level` and that of each mapped control matters: the PDPL prohibition itself is verified from primary text, while its mapping onto a particular SAMA control consideration is an inference. Conflating them would overstate what is known.

## 6. Scope

**In scope for this phase:** the core engine with Saudi detectors, NDMO classification with the aggregation rule, the PDPL rule set anchored in verified article text, a research-grounded compliance map with mandatory confidence and legal-review fields, bilingual audit logging, a FastAPI service, a deployed demonstration interface surfacing confidence inline, and a test suite covering every rule and detector.

**Designed but not implemented:** the Agent Action Gate. Its interface is defined and the engine is surface-agnostic, so adding it is additive work rather than restructuring.

**Explicitly out of scope:** identity issuance, RAG or search implementation, legal advisory services, production connectors to Glean or Microsoft 365 Copilot, and persistent storage — the demo holds no customer data.

## 7. Global constraints

Python 3.11 for the engine, no network calls anywhere in `dabt-core`, engine determinism enforced by test, every compliance map entry validated for `confidence_level` and `requires_legal_review` at load time with a hard failure on absence, Arabic and English rationale required on every rule, verbatim citation quotes only with no paraphrase in the `quote` field, and `needs_verification` rules structurally unable to produce a terminal deny. Arabic text in the interface renders right-to-left with correct typography. No mapping is presented as authoritative anywhere in the user interface or the API response.

## 8. Verification

The build is complete when the full test suite passes, every rule in the map has a test asserting both its firing condition and its non-firing boundary, every detector has positive and negative cases including checksum-failure behaviour, the engine's determinism is asserted, schema validation is proven to reject an entry missing either mandatory field, the deployed demo classifies a document end-to-end with visible confidence flags, and the Arabic output is verified as correct rather than merely present.

## 9. Risks

Mapping accuracy is a legal liability rather than an engineering defect, which is why confidence flags and the review outcome are structural rather than cosmetic. Leaf-level ECC control identifiers remain unreconciled against the official PDF and are marked accordingly. The National ID checksum algorithm lacks a located primary specification, so it is used only as a confidence signal. Detector recall on adversarial or obfuscated input is inherently imperfect and the demo should not imply exhaustiveness. And the durable moat is accumulated legal validation, sandbox standing, and mapping accuracy — not the adapter code, which any competent team could rebuild.

## References

[1] [Personal Data Protection Law, English text V2, 23 April 2023](https://sdaia.gov.sa/en/SDAIA/about/Documents/Personal%20Data%20English%20V2-23April2023-%20Reviewed-.pdf) — SDAIA
[2] [Cyber Security Framework, Circular 381000091275](https://rulebook.sama.gov.sa/en/cyber-security-framework-2) — Saudi Central Bank Rulebook
[3] [Essential Cybersecurity Controls (ECC-2:2024)](https://nca.gov.sa/en/regulatory-documents/controls-list/ecc/) — National Cybersecurity Authority
[4] [National Data Governance Interim Regulations](https://sdaia.gov.sa/ndmo/Files/PoliciesEn.pdf) — National Data Management Office, SDAIA
