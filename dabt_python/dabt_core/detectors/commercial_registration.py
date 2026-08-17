"""Saudi Commercial Registration format detector.

Region-prefix recognition is intentionally marked inferred: it needs validation
against an authoritative Ministry of Commerce source before regulatory reliance.
"""

from __future__ import annotations

import re

from .base import Finding


_PATTERN = re.compile(r"(?<!\d)((?:1010|4030|2050)\d{6})(?!\d)")


class CommercialRegistrationDetector:
    def detect(self, text: str) -> list[Finding]:
        return [
            Finding(
                type="saudi_commercial_registration",
                value=match.group(1),
                normalized_value=match.group(1),
                start=match.start(1),
                end=match.end(1),
                confidence_tier="format_detected",
                confidence_level="inferred",
                checksum_result=None,
            )
            for match in _PATTERN.finditer(text)
        ]
