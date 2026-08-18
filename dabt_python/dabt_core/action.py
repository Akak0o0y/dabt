"""The Agent Action Gate: policy evaluation for MCP tool calls.

The retrieval gate evaluates one document. An action gate evaluates a set of
named values — a tool call's arguments on the request leg, its declared response
fields on the response leg. Detection, classification, redaction and audit are
the retrieval gate's, unchanged; only the shape of the payload differs, so a
finding carries the element it came from and offsets relative to that element.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .detectors.base import Detector, Finding
from .manifest import ToolSpec


@dataclass(frozen=True)
class ElementFinding:
    """One detection result, tagged with the element of the call it came from."""

    element: str
    finding: Finding


@dataclass(frozen=True)
class ElementObligation:
    element: str
    start: int
    end: int
    strategy: str


@dataclass(frozen=True)
class ActionRequest:
    server_id: str
    tool: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    agent_id: str = "demo-agent"
    purpose: str = "action"
    lawful_basis: str = "consent"
    sector: str = "development"
    agent_authorised: bool = True
    requires_minimisation: bool = True


@dataclass(frozen=True)
class ActionResultRequest:
    server_id: str
    tool: str
    result: Mapping[str, Any] = field(default_factory=dict)
    agent_id: str = "demo-agent"
    purpose: str = "action"
    lawful_basis: str = "consent"
    sector: str = "development"
    agent_authorised: bool = True
    requires_minimisation: bool = True


def flatten_arguments(spec: ToolSpec | None, arguments: Mapping[str, Any]) -> dict[str, str]:
    """Every argument value is inspectable; the manifest governs masking, not scanning."""
    flattened: dict[str, str] = {}
    for name, value in arguments.items():
        if value is None:
            continue
        flattened[f"arguments.{name}"] = value if isinstance(value, str) else str(value)
    return flattened


def flatten_result(spec: ToolSpec | None, result: Mapping[str, Any]) -> dict[str, str]:
    """Only manifest-declared response fields marked for inspection are scanned."""
    if spec is None:
        return {}
    flattened: dict[str, str] = {}
    for name, value in result.items():
        declared = spec.return_field(name)
        if declared is None or not declared.inspect_content or value is None:
            continue
        if declared.collection and isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                if item is None:
                    continue
                flattened[f"result.{name}[{index}]"] = item if isinstance(item, str) else str(item)
            continue
        flattened[f"result.{name}"] = value if isinstance(value, str) else str(value)
    return flattened


def has_undeclared_fields(spec: ToolSpec | None, result: Mapping[str, Any]) -> bool:
    """A response field the manifest never described cannot be reasoned about.

    Spec limitation 2: such a field is not inspected, so it must not be able to
    reach ALLOW. Without this the gate would permit a response purely because it
    failed to look at it.
    """
    if spec is None:
        return bool(result)
    return any(spec.return_field(name) is None for name in result)


def scan_elements(
    values: Mapping[str, str], detectors: Iterable[Detector]
) -> tuple[ElementFinding, ...]:
    """Run every detector over each element independently, preserving local offsets."""
    detectors = tuple(detectors)
    found: list[ElementFinding] = []
    for element in sorted(values):
        text = values[element]
        for detector in detectors:
            for finding in detector.detect(text):
                found.append(ElementFinding(element, finding))
    return tuple(
        sorted(
            found,
            key=lambda item: (item.element, item.finding.start, item.finding.end, item.finding.type),
        )
    )
