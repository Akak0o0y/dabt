"""Saudi mobile-number format detector."""

from __future__ import annotations

import re

from .base import Finding


_PATTERN = re.compile(r"(?<!\d)(\+9665\d{8}|009665\d{8}|05\d{8})(?!\d)")


class SaudiMobileDetector:
    def detect(self, text: str) -> list[Finding]:
        return [
            Finding(
                type="saudi_mobile",
                value=match.group(1),
                normalized_value=(
                    "+966" + match.group(1)[1:]
                    if match.group(1).startswith("0") and not match.group(1).startswith("00966")
                    else "+" + match.group(1)[2:]
                    if match.group(1).startswith("00966")
                    else match.group(1)
                ),
                start=match.start(1),
                end=match.end(1),
                confidence_tier="format_detected",
                confidence_level="verified",
                checksum_result=None,
            )
            for match in _PATTERN.finditer(text)
        ]
