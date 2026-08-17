"""Saudi IBAN format detection plus ISO 13616 MOD-97 confidence validation."""

from __future__ import annotations

import re

from .base import Finding


_PATTERN = re.compile(r"(?<![A-Z0-9])(SA\d{2}(?:[\s-]?[A-Z0-9]){20})(?![A-Z0-9])", re.IGNORECASE)


def passes_mod97(iban: str) -> bool:
    normalized = re.sub(r"[\s-]", "", iban).upper()
    if len(normalized) != 24 or not normalized.startswith("SA") or not normalized.isalnum():
        return False
    rearranged = normalized[4:] + normalized[:4]
    digits = "".join(str(ord(char) - 55) if char.isalpha() else char for char in rearranged)
    remainder = 0
    for char in digits:
        remainder = (remainder * 10 + int(char)) % 97
    return remainder == 1


class SaudiIbanDetector:
    def detect(self, text: str) -> list[Finding]:
        findings: list[Finding] = []
        for match in _PATTERN.finditer(text):
            value = match.group(1)
            normalized = re.sub(r"[\s-]", "", value).upper()
            checksum_ok = passes_mod97(normalized)
            findings.append(
                Finding(
                    type="saudi_iban",
                    value=value,
                    normalized_value=normalized,
                    start=match.start(1),
                    end=match.end(1),
                    confidence_tier="checksum_verified" if checksum_ok else "format_detected",
                    confidence_level="verified" if checksum_ok else "inferred",
                    checksum_result=checksum_ok,
                )
            )
        return findings
