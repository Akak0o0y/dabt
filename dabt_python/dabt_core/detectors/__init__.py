"""Saudi-specific and PDPL-sensitive data detectors."""

from .commercial_registration import CommercialRegistrationDetector
from .iban import SaudiIbanDetector
from .mobile import SaudiMobileDetector
from .national_id import NationalIdDetector
from .sensitive import SensitiveDataDetector

DEFAULT_DETECTORS = (
    NationalIdDetector(),
    SaudiIbanDetector(),
    SaudiMobileDetector(),
    CommercialRegistrationDetector(),
    SensitiveDataDetector(),
)

__all__ = [
    "CommercialRegistrationDetector",
    "DEFAULT_DETECTORS",
    "NationalIdDetector",
    "SaudiIbanDetector",
    "SaudiMobileDetector",
    "SensitiveDataDetector",
]
