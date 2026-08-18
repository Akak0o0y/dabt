# NCA ECC Research Notes

## Official source
- NCA regulatory documents page (EN): https://nca.gov.sa/en/regulatory-documents/controls-list/ecc/
- Official PDF (ECC-2:2024 EN): https://cdn.nca.gov.sa/api/files/public/upload/86e09090-44e4-481f-bc28-355673607654_ECC--2024-EN.pdf
- Implementation guide PDF: https://cdn.nca.gov.sa/api/files/public/upload/94c6c5f5-4d70-4afd-a440-64369aa667e2_Guide-to-Essential-Cybersecurity-Controls-(ECC)-Implementation-en.pdf
- Arabic page: https://nca.gov.sa/ar/regulatory-documents/controls-list/ecc/

## Versions
- ECC-1:2018: 5 domains, 29 subdomains, 114 main controls
- ECC-2:2024: replaced ECC-1 in **October 2024**. 4 domains, 28 subdomains, 108 main controls, 92 sub-controls (232 nodes total)
- ICS domain (was domain 5 in ECC-1) removed → now covered by separate OTCC

## Control ID format
Hierarchical: `Domain-Subdomain-Control` e.g. `2-3-1`. Sub-controls extend: `2-2-3-1`.

## ECC-2:2024 domain/subdomain structure (from grcvantage, cross-checked with itbuilders)

### Domain 1 — Cybersecurity Governance (10 subdomains, 35 controls)
| ID | Subdomain | Controls |
|---|---|---|
| 1-1 | Cybersecurity Strategy | 3 |
| 1-2 | Cybersecurity Management | 3 |
| 1-3 | Cybersecurity Policies and Procedures | 4 |
| 1-4 | Cybersecurity Roles and Responsibilities | 2 |
| 1-5 | Cybersecurity Risk Management | 7 |
| 1-6 | Cybersecurity in Information and Technology Project Management | 9 |
| 1-7 | Compliance with Cybersecurity Standards, Laws and Regulations | 1 |
| 1-8 | Periodical Cybersecurity Review and Audit | 3 |
| 1-9 | Cybersecurity in Human Resources | 8 |
| 1-10 | Cybersecurity Awareness and Training Program | 10 |

### Domain 2 — Cybersecurity Defense (15 subdomains, 61 controls)
| ID | Subdomain | Controls |
|---|---|---|
| 2-1 | Asset Management | 6 |
| 2-2 | Identity and Access Management | 8 |
| 2-3 | Information System and Processing Facilities Protection | 7 |
| 2-4 | Email Protection | 8 |
| 2-5 | Networks Security Management | 12 |
| 2-6 | Mobile Devices Security | 7 |
| 2-7 | Data and Information Protection | 3 |
| 2-8 | Cryptography | 6 |
| 2-9 | Backup and Recovery Management | 6 |
| 2-10 | Vulnerabilities Management | 8 |
| 2-11 | Penetration Testing | 5 |
| 2-12 | Cybersecurity Event Logs and Monitoring Management | 8 |
| 2-13 | Cybersecurity Incident and Threat Management | 8 |
| 2-14 | Physical Security | 8 |
| 2-15 | Web Application Security | 8 |

### Domain 3 — Cybersecurity Resilience (1 subdomain, 4 controls)
| ID | Subdomain |
|---|---|
| 3-1 | Cybersecurity Resilience Aspects of Business Continuity Management (BCM) |

### Domain 4 — Third-Party and Cloud Computing Cybersecurity (2 subdomains, 8 controls)
| ID | Subdomain | Controls |
|---|---|---|
| 4-1 | Third-Party Cybersecurity | 7 |
| 4-2 | Cloud Computing and Hosting Cybersecurity | 5 |

## Subdomain objectives (verbatim-ish, from grcvantage listing)
- 2-2 IAM: "To ensure protecting cybersecurity of logical access to information and technology assets, in order to prevent unauthorized access and restrict access to the extent necessary for accomplishment of the assigned tasks of the entity."
- 2-7 Data and Information Protection: "To ensure confidentiality, integrity, accuracy, and availability of the entity's data and information."
- 2-8 Cryptography: "To ensure the proper and efficient use of cryptography to protect electronic information assets of the entity."
- 2-12 Event Logs & Monitoring: "To ensure timely collection, analysis, and monitoring of cybersecurity event logs for proactive detection and effective management of cyber-attacks."
- 2-13 Incident & Threat Mgmt: "To ensure timely identification, detection, and effective management of cybersecurity incidents and proactive response to cybersecurity threats."
- 4-1 Third-Party: "To ensure the protection of the entity's assets against third-party cybersecurity risks (including IT outsourcing, cybersecurity outsourcing, and managed services)."
- 4-2 Cloud: "To ensure proper and efficient remediation of cyber risks and implementation of cybersecurity requirements for cloud computing and hosting."

## Relevance to Dabt (which subdomains map to agent/data enforcement)
- **2-2 IAM** → Agent Action Gate: agent identity, least privilege, authorization of actions
- **2-7 Data and Information Protection** → Data Retrieval Gate: classification-based protection through lifecycle, DLP
- **2-8 Cryptography** → redaction/masking adjacent (not identical — cryptography ≠ redaction; mark as inferred)
- **2-12 Event Logs & Monitoring** → both gates: the decision log itself
- **2-13 Incident & Threat Mgmt** → deny events escalation
- **2-15 Web Application Security** → API surface of the gate itself
- **4-1 / 4-2 Third-Party & Cloud** → agents calling external tools / LLM APIs hosted outside KSA

## Other NCA frameworks in the ecosystem (base = ECC)
- CSCC — Critical Systems Cybersecurity Controls
- CCC — Cloud Cybersecurity Controls
- DCC — Data Cybersecurity Controls
- OTCC — Operational Technology Cybersecurity Controls
- Telework Cybersecurity Controls

NOTE: The user's doc says "SAMA CSCC" meaning SAMA's Cyber Security Framework. Careful: **CSCC is an NCA framework (Critical Systems)**, while SAMA issues the **SAMA CSF (Cyber Security Framework)**. Need to verify and flag this naming discrepancy to the user.

## Caveats
- Control *counts* per subdomain from grcvantage (secondary source) — sums: D1=35? (3+3+4+2+7+9+1+3+8+10=50 — DOES NOT match stated 35). D2 listed sums to 110 not 61. D3 says "1 subdomain, 4 controls" but the row says 6 controls. **Secondary source is internally inconsistent — per-subdomain counts are NOT reliable.** Domain/subdomain NAMES and IDs are consistent across sources and are usable. Control counts must be marked needs_verification.
