"""Saudi National ID and Iqama detector.

The ten-digit format is a detection boundary. The checksum only raises the
confidence tier; an invalid checksum must never suppress a format match.
"""

from __future__ import annotations

import re

from .base import Finding


_PATTERN = re.compile(r"(?<!\d)([12]\d{9})(?!\d)")


def passes_saudi_id_checksum(value: str) -> bool:
    """Apply the commonly used Saudi ID mod-10 (Luhn-style) confidence check."""
    if len(value) != 10 or not value.isdigit() or value[0] not in {"1", "2"}:
        return False
    total = 0
    for index, char in enumerate(value[:9]):
        digit = int(char)
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    check_digit = (10 - (total % 10)) % 10
    return check_digit == int(value[9])


class NationalIdDetector:
    def detect(self, text: str) -> list[Finding]:
        findings: list[Finding] = []
        for match in _PATTERN.finditer(text):
            value = match.group(1)
            checksum_ok = passes_saudi_id_checksum(value)
            findings.append(
                Finding(
                    type="saudi_national_id" if value[0] == "1" else "iqama",
                    value=value,
                    normalized_value=value,
                    start=match.start(1),
                    end=match.end(1),
                    confidence_tier="checksum_verified" if checksum_ok else "format_detected",
                    confidence_level="verified" if checksum_ok else "inferred",
                    checksum_result=checksum_ok,
                )
            )
        return findings
