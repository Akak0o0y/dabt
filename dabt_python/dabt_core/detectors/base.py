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

    @property
    def is_personal_data(self) -> bool:
        return self.type in {
            "saudi_national_id",
            "iqama",
            "saudi_iban",
            "saudi_mobile",
            "sensitive_data",
        }


class Detector(Protocol):
    def detect(self, text: str) -> list[Finding]: ...
