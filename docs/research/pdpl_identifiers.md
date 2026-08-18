# PDPL + Saudi Identifier Formats — Research Notes

## PDPL source
- Official English PDF (SDAIA): https://sdaia.gov.sa/en/SDAIA/about/Documents/Personal%20Data%20English%20V2-23April2023-%20Reviewed-.pdf
- Version: V2, 23 April 2023 (amended). Came into force with Implementing Regulations, effective **14 September 2023**, with a one-year grace to **14 September 2024** (per Cleary/Akin Gump commentary).

## Article-level findings VERIFIED verbatim from the official PDF

### Article 1 — Definitions (the ones that matter for Dabt)
- **(4) Personal Data**: "Any data, regardless of its source or form, that may lead to identifying an individual specifically, or that may directly or indirectly make it possible to identify an individual, including name, **personal identification number**, addresses, contact numbers, **license numbers**, records, personal assets, **bank and credit card numbers**, photos and videos of an individual, and any other data of personal nature."
  → "personal identification number" covers National ID / Iqama. "bank ... numbers" covers IBAN. **Direct legal hook for Dabt's detectors.**
- **(5) Processing**: "Any operation carried out on Personal Data by any means, whether manual or automated, including collecting, recording, saving, indexing, organizing, formatting, storing, modifying, updating, consolidating, **retrieving**, using, **disclosing**, transmitting, publishing, sharing, linking, blocking, erasing and destroying data."
  → **CRITICAL**: "retrieving" is explicitly an act of Processing. A RAG retrieval is Processing under PDPL. This is the single strongest legal justification for the Data Retrieval Gate existing at all.
- **(8) Disclosure**: "Enabling any person - other than the Controller or the Processor, as the case may be - to access, collect or use personal data by any means and for any purpose."
  → Feeding personal data into a third-party LLM plausibly = Disclosure. (Mark as `inferred` — needs legal review, but the argument is strong.)
- **(11) Sensitive Data**: "Personal Data revealing racial or ethnic origin, or religious, intellectual or political belief, data relating to security criminal convictions and offenses, biometric or Genetic Data for the purpose of identifying the person, **Health Data**, and data that indicates that one or both of the individual's parents are unknown."
- **(13) Health Data**: "Any Personal Data related to an individual's health condition, whether their physical, mental or psychological conditions, or related to Health Services received by that individual."
- **(15) Credit Data**: personal data related to request for/obtaining financing, ability to obtain and repay debts, credit history.

### Article 2 — Scope
Applies to any Processing of Personal Data taking place in the Kingdom by any means, **including processing of data of individuals residing in the Kingdom by any party outside the Kingdom**. Excludes purely personal/family use.
→ Extraterritorial. A US-hosted RAG stack processing Saudi residents' data is in scope.

### Article 5 — Consent
Default: no Processing and no change of purpose without consent of the Data Subject.

### Article 6 — Consent exceptions (lawful bases)
1. Serves actual interests of Data Subject but contacting them is impossible/difficult
2. Pursuant to another law or a previous agreement to which the Data Subject is a party
3. Controller is a Public Entity and Processing required for security purposes or judicial requirements
4. **Necessary for legitimate interest of the Controller, without prejudice to rights and interests of the Data Subject, and provided that NO SENSITIVE DATA is processed**
→ **Rule for the engine**: legitimate interest can NEVER cover Sensitive Data. So any retrieval whose lawful basis is `legitimate_interest` and whose payload contains Sensitive Data (health, biometric, genetic, religious, ethnic, political, criminal) must be DENIED. This is a hard, verifiable, article-anchored rule. Art. 6(4).

### Article 10 — Collection limitation
Controller may only collect directly from the Data Subject and only process for the purposes for which collected, with 7 exceptions. Notably 10(6): "Personal Data is not to be recorded or stored in a form that makes it possible to directly or indirectly identify the Data Subject" → **anonymization/redaction as a lawful path**. 10(7) mirrors legitimate interest with the same no-Sensitive-Data proviso.

### Article 11(3) — Data minimization
"The content of the Personal Data shall be appropriate and **limited to the minimum amount necessary** to achieve the purpose of the Collection."
→ Legal hook for redaction-by-default rather than full-document return.

### Article 15 — Disclosure restrictions
Controller may not Disclose except in 6 situations, incl. 15(5): "The Disclosure will only involve subsequent Processing in a form that makes it **impossible to directly or indirectly identify the Data Subject**" and 15(6) legitimate interest with the no-Sensitive-Data proviso.
→ 15(5) is the article that makes **redaction the compliant path** for onward disclosure. Core to Surface B.

### Article 16 — Absolute disclosure prohibitions
Even under 15(1,2,5,6), must not disclose if it threatens security, harms the reputation/interests of the Kingdom, affects the Kingdom's relations with another state, prevents detection of a crime, compromises safety of an individual, violates privacy of a person other than the Data Subject, etc.
→ Maps to NDMO Top Secret / national interest. Useful as the hard-deny tier.

### Article 19 — Security measures
"The Controller shall implement all the necessary organizational, administrative and technical measures to protect Personal Data, including during the Transfer of Personal Data."
→ Dabt itself is a "technical measure" under Art. 19. Good positioning line.

### Article 20 — Breach notification
Must notify Competent Authority upon knowing of any breach, damage or illegal access; must notify Data Subject where damage/prejudice to rights.

### Article 22 — Impact assessment
Controller shall conduct an impact assessment of Processing "in relation to any product or service". → DPIA obligation; Dabt's logs feed this.

### Article 23 — Health Data extra controls
"Restricting the right to access Health Data, including medical files, to the **minimum number of employees or workers** and only to the extent necessary to provide the required Health Services."
→ Strong justification for denying agent/RAG access to health data absent explicit purpose.

### Article 24 — Credit Data extra controls
Explicit consent verification; Data Subject notified when a Disclosure request for their Credit Data is received.

### Article 29 — Cross-border transfer
May transfer outside the Kingdom for: obligation under an agreement to which the Kingdom is party; to serve the interests of the Kingdom; performance of an obligation to which the Data Subject is a party; other purposes per Regulations.
Conditions: (a) no prejudice to national security or vital interests of the Kingdom; (b) adequate level of protection outside the Kingdom, at least equivalent to the Law, per Competent Authority assessment; (c) **limited to the minimum amount of Personal Data needed**.
→ **CRITICAL for AI agents**: calling a foreign-hosted LLM API with personal data is a Transfer under Art. 29. Condition (c) again mandates minimization. This is the rule that makes Dabt necessary for anyone using OpenAI/Anthropic/Gemini from inside KSA.

### Article 30 — Oversight
Competent Authority oversees implementation, "without prejudice to ... the powers of the **Saudi Central Bank**".
→ Explicit acknowledgement that SAMA's powers sit alongside PDPL. Justifies Dabt evaluating PDPL + SAMA CSF together for financial institutions.

---

## Saudi identifier formats

### National ID / Iqama (10 digits)
- Saudi national ID begins with **1**; Iqama (resident permit) begins with **2**. 10 digits total.
- Widely implemented check-digit algorithm is a **Luhn-style mod-10** variant over the first 9 digits producing the 10th.
- Source for the leading-digit convention: StackOverflow discussion (secondary) + NDMO/PDPL naming the identifier. Leading digit rule = **verified by convention/multiple secondary sources**; the exact checksum algorithm = **needs_verification** (no primary government spec located in this pass).
- Implementation decision: detect on `^[12]\d{9}$` with word boundaries, then apply Luhn as a *confidence booster*, not as a hard gate. Never reject a match solely because checksum fails — false negatives are worse than false positives in a compliance gate.

### Saudi IBAN
- 24 characters: `SA` + 2 check digits + 2-digit bank code + 18-character account number.
- Example (from Wise): `SA0380000000608010167519`, print format `SA03 8000 0000 6080 1016 7519`.
- Validation: standard **ISO 13616 / MOD-97-10** (move first 4 chars to end, letters→numbers A=10..Z=35, mod 97 must equal 1).
- Confidence: **verified** (format + MOD-97 is an international standard).

### Others worth detecting (Saudi-specific, generic tools miss)
- **Saudi mobile**: `+9665XXXXXXXX` / `05XXXXXXXX` (9 digits after leading 0, second digit 5)
- **CR number (Commercial Registration)**: 10 digits, commonly starting `1010` (Riyadh), `2050` (Dammam), `4030` (Jeddah) — region-prefixed. Confidence: `inferred`.
- **Saudi passport**: letter + 8 digits, typically starting with a letter. Confidence: `needs_verification`.
- **Absher / MOI reference numbers**: no public spec. Skip.

## Why generic DLP misses these
Global tools (Microsoft Purview, Google DLP, AWS Macie) ship detectors for US SSN, EU passport, UK NHS etc. Saudi National ID/Iqama, Saudi IBAN bank-code semantics, and CR numbers are either absent or low-confidence in default rule sets. This is Dabt's demonstrable technical differentiator and is testable — that's the free-tool wedge from the user's GTM plan.
