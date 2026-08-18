"""Domain types shared by the gate, its policy client, and its upstream client.

These deliberately carry no MCP wire types. The gate reasons about a normalised
tool response and a normalised policy outcome; translating to and from MCP's
`CallToolResult` happens at the edge, in `adapter.py` and `server.py`. That
keeps the interesting logic testable without a transport, a subprocess, or a
socket.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Outcomes the engine can return. Mirrored here as plain strings because the
# proxy must also represent states the engine never produces (a transport
# failure, a response the proxy cannot inspect) without inventing new Decision
# members inside dabt_core.
ALLOW = "ALLOW"
ALLOW_WITH_REDACTION = "ALLOW_WITH_REDACTION"
DENY = "DENY"
REVIEW = "REVIEW"

RELEASING_DECISIONS = frozenset({ALLOW, ALLOW_WITH_REDACTION})


@dataclass(frozen=True)
class ToolResponse:
    """An upstream tool response, normalised but not lossy.

    `blocks` holds the upstream content blocks exactly as received, so a
    passthrough returns byte-for-byte what the server sent. `structured` holds
    `structuredContent` when the server supplied it. Both are kept because the
    proxy has to gate one and return the other consistently: a server that
    returns structured content normally mirrors it as serialised text, and
    substituting only the structure would hand the model the unredacted text.
    """

    structured: dict[str, Any] | None = None
    blocks: tuple[Any, ...] = ()
    is_error: bool = False


@dataclass(frozen=True)
class PolicyOutcome:
    """One evaluation from the policy engine, however it was reached."""

    decision: str
    decision_rule_id: str | None = None
    classification: str | None = None
    released_arguments: dict[str, Any] | None = None
    released_result: dict[str, Any] | None = None
    rewritten: bool = False
    findings: tuple[dict[str, Any], ...] = ()
    fired_rules: tuple[str, ...] = ()
    obligations: tuple[dict[str, Any], ...] = ()
    audit: dict[str, Any] = field(default_factory=dict)
    classification_evidence: dict[str, Any] = field(default_factory=dict)
    manifest_version: str | None = None
    policy_map_version: str | None = None
    # True when the outcome is a fail-closed denial the engine did not author:
    # the service was unreachable, or it could not describe what went wrong.
    service_error: bool = False
    detail_en: str | None = None
    detail_ar: str | None = None

    @property
    def releases(self) -> bool:
        return self.decision in RELEASING_DECISIONS and not self.service_error


@dataclass(frozen=True)
class GateOutcome:
    """What the gate decided about one tool call, and why.

    `blocked` is the single question the transport layer asks. Everything else
    exists so the refusal can state its own grounds in both languages, which is
    the whole point of gating rather than merely logging.
    """

    tool: str
    blocked: bool
    leg: str
    decision: str
    reason_en: str
    reason_ar: str
    decision_rule_id: str | None = None
    citation: dict[str, Any] | None = None
    classification: str | None = None
    findings: tuple[dict[str, Any], ...] = ()
    fired_rules: tuple[str, ...] = ()
    rewritten_arguments: bool = False
    rewritten_result: bool = False
    released: ToolResponse | None = None
    # The call was forwarded upstream. Whether it took effect is upstream's to
    # know: on an upstream failure after ALLOW the proxy genuinely cannot tell,
    # and an audit record must not claim otherwise.
    dispatched: bool = False
    audit: dict[str, Any] = field(default_factory=dict)
    manifest_version: str | None = None
    policy_map_version: str | None = None
    legal_review_disclaimer_en: str | None = None
    legal_review_disclaimer_ar: str | None = None
