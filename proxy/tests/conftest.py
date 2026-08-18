"""Shared fixtures.

The fakes here are deliberately dumb. `FakeUpstream` records what reached it and
returns what it was told to; `ScriptedPolicy` returns prepared outcomes. Between
them every branch of the gate is reachable without a transport, which is what
makes the interception guarantee cheap to assert rather than expensive to
demonstrate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pytest
from dabt_core.action import ActionEngine
from dabt_core.loader import load_compliance_map
from dabt_core.manifest import load_manifest

from dabt_proxy.config import DEFAULT_MAP, load_manifests
from dabt_proxy.gate import Gate
from dabt_proxy.outcome import PolicyOutcome, ToolResponse
from dabt_proxy.policy import InProcessPolicyClient

FIXTURES = Path(__file__).parent / "fixtures"
DEMO_MANIFEST = FIXTURES / "demo_paas.yaml"

FIXED_TIME = "2026-08-18T09:00:00+00:00"


def fixed_clock() -> str:
    return FIXED_TIME


class FakeUpstream:
    """An upstream that records every call it receives."""

    def __init__(self, response: ToolResponse | None = None, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.response = response if response is not None else ToolResponse(structured={})
        self.error = error
        self.tools: Any = None

    async def list_tools(self) -> Any:
        return self.tools

    async def call_tool(self, tool: str, arguments: Mapping[str, Any]) -> ToolResponse:
        self.calls.append((tool, dict(arguments)))
        if self.error is not None:
            raise self.error
        return self.response

    @property
    def was_called(self) -> bool:
        return bool(self.calls)


class ScriptedPolicy:
    """Returns prepared outcomes, so gate branches can be driven directly."""

    def __init__(self, request: PolicyOutcome, result: PolicyOutcome | None = None) -> None:
        self.request = request
        self.result = result
        self.seen: list[tuple[str, str, dict[str, Any]]] = []

    async def evaluate_action(
        self, server_id: str, tool: str, arguments: Mapping[str, Any], timestamp: str, **context: Any
    ) -> PolicyOutcome:
        self.seen.append(("request", tool, dict(arguments)))
        return self.request

    async def evaluate_action_result(
        self, server_id: str, tool: str, result: Mapping[str, Any], timestamp: str, **context: Any
    ) -> PolicyOutcome:
        self.seen.append(("response", tool, dict(result)))
        assert self.result is not None, "the gate reached the response leg unexpectedly"
        return self.result


@pytest.fixture(scope="session")
def compliance_map() -> Any:
    return load_compliance_map(DEFAULT_MAP)


@pytest.fixture(scope="session")
def manifests() -> dict[str, Any]:
    """Packaged manifests plus the demo fixture, exactly as --manifest supplies it."""
    return load_manifests((DEMO_MANIFEST,))


@pytest.fixture
def engine(compliance_map: Any, manifests: dict[str, Any]) -> ActionEngine:
    return ActionEngine(compliance_map, manifests)


@pytest.fixture
def policy(engine: ActionEngine, compliance_map: Any) -> InProcessPolicyClient:
    return InProcessPolicyClient(engine, compliance_map.version)


@pytest.fixture
def demo_manifest() -> Any:
    return load_manifest(DEMO_MANIFEST)


def build_gate(policy: Any, upstream: Any, server_id: str = "demo-paas", **context: Any) -> Gate:
    return Gate(
        policy=policy,
        upstream=upstream,
        server_id=server_id,
        clock=fixed_clock,
        context=context or {"sector": "development"},
    )
