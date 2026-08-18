"""Strict, immutable types for a tool manifest.

A manifest states what a third party's tool does: which operation it performs,
which parameter carries a deployment region, which response field carries a
credential. That is a claim about software Dabt does not control, so it is
validated at load time on the same terms as a claim about a regulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .schema import ConfidenceLevel


class ManifestError(ValueError):
    """Raised when a tool manifest cannot meet Dabt's integrity contract."""


OPERATIONS = frozenset({"create", "read", "update", "delete", "execute"})
REQUEST_ROLES = frozenset(
    {
        "deployment_region",
        "opaque_payload",
        "resource_name",
        "resource_reference",
        "credential_reference",
    }
)
RESPONSE_ROLES = frozenset({"credential", "opaque_payload", "resource_metadata"})


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    role: str
    maskable: bool


@dataclass(frozen=True)
class ReturnFieldSpec:
    name: str
    role: str
    maskable: bool
    declared_sensitive: bool = False
    inspect_content: bool = False
    collection: bool = False


@dataclass(frozen=True)
class ToolSpec:
    name: str
    operation: str
    resource_type: str
    persists_data: bool
    confidence_level: ConfidenceLevel
    requires_legal_review: bool
    parameters: tuple[ParameterSpec, ...] = ()
    returns: tuple[ReturnFieldSpec, ...] = ()

    def parameter(self, name: str) -> ParameterSpec | None:
        for item in self.parameters:
            if item.name == name:
                return item
        return None

    def return_field(self, name: str) -> ReturnFieldSpec | None:
        for item in self.returns:
            if item.name == name:
                return item
        return None

    @property
    def declares_sensitive_response(self) -> bool:
        return any(item.declared_sensitive for item in self.returns)


@dataclass(frozen=True)
class ToolManifest:
    version: str
    server_id: str
    tools: tuple[ToolSpec, ...]

    def tool(self, name: str) -> ToolSpec | None:
        for item in self.tools:
            if item.name == name:
                return item
        return None

    def parameter(self, tool_name: str, parameter_name: str) -> ParameterSpec | None:
        spec = self.tool(tool_name)
        return spec.parameter(parameter_name) if spec else None


def _require(mapping: Mapping[str, Any], key: str, label: str) -> Any:
    if key not in mapping:
        raise ManifestError(f"{label}: missing required field '{key}'")
    return mapping[key]


def _non_empty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{label}: must be a non-empty string")
    return value


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ManifestError(f"{label}: must be a boolean")
    return value


def _legal_review(value: Any, label: str) -> bool:
    if value is not True:
        raise ManifestError(f"{label}: must be true")
    return True


def _confidence(value: Any, label: str) -> ConfidenceLevel:
    try:
        return ConfidenceLevel(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in ConfidenceLevel)
        raise ManifestError(f"{label}: must be one of {allowed}") from exc


def _parse_parameter(name: str, raw: Any, label: str) -> ParameterSpec:
    if not isinstance(raw, Mapping):
        raise ManifestError(f"{label}: must be an object")
    role = _non_empty(_require(raw, "role", label), f"{label}.role")
    if role not in REQUEST_ROLES:
        allowed = ", ".join(sorted(REQUEST_ROLES))
        raise ManifestError(f"{label}.role: must be one of {allowed}")
    return ParameterSpec(
        name=name,
        role=role,
        maskable=_boolean(_require(raw, "maskable", label), f"{label}.maskable"),
    )


def _parse_return_field(name: str, raw: Any, label: str) -> ReturnFieldSpec:
    if not isinstance(raw, Mapping):
        raise ManifestError(f"{label}: must be an object")
    role = _non_empty(_require(raw, "role", label), f"{label}.role")
    if role not in RESPONSE_ROLES:
        allowed = ", ".join(sorted(RESPONSE_ROLES))
        raise ManifestError(f"{label}.role: must be one of {allowed}")
    return ReturnFieldSpec(
        name=name,
        role=role,
        maskable=_boolean(_require(raw, "maskable", label), f"{label}.maskable"),
        declared_sensitive=_boolean(raw.get("declared_sensitive", False), f"{label}.declared_sensitive"),
        inspect_content=_boolean(raw.get("inspect_content", False), f"{label}.inspect_content"),
        collection=_boolean(raw.get("collection", False), f"{label}.collection"),
    )


def _parse_tool(name: str, raw: Any) -> ToolSpec:
    label = name
    if not isinstance(raw, Mapping):
        raise ManifestError(f"{label}: must be an object")

    operation = _non_empty(_require(raw, "operation", label), f"{label}.operation")
    if operation not in OPERATIONS:
        allowed = ", ".join(sorted(OPERATIONS))
        raise ManifestError(f"{label}.operation: must be one of {allowed}")

    parameters = tuple(
        _parse_parameter(param_name, param_raw, f"{label}.parameters.{param_name}")
        for param_name, param_raw in (raw.get("parameters") or {}).items()
    )
    returns = tuple(
        _parse_return_field(field_name, field_raw, f"{label}.returns.{field_name}")
        for field_name, field_raw in (raw.get("returns") or {}).items()
    )

    return ToolSpec(
        name=name,
        operation=operation,
        resource_type=_non_empty(_require(raw, "resource_type", label), f"{label}.resource_type"),
        persists_data=_boolean(_require(raw, "persists_data", label), f"{label}.persists_data"),
        confidence_level=_confidence(_require(raw, "confidence_level", label), f"{label}.confidence_level"),
        requires_legal_review=_legal_review(
            _require(raw, "requires_legal_review", label), f"{label}.requires_legal_review"
        ),
        parameters=parameters,
        returns=returns,
    )


def validate_manifest_payload(raw: Mapping[str, Any]) -> ToolManifest:
    """Validate an untrusted manifest payload and return an immutable ToolManifest."""
    if not isinstance(raw, Mapping):
        raise ManifestError("tool manifest: expected an object")
    version = _non_empty(_require(raw, "version", "tool manifest"), "tool manifest.version")
    server = _require(raw, "server", "tool manifest")
    if not isinstance(server, Mapping):
        raise ManifestError("tool manifest.server: must be an object")
    server_id = _non_empty(_require(server, "id", "tool manifest.server"), "tool manifest.server.id")

    raw_tools = _require(raw, "tools", "tool manifest")
    if not isinstance(raw_tools, Mapping) or not raw_tools:
        raise ManifestError("tool manifest.tools: must be a non-empty object")

    return ToolManifest(
        version=version,
        server_id=server_id,
        tools=tuple(_parse_tool(name, spec) for name, spec in raw_tools.items()),
    )


def load_manifest(path: str | Path) -> ToolManifest:
    """Read and validate a manifest once, before any evaluation can occur."""
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            payload: Any = yaml.safe_load(handle)
    except OSError as exc:
        raise ManifestError(f"tool manifest: unable to read {path}") from exc
    except yaml.YAMLError as exc:
        raise ManifestError(f"tool manifest: invalid YAML in {path}") from exc
    return validate_manifest_payload(payload)
