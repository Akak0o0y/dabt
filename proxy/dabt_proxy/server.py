"""MCP wiring: the edge where gate outcomes become protocol messages.

Two invariants live here.

`stdout` is the MCP transport. Every log line and audit record goes to `stderr`,
because a stray byte on `stdout` corrupts the protocol framing.

The audit log records the decision, never the payload. It states that a Saudi
IBAN was found in `arguments.value` and withheld; it does not write the IBAN to
disk. A gate whose log contains what it just refused to disclose has moved the
leak rather than closed it - the same discipline the Evidence Vault applies to
source documents.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any, Callable, TextIO

import httpx
from mcp import stdio_server, types
from mcp.server.lowlevel import Server

from . import __version__
from .adapter import to_call_tool_result
from .config import ProxyConfig
from .gate import Gate
from .outcome import GateOutcome
from .policy import HttpPolicyClient, InProcessPolicyClient, PolicyClient
from .upstream import connect

REWRITTEN_NOTE_EN = (
    "Dabt redacted part of this exchange before release. The values you see are "
    "masked, not the originals."
)
REWRITTEN_NOTE_AR = (
    "حجبت ضبط جزءًا من هذا التبادل قبل الإفصاح. القيم المعروضة محجوبة وليست القيم الأصلية."
)


def utc_now() -> str:
    """The engine takes its clock from the caller; this is that clock."""
    return datetime.now(timezone.utc).isoformat()


def build_policy_client(config: ProxyConfig) -> PolicyClient:
    if config.policy_url:
        async def post(url: str, body: dict[str, Any]) -> Any:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=body)
                response.raise_for_status()
                return response.json()

        return HttpPolicyClient(config.policy_url, post)
    return InProcessPolicyClient(config.build_engine(), config.compliance_map.version)


def audit_entry(outcome: GateOutcome, timestamp: str) -> dict[str, Any]:
    """A record of the decision and its grounds, carrying no gated payload."""
    return {
        "timestamp": timestamp,
        "tool": outcome.tool,
        "decision": outcome.decision,
        "leg": outcome.leg,
        "blocked": outcome.blocked,
        "dispatched": outcome.dispatched,
        "decision_rule_id": outcome.decision_rule_id,
        "citation": outcome.citation,
        "classification": outcome.classification,
        # Types and element paths only. The matched text is deliberately absent.
        "findings": [
            {"element": finding.get("element"), "type": finding.get("type")}
            for finding in outcome.findings
        ],
        "fired_rules": list(outcome.fired_rules),
        "rewritten_arguments": outcome.rewritten_arguments,
        "rewritten_result": outcome.rewritten_result,
        "reason_en": outcome.reason_en,
        "reason_ar": outcome.reason_ar,
        "manifest_version": outcome.manifest_version,
        "policy_map_version": outcome.policy_map_version,
        "legal_review_disclaimer_en": outcome.legal_review_disclaimer_en,
        "legal_review_disclaimer_ar": outcome.legal_review_disclaimer_ar,
    }


class AuditSink:
    """Writes audit records to stderr, and optionally to a file."""

    def __init__(self, stream: TextIO | None = None, path: Any = None) -> None:
        self._stream = stream if stream is not None else sys.stderr
        self._path = path

    def write(self, entry: dict[str, Any]) -> None:
        line = json.dumps(entry, ensure_ascii=False)
        print(line, file=self._stream, flush=True)
        if self._path is not None:
            with open(self._path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")


def refusal_text(outcome: GateOutcome) -> str:
    """A refusal an agent can read, stating the rule it rests on."""
    lines = [f"DABT ACTION GATE: {outcome.decision} ({outcome.leg} leg) for '{outcome.tool}'"]
    if outcome.decision_rule_id:
        citation = outcome.citation or {}
        detail = " | ".join(
            part
            for part in (
                f"rule {outcome.decision_rule_id}",
                citation.get("framework"),
                citation.get("article"),
                (
                    f"mapping confidence: {citation['confidence_level']}"
                    if citation.get("confidence_level")
                    else None
                ),
            )
            if part
        )
        lines.append(detail)
    if outcome.dispatched:
        lines.append(
            "The call had already been forwarded, so any side effect stands; "
            "only the disclosure was stopped."
        )
    lines.append(f"EN: {outcome.reason_en}")
    lines.append(f"AR: {outcome.reason_ar}")
    if outcome.legal_review_disclaimer_en:
        lines.append(f"EN: {outcome.legal_review_disclaimer_en}")
    if outcome.legal_review_disclaimer_ar:
        lines.append(f"AR: {outcome.legal_review_disclaimer_ar}")
    return "\n".join(lines)


def to_mcp_result(outcome: GateOutcome) -> types.CallToolResult:
    """Render a gate outcome as the tool result the agent receives."""
    if outcome.blocked:
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=refusal_text(outcome))],
            structuredContent={"dabt": audit_entry(outcome, utc_now())},
            isError=True,
        )

    assert outcome.released is not None  # a released outcome always carries a response
    result = to_call_tool_result(outcome.released)
    if outcome.rewritten_arguments or outcome.rewritten_result:
        # The agent must not proceed believing it read or wrote the original value.
        result.content.append(
            types.TextContent(type="text", text=f"EN: {REWRITTEN_NOTE_EN}\nAR: {REWRITTEN_NOTE_AR}")
        )
    return result


def build_server(gate: Gate, audit: AuditSink, name: str = "dabt-proxy") -> Server[Any]:
    async def on_list_tools(_: Any, __: Any) -> types.ListToolsResult:
        return await gate.list_tools()

    async def on_call_tool(_: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        outcome = await gate.call_tool(params.name, params.arguments or {})
        audit.write(audit_entry(outcome, utc_now()))
        return to_mcp_result(outcome)

    return Server(
        name,
        version=__version__,
        instructions=(
            "Every tool call is evaluated against Saudi regulatory policy before it "
            "executes, and its result before disclosure. A blocked call returns the "
            "rule it was blocked on. This is an engineering control, not a legal "
            "determination."
        ),
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


async def serve(config: ProxyConfig, clock: Callable[[], str] = utc_now) -> None:
    """Run the gate over stdio until the client disconnects."""
    audit = AuditSink(path=config.audit_log)
    async with connect(config.upstream) as upstream:
        gate = Gate(
            policy=build_policy_client(config),
            upstream=upstream,
            server_id=config.server_id,
            clock=clock,
            context=config.context.as_engine_context(),
        )
        server = build_server(gate, audit)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
