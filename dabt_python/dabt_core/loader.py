"""Single explicit I/O boundary for loading a Dabt compliance map."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .schema import ComplianceMap, SchemaError, validate_map_payload


def load_compliance_map(path: str | Path) -> ComplianceMap:
    """Read and validate the map once, before any evaluation can occur."""
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload: Any = yaml.safe_load(handle)
    except OSError as exc:
        raise SchemaError(f"compliance map: unable to read {path}") from exc
    except yaml.YAMLError as exc:
        raise SchemaError(f"compliance map: invalid YAML in {path}") from exc
    return validate_map_payload(payload)

