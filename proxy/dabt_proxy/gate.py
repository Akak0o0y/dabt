"""The gate: what happens between an agent asking and a tool running.

Both collaborators are injected protocols, so every branch below is reachable in
a test without a subprocess, a socket, or a real MCP server. That is the point of
the shape - the behaviour worth trusting is the behaviour that is cheap to prove.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from .adapter import ResponseEnvelope, restore, to_envelope
from .outcome import (
    ALLOW_WITH_REDACTION,
    DENY,
    REVIEW,
    GateOutcome,
    PolicyOutcome,
    ToolResponse,
)
from .policy import PolicyClient

UPSTREAM_ERROR = "UPSTREAM_ERROR"

UNINSPECTABLE_EN = (
    "The response carried content Dabt cannot inspect ({types}), so its disclosure is "
    "held for human review. This is a limit of the gate's detectors, not a finding "
    "about the content."
)
UNINSPECTABLE_AR = (
    "احتوت النتيجة على محتوى لا تستطيع ضبط تفتيشه ({types})، ولذلك أُوقف الإفصاح عنها "
    "لمراجعة بشرية. وهذا قيد في أدوات الكشف، وليس استنتاجًا بشأن المحتوى."
)

INCOHERENT_RELEASE_EN = (
    "The engine required redaction but released no rewritten payload, so the call was "
    "denied rather than forwarded unredacted."
)
INCOHERENT_RELEASE_AR = (
    "اشترط المحرّك الحجب دون أن يُصدر حِزمة معادة الصياغة، ولذلك رُفض الاستدعاء بدلًا من "
    "تمريره دون حجب."
)

UPSTREAM_FAILED_EN = (
    "The call was permitted and forwarded, but the upstream server failed: {error}. "
    "Whether the operation took effect is unknown to Dabt."
)
UPSTREAM_FAILED_AR = (
    "سُمح بالاستدعاء وأُرسل، لكن الخدمة المستهدفة فشلت: {error}. ولا تعلم ضبط ما إذا كان "
    "الإجراء قد نفذ."
)


class UpstreamClient(Protocol):
    """The gated server, as the gate sees it."""

    async def list_tools(self) -> Any: ...

    async def call_tool(self, tool: str, arguments: Mapping[str, Any]) -> ToolResponse: ...


def _rule_evidence(outcome: PolicyOutcome) -> dict[str, Any] | None:
    """The deciding rule's own words, so a refusal can state its grounds."""
    for rule in outcome.audit.get("fired_rules") or ():
        if isinstance(rule, Mapping) and rule.get("id") == outcome.decision_rule_id:
            return dict(rule)
    return None


class Gate:
    """Evaluate, then forward - never the other way round."""

    def __init__(
        self,
        policy: PolicyClient,
        upstream: UpstreamClient,
        server_id: str,
        clock: Any,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        self._policy = policy
        self._upstream = upstream
        self._server_id = server_id
        self._clock = clock
        self._context = dict(context or {})

    async def list_tools(self) -> Any:
        """Discovery is passed through unaltered; only tools/call is gated."""
        return await self._upstream.list_tools()

    def _blocked(
        self,
        tool: str,
        leg: str,
        outcome: PolicyOutcome,
        dispatched: bool,
        reason_en: str | None = None,
        reason_ar: str | None = None,
        decision: str | None = None,
    ) -> GateOutcome:
        evidence = _rule_evidence(outcome)
        audit = outcome.audit
        fallback_en = (
            outcome.detail_en or (evidence or {}).get("rationale_en") or audit.get("summary_en")
        )
        fallback_ar = (
            outcome.detail_ar or (evidence or {}).get("rationale_ar") or audit.get("summary_ar")
        )
        return GateOutcome(
            tool=tool,
            blocked=True,
            leg=leg,
            decision=decision or outcome.decision,
            reason_en=reason_en or str(fallback_en or "The Action Gate did not permit this call."),
            reason_ar=reason_ar or str(fallback_ar or "لم تسمح بوابة الإجراءات بهذا الاستدعاء."),
            decision_rule_id=outcome.decision_rule_id,
            citation=(
                {
                    "framework": evidence.get("framework"),
                    "article": evidence.get("article"),
                    "confidence_level": evidence.get("confidence_level"),
                }
                if evidence
                else None
            ),
            classification=outcome.classification,
            findings=outcome.findings,
            fired_rules=outcome.fired_rules,
            dispatched=dispatched,
            audit=audit,
            manifest_version=outcome.manifest_version,
            policy_map_version=outcome.policy_map_version,
            legal_review_disclaimer_en=audit.get("legal_review_disclaimer_en"),
            legal_review_disclaimer_ar=audit.get("legal_review_disclaimer_ar"),
        )

    async def call_tool(self, tool: str, arguments: Mapping[str, Any]) -> GateOutcome:
        """Gate one tool call across both legs.

        The request leg is the only place a side effect can be prevented. The
        response leg cannot unwind what already ran, but it can still stop a
        live credential reaching the model - a separate event worth stopping.
        """
        request_outcome = await self._policy.evaluate_action(
            self._server_id, tool, arguments, self._clock(), **self._context
        )
        if not request_outcome.releases:
            # Nothing is forwarded. This is the branch the product exists for.
            return self._blocked(tool, "request", request_outcome, dispatched=False)

        forward = request_outcome.released_arguments
        if forward is None:
            if request_outcome.decision == ALLOW_WITH_REDACTION or request_outcome.rewritten:
                # Forwarding the originals here would send exactly the values the
                # engine just said must be masked.
                return self._blocked(
                    tool,
                    "request",
                    request_outcome,
                    dispatched=False,
                    decision=DENY,
                    reason_en=INCOHERENT_RELEASE_EN,
                    reason_ar=INCOHERENT_RELEASE_AR,
                )
            forward = dict(arguments)

        try:
            response = await self._upstream.call_tool(tool, forward)
        except Exception as error:  # noqa: BLE001 - reported, never swallowed into an ALLOW
            return self._blocked(
                tool,
                "upstream",
                request_outcome,
                dispatched=True,
                decision=UPSTREAM_ERROR,
                reason_en=UPSTREAM_FAILED_EN.format(error=error),
                reason_ar=UPSTREAM_FAILED_AR.format(error=error),
            )

        envelope = to_envelope(response)
        if envelope.uninspectable:
            block_types = ", ".join(sorted(set(envelope.uninspectable_block_types)))
            return self._blocked(
                tool,
                "response",
                request_outcome,
                dispatched=True,
                decision=REVIEW,
                reason_en=UNINSPECTABLE_EN.format(types=block_types),
                reason_ar=UNINSPECTABLE_AR.format(types=block_types),
            )

        result_outcome = await self._policy.evaluate_action_result(
            self._server_id, tool, envelope.payload, self._clock(), **self._context
        )
        if not result_outcome.releases:
            return self._blocked(tool, "response", result_outcome, dispatched=True)

        released_payload = result_outcome.released_result
        if released_payload is None:
            if result_outcome.decision == ALLOW_WITH_REDACTION or result_outcome.rewritten:
                return self._blocked(
                    tool,
                    "response",
                    result_outcome,
                    dispatched=True,
                    decision=DENY,
                    reason_en=INCOHERENT_RELEASE_EN,
                    reason_ar=INCOHERENT_RELEASE_AR,
                )
            released_payload = envelope.payload

        released = restore(response, envelope, released_payload, result_outcome.rewritten)
        return self._released(tool, request_outcome, result_outcome, released)

    def _released(
        self,
        tool: str,
        request_outcome: PolicyOutcome,
        result_outcome: PolicyOutcome,
        released: ToolResponse,
    ) -> GateOutcome:
        audit = result_outcome.audit
        return GateOutcome(
            tool=tool,
            blocked=False,
            leg="response",
            decision=result_outcome.decision,
            reason_en=str(audit.get("summary_en") or "Released."),
            reason_ar=str(audit.get("summary_ar") or "أُفصح عنها."),
            decision_rule_id=result_outcome.decision_rule_id,
            classification=result_outcome.classification,
            findings=result_outcome.findings,
            fired_rules=result_outcome.fired_rules,
            rewritten_arguments=request_outcome.rewritten,
            rewritten_result=result_outcome.rewritten,
            released=released,
            dispatched=True,
            audit=audit,
            manifest_version=result_outcome.manifest_version,
            policy_map_version=result_outcome.policy_map_version,
            legal_review_disclaimer_en=audit.get("legal_review_disclaimer_en"),
            legal_review_disclaimer_ar=audit.get("legal_review_disclaimer_ar"),
        )
