"""Shared finding type and detector contract; intentionally free of I/O."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Finding:
    """One deterministic detection result, preserving source offsets."""

    type: str
    value: str
    normalized_value: str
    start: int
    end: int
    confidence_tier: str
    confidence_level: str
    checksum_result: bool | None
    sensitive_category: str | None = None
    redaction_start: int | None = None
    redaction_end: int | None = None

    @property
    def is_personal_data(self) -> bool:
        return self.type in {
            "saudi_national_id",
            "iqama",
            "saudi_iban",
            "saudi_mobile",
            "saudi_commercial_registration",
            "sensitive_data",
        }

    @property
    def redaction_span(self) -> tuple[int, int]:
        """The span an obligation must mask.

        For a directly matched identifier the detection span is the protected
        value. For a keyword-triggered finding the matched word is only the
        signal; the protected content sits around it, so the detector supplies
        a wider span. Detection offsets stay exact for evidence either way.
        """
        start = self.start if self.redaction_start is None else self.redaction_start
        end = self.end if self.redaction_end is None else self.redaction_end
        return start, end


class Detector(Protocol):
    def detect(self, text: str) -> list[Finding]: ...
