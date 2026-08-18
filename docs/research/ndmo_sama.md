# NDMO Data Classification + SAMA CSF Research Notes

## NDMO — National Data Governance Interim Regulations
- Official PDF: https://sdaia.gov.sa/ndmo/Files/PoliciesEn.pdf
- Standards PDF: https://sdaia.gov.sa/ndmo/Files/PoliciesEn001.pdf
- Version 1, June 1st 2020. Issued by NDMO under SDAIA.
- Covers: Data Classification, Personal Data Protection, Data Sharing, Freedom of Information, Open Data

### The FOUR classification levels (§4.3) — VERIFIED from official PDF
| Level | Code | Impact Level | Trigger definition (paraphrased from official text) |
|---|---|---|---|
| Top Secret | TS | High | Unauthorized access/disclosure "adversely and exceptionally affects in a way that is difficult to resolve" national interest, KSA organizations' functionality, individuals' health/safety at massive scale, privacy of Protected Individual personnel, or catastrophic environmental damage |
| Secret | S | Medium | Adversely affects national interest, financial loss leading to bankruptcy/inability to perform duties, significant harm to life of individuals, long-term environmental damage |
| Confidential | C | Low | Contained negative effect on government entity operations/KSA economy, damage to entity assets with limited financial loss, negative effect on individuals' interests, contained short-term environmental damage |
| Public | P | None | No impact on national interest, organizations, individuals, or environment |

IMPORTANT: Some secondary sources (Saudipedia, some universities) say the four levels are "Top Secret, Secret, **Restricted**, Public". The **official NDMO PDF says "Confidential"**, not "Restricted". Use Confidential; note the discrepancy.

### Confidential sub-categories (VERIFIED)
- **Confidential – Category (A)**: impact at the scale of a sector or across a general economic activity
- **Confidential – Category (B)**: impact cuts across activities of multiple entities or interests of a group of individuals
- **Confidential – Category (C)**: impact relates to activity of a single entity or interest of a specific individual

### PII is explicitly Confidential (VERIFIED — key finding for Dabt)
Under the CONFIDENTIAL examples list, the official text includes verbatim:
> "Personally Identifiable Information (PII) such as name, address, social security numbers, phone numbers, and account numbers, license numbers, biometric identifiers"
> "Information on an individual's medical file"
> "Detailed statements of individual transactions"
> "Employees' salary information"

This is the single most important mapping for the Data Retrieval Gate: **PII → Confidential (C) → Low impact**. And per Principle 4, aggregation raises the level.

### Personal Data definition (§2 Definitions) — VERIFIED verbatim
> "**Personal Data:** Is any element of data, regardless of source or form whatsoever, which independently or when combined with other available information could lead to the identification of a person including but not limited to: First Name and Last Name, **Saudi National Identity ID Number**, addresses, Phone Number, bank account number, credit card number, health data, images or videos of the person."

The Saudi National Identity ID Number is named explicitly in the official definition. This directly justifies Dabt's Saudi-specific detectors.

### The 7 Classification Key Principles (§4.2) — VERIFIED
1. **Open by Default** — open by default in development sectors unless nature/sensitivity requires higher; Top Secret by default in political and security sectors unless it requires lower
2. **Classification Based on Necessity** — level based on potential adverse impact of unauthorized disclosure
3. **Timely Classification** — classify upon creation or upon receipt from another entity; time-bound
4. **Highest Level of Protection** — "If information includes an integrated set of data with different classification levels, the highest classification level should be applied to the aggregated data"
5. **Segregation of Duties** — classify / approve / authorize / access / protect / dispose must not overlap
6. **Need to Know** — access only with legitimate requirement, least number of people
7. **Least Privilege** — minimal access required

**Principle 4 is directly implementable** as the aggregation rule in the policy engine. **Principle 1 gives the default.** **Principles 6 & 7 justify the deny-by-default posture.**

### Impact→Level mapping in the classification process (§4.5, Step 3) — VERIFIED
- High Impact → "Top Secret"
- Medium Impact → "Secret"
- Low Impact → further assessments (Steps 4 and 5)
- None → "Public"

### Classification Controls (§4.4) — control categories
Protective Marking, Access, Usage, Storage, Data Sharing, Retention, Disposal.
Notable verified specifics:
- "Top Secret", "Secret" and "Confidential" data shall not be left unattended
- Archived "Top Secret" and "Secret" data shall be protected using NCA (National Cybersecurity Authority) standards → **explicit NDMO→NCA cross-reference**
- "Top Secret", "Secret" electronically controlled data shall be disposed using electronic media disposal

---

## SAMA Cyber Security Framework (CSF)
- Official source: https://rulebook.sama.gov.sa/en/cyber-security-framework-2
- Structure page: https://rulebook.sama.gov.sa/en/21-structure-3
- Circular No. **381000091275**, dated **28/8/1438H = 24/5/2017G**. Status: **In-Force**.
- Scope of application (verbatim): "Banking Sector—Finance Sector—Payment Systems and Payment Services Providers—Credit Bureaus—**Regulatory Sandbox**"

**CRITICAL for Dabt's GTM:** the Regulatory Sandbox is explicitly named in the CSF scope. SAMA-sandbox fintechs (Dabt's stated primary customer) are directly bound by the CSF.

### NAMING CORRECTION for the user's doc
The user's v3.0 doc says "**SAMA CSCC**". That is inaccurate:
- **SAMA** issues the **CSF** (Cyber Security Framework), 2017, 4 domains.
- **CSCC** = **Critical Systems Cybersecurity Controls**, which is an **NCA** framework, not SAMA's.
Must flag this. Dabt should reference `SAMA CSF` and, if critical-systems coverage is wanted, `NCA CSCC` as a separate framework.

### The 4 CSF domains — VERIFIED verbatim
1. Cyber Security Leadership and Governance
2. Cyber Security Risk Management and Compliance
3. Cyber Security Operations and Technology
4. Third Party Cyber Security

### Structure
- Domain → subdomain → {principle, objective, control considerations}
- Control considerations uniquely numbered, "can consist of up to 4 levels"
- Numbering observed in text: subdomains referenced as `3.1.1`, `3.1.2`, `3.2.3`, `3.3.12`, `3.3.13` — i.e. chapter 3 = Control Domains, so `3.X.Y` where X = domain, Y = subdomain. Control considerations then numbered beneath.
- Example verified: **3.1.1 Cyber Security Governance** — Principle: "A cyber security governance structure should be defined and implemented, and should be endorsed by the board." Objective: "To direct and control the overall approach to cyber security within the Member Organization."

### Applicability (§1.4) — VERIFIED
All Banks, all Insurance/Reinsurance, all Financing Companies, all Credit Bureaus, the Financial Market Infrastructure operating in Saudi Arabia.
Exceptions for non-banking FIs: subdomain 3.1.2 alignment mandatory when applicable; exclude 3.2.3 (unless cardholder data/SWIFT → then PCI DSS and/or SWIFT CSCF); exclude 3.3.12; exclude 3.3.13 (but MFA required if online customer services).

### Maturity Model (§2.4) — VERIFIED, 6 levels 0-5
| Level | Name |
|---|---|
| 0 | Non-existent |
| 1 | Ad-hoc |
| 2 | Repeatable but informal |
| 3 | Structured and formalized |
| 4 | Managed and measurable |
| 5 | Adaptive |

Member Organizations "should at least operate at maturity level 3 or higher". Banks have additional level-4 requirements per circular No (29814/67) dated 15/05/1440H.

**Directly usable in Dabt:** each policy rule can carry a `sama_maturity_target` of 3, and the enforcement log is itself evidence toward level 3 ("implementation of cyber security controls can be demonstrated") and level 5 ("supported with automated real-time monitoring"). That is a strong, verifiable sales argument.

### Framework basis
"based on the SAMA requirements and industry cyber security standards, such as NIST, ISF, ISO, BASEL and PCI"
