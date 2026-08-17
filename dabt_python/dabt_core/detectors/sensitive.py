"""Conservative keyword detector for PDPL Article 1(11) Sensitive Data.

This reference rule set cannot exhaustively detect sensitive data, especially
obfuscated, contextual, or multilingual variants. A missing finding is never a
legal determination that a document contains no Sensitive Data.
"""

from __future__ import annotations

import re

from .base import Finding


_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ethnic": ("ethnicity", "ethnic origin", "race", "عرق", "أصل عرقي"),
    "belief": ("religion", "religious", "belief", "political", "intellectual", "دين", "معتقد", "سياسي"),
    "criminal": ("criminal", "conviction", "offence", "offense", "جريمة", "إدانة"),
    "biometric": ("biometric", "fingerprint", "facial recognition", "بصمة", "بيومتري"),
    "genetic": ("genetic", "dna", "جينات", "وراثي"),
    "health": ("health", "medical", "patient", "diagnosis", "hospital", "بيانات صحية", "صحي", "طبي", "ملف طبي"),
    "unknown_parentage": ("unknown parent", "adoption", "parentage", "مجهول الأبوين", "تبني"),
    "credit": ("credit history", "credit score", "financing", "loan", "بيانات ائتمانية", "سجل ائتماني", "قرض"),
}


class SensitiveDataDetector:
    def detect(self, text: str) -> list[Finding]:
        findings: list[Finding] = []
        for category, terms in _KEYWORDS.items():
            for term in terms:
                for match in re.finditer(re.escape(term), text, re.IGNORECASE):
                    findings.append(
                        Finding(
                            type="sensitive_data",
                            value=match.group(0),
                            normalized_value=term,
                            start=match.start(),
                            end=match.end(),
                            confidence_tier="format_detected",
                            confidence_level="inferred",
                            checksum_result=None,
                            sensitive_category=category,
                        )
                    )
        return sorted(findings, key=lambda finding: (finding.start, finding.end, finding.sensitive_category or ""))
