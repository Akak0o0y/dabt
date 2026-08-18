"""Conservative keyword detector for PDPL Article 1(11) Sensitive Data.

This reference rule set cannot exhaustively detect sensitive data, especially
obfuscated, contextual, or multilingual variants. A missing finding is never a
legal determination that a document contains no Sensitive Data.

Matching is word-bounded per script. Latin terms use a regex word boundary.
That boundary is wrong for Arabic: Arabic letters are word characters, so a
bare \\b would reject the ordinary attached forms of a term - the definite
article and the conjunction/preposition proclitics - producing false negatives
on the most common written form. Arabic terms therefore match a bounded affix
envelope delimited by Arabic-letter lookarounds.

Arabic diacritics (tashkeel) are not normalised, so a fully vowelled document
may not match. That is a known limitation of this reference detector.
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


_AR_LETTER = "\u0620-\u064a\u0671-\u06d3\u06d5"
# Optional conjunction, then preposition, then the definite article.
_AR_PREFIX = "(?:[\u0648\u0641]?[\u0628\u0643\u0644]?(?:\u0627\u0644)?)"
# Common nominal enclitics, longest alternative first.
_AR_SUFFIX = (
    "(?:\u0627\u062a|\u064a\u0646|\u0648\u0646|\u064a\u0629"
    "|\u0647\u0627|\u0647\u0645|\u0629|\u064a|\u0647)?"
)
# A sentence is the smallest unit that reliably contains the flagged content.
_TERMINATORS = ".!?;\n\r\u060c\u061b\u061f\u06d4"


def _is_arabic(term: str) -> bool:
    return any("\u0600" <= character <= "\u06ff" for character in term)


def _latin_stem(term: str) -> str:
    """Tolerate regular English plurals; a missed category is the costly error."""
    if term.endswith("y"):
        return re.escape(term[:-1]) + "(?:y|ies)"
    return re.escape(term) + "(?:e?s)?"


def _compile(term: str) -> re.Pattern[str]:
    if _is_arabic(term):
        # Each token carries its own affixes: in a multi-word term the definite
        # article attaches to the interior word too, so an envelope wrapped only
        # around the whole phrase would miss the ordinary written form.
        body = "\\s+".join(
            f"{_AR_PREFIX}{re.escape(token)}{_AR_SUFFIX}" for token in term.split()
        )
        return re.compile(f"(?<![{_AR_LETTER}]){body}(?![{_AR_LETTER}])")
    return re.compile(rf"\b{_latin_stem(term)}\b", re.IGNORECASE)


_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = tuple(
    (category, term, _compile(term))
    for category, terms in _KEYWORDS.items()
    for term in terms
)


def _enclosing_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Widen a keyword hit to the sentence carrying it.

    A keyword detector locates the signal, not the protected value: masking
    only the word "medical" leaves the diagnosis beside it in clear text. The
    enclosing sentence is the narrowest deterministic unit that covers it.
    """
    left = start
    while left > 0 and text[left - 1] not in _TERMINATORS:
        left -= 1
    right = end
    while right < len(text) and text[right] not in _TERMINATORS:
        right += 1
    while left < start and text[left].isspace():
        left += 1
    while right > end and text[right - 1].isspace():
        right -= 1
    return left, right


def _drop_contained(findings: list[Finding]) -> list[Finding]:
    """Keep the widest hit per category so one phrase is not reported twice."""
    kept: list[Finding] = []
    for finding in findings:
        if any(
            other is not finding
            and other.sensitive_category == finding.sensitive_category
            and other.start <= finding.start
            and other.end >= finding.end
            and (other.end - other.start) > (finding.end - finding.start)
            for other in findings
        ):
            continue
        kept.append(finding)
    return kept


class SensitiveDataDetector:
    def detect(self, text: str) -> list[Finding]:
        findings: list[Finding] = []
        for category, term, pattern in _PATTERNS:
            for match in pattern.finditer(text):
                redaction_start, redaction_end = _enclosing_span(text, match.start(), match.end())
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
                        redaction_start=redaction_start,
                        redaction_end=redaction_end,
                    )
                )
        return sorted(
            _drop_contained(findings),
            key=lambda finding: (finding.start, finding.end, finding.sensitive_category or ""),
        )
