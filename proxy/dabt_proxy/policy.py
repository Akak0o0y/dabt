"""How the proxy reaches the policy engine.

Two implementations, one protocol. In-process imports the engine, which means
the gate has no runtime dependency on a service being up - so "fails closed" is
structurally true rather than true while the service happens to be running. HTTP
calls the same endpoints a production gateway would call, which makes the proxy
a faithful integration example.

Both parse the *same* payload shape, because `ActionResult.to_dict()` is what
the FastAPI layer serialises. That is deliberate: a shared parser is why the two
transports cannot drift in what they conclude from an identical evaluation.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from dabt_core.action import ActionEngine, ActionRequest, ActionResultRequest

from .outcome import DENY, PolicyOutcome

SERVICE_ERROR_REQUEST_EN = (
    "The Action Gate could not evaluate this call and therefore denied it."
)
SERVICE_ERROR_REQUEST_AR = "تعذر على بوابة الإجراءات تقييم هذا الاستدعاء، ولذلك رفضته."
SERVICE_ERROR_RESULT_EN = (
    "The Action Gate could not evaluate this result and therefore denied its disclosure."
)
SERVICE_ERROR_RESULT_AR = "تعذر على بوابة الإجراءات تقييم هذه النتيجة، ولذلك رفضت الإفصاح عنها."


def failed_closed(detail_en: str, detail_ar: str) -> PolicyOutcome:
    """A gate that cannot decide denies. Failing open would defeat the gate."""
    return PolicyOutcome(
        decision=DENY,
        service_error=True,
        detail_en=detail_en,
        detail_ar=detail_ar,
    )


def outcome_from_payload(payload: Mapping[str, Any]) -> PolicyOutcome:
    """Read an evaluation payload, whichever transport produced it."""
    if payload.get("service_error"):
        return failed_closed(
            str(payload.get("detail_en") or SERVICE_ERROR_REQUEST_EN),
            str(payload.get("detail_ar") or SERVICE_ERROR_REQUEST_AR),
        )
    return PolicyOutcome(
        decision=str(payload["decision"]),
        decision_rule_id=payload.get("decision_rule_id"),
        classification=payload.get("classification"),
        released_arguments=payload.get("released_arguments"),
        released_result=payload.get("released_result"),
        rewritten=bool(payload.get("rewritten", False)),
        findings=tuple(payload.get("findings") or ()),
        fired_rules=tuple(payload.get("fired_rules") or ()),
        obligations=tuple(payload.get("obligations") or ()),
        audit=dict(payload.get("audit") or {}),
        classification_evidence=dict(payload.get("classification_evidence") or {}),
        manifest_version=payload.get("manifest_version"),
        policy_map_version=payload.get("policy_map_version"),
    )


class PolicyClient(Protocol):
    """The gate's only view of the policy engine."""

    async def evaluate_action(
        self, server_id: str, tool: str, arguments: Mapping[str, Any], timestamp: str, **context: Any
    ) -> PolicyOutcome: ...

    async def evaluate_action_result(
        self, server_id: str, tool: str, result: Mapping[str, Any], timestamp: str, **context: Any
    ) -> PolicyOutcome: ...


class InProcessPolicyClient:
    """Evaluate in this process, against an injected engine.

    No socket and no subprocess, so the gate cannot be defeated by making a
    service unavailable - the failure mode `dabt.ts` still has, and the reason
    this is the default.
    """

    def __init__(self, engine: ActionEngine, policy_map_version: str) -> None:
        self._engine = engine
        self._policy_map_version = policy_map_version

    def _finish(self, payload: dict[str, Any]) -> PolicyOutcome:
        return outcome_from_payload({**payload, "policy_map_version": self._policy_map_version})

    async def evaluate_action(
        self, server_id: str, tool: str, arguments: Mapping[str, Any], timestamp: str, **context: Any
    ) -> PolicyOutcome:
        try:
            result = self._engine.evaluate(
                ActionRequest(server_id=server_id, tool=tool, arguments=dict(arguments), **context),
                timestamp,
            )
        except Exception:  # noqa: BLE001 - the gate denies anything it cannot describe
            return failed_closed(SERVICE_ERROR_REQUEST_EN, SERVICE_ERROR_REQUEST_AR)
        return self._finish(result.to_dict())

    async def evaluate_action_result(
        self, server_id: str, tool: str, result: Mapping[str, Any], timestamp: str, **context: Any
    ) -> PolicyOutcome:
        try:
            evaluated = self._engine.evaluate_result(
                ActionResultRequest(server_id=server_id, tool=tool, result=dict(result), **context),
                timestamp,
            )
        except Exception:  # noqa: BLE001
            return failed_closed(SERVICE_ERROR_RESULT_EN, SERVICE_ERROR_RESULT_AR)
        return self._finish(evaluated.to_dict())


class HttpPolicyClient:
    """Call the FastAPI service - the integration pattern a real gateway copies.

    Any transport failure is a denial, not a pass-through. This client therefore
    makes the policy service a hard dependency of every gated call, which is the
    correct trade for an enforcement point and the reason it is not the default
    for the reference harness.
    """

    def __init__(self, base_url: str, post: Any) -> None:
        self._base_url = base_url.rstrip("/")
        self._post = post

    async def _evaluate(self, path: str, body: dict[str, Any], en: str, ar: str) -> PolicyOutcome:
        try:
            payload = await self._post(f"{self._base_url}{path}", body)
        except Exception:  # noqa: BLE001 - unreachable, timed out, or unparseable
            return failed_closed(en, ar)
        if not isinstance(payload, Mapping) or "decision" not in payload:
            return failed_closed(en, ar)
        return outcome_from_payload(payload)

    async def evaluate_action(
        self, server_id: str, tool: str, arguments: Mapping[str, Any], timestamp: str, **context: Any
    ) -> PolicyOutcome:
        return await self._evaluate(
            "/v1/action/evaluate",
            {
                "server_id": server_id,
                "tool": tool,
                "arguments": dict(arguments),
                "timestamp": timestamp,
                **context,
            },
            SERVICE_ERROR_REQUEST_EN,
            SERVICE_ERROR_REQUEST_AR,
        )

    async def evaluate_action_result(
        self, server_id: str, tool: str, result: Mapping[str, Any], timestamp: str, **context: Any
    ) -> PolicyOutcome:
        return await self._evaluate(
            "/v1/action/result",
            {
                "server_id": server_id,
                "tool": tool,
                "result": dict(result),
                "timestamp": timestamp,
                **context,
            },
            SERVICE_ERROR_RESULT_EN,
            SERVICE_ERROR_RESULT_AR,
        )
