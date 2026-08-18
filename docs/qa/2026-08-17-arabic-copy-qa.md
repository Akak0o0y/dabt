# Dabt Arabic Copy QA Review

**Review date:** 17 August 2026  
**Scope:** All user-facing Arabic strings in the Dabt demo and its FastAPI response contract.  
**Register:** Reference implementation only; this review checks linguistic quality, not legal correctness of any regulatory mapping.

## Review outcome

The Arabic interface copy has been reviewed for **Modern Standard Arabic (MSA) grammar, natural phrasing, terminology consistency, and right-to-left presentation**. The product name **ضبط** is retained as the Arabic rendering of Dabt. Regulatory framework identifiers, article IDs, and decision codes remain in their canonical Latin form where appropriate to preserve audit traceability.

| Surface | Reviewed phrasing | QA outcome |
|---|---|---|
| Decision states | `مسموح` / `مسموح بعد الحجب` / `مرفوض` / `مراجعة مطلوبة` | Natural and concise. `الحجب` accurately conveys redaction/masking in this context. |
| Legal caveat | `يتطلب هذا المخرج الهندسي مراجعة قانونية أو مراجعة امتثال مؤهلة في المملكة العربية السعودية قبل الاعتماد التنظيمي.` | Revised to use the complete phrase **مراجعة امتثال** rather than the incomplete noun **امتثال**. |
| Audit summary | `قيّمت منصة ضبط طلب الاسترجاع بالنتيجة…` | Revised to name the platform explicitly and to use a natural Arabic verb construction. |
| Rule rationales | Arabic rationales in `compliance_map.yaml` | Reviewed as plain-language explanations, with no claim that the mapping is legally authoritative. |
| API responses | Validation, not-implemented, and unexpected-error messages | Reviewed for grammatical, direct MSA. The Action Gate response was changed to the more natural passive construction `صُمِّمت … لكنها غير مطبقة`. |
| RTL rendering | Audit rationale and legal-caveat blocks use `lang="ar" dir="rtl"` and IBM Plex Sans Arabic | Confirmed in the live browser output. |

## Terminology decisions

| English term | Approved Arabic |
|---|---|
| Compliance | الامتثال |
| Legal review | مراجعة قانونية |
| Compliance review | مراجعة امتثال |
| Redaction | الحجب |
| Retrieval | الاسترجاع |
| Payload | حمولة |
| Sensitive Data | البيانات الحساسة |
| Personal Data | البيانات الشخصية |
| Confidence level | مستوى الثقة |

> **Note:** This language QA does not replace the mandatory qualified Saudi legal or compliance review shown in every audit record.

