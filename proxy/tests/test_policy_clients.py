"""Both routes to the engine: in-process, and over HTTP to the FastAPI service."""

from __future__ import annotations

import os
from dataclasses import replace
from typing import Any

import httpx
import pytest
from conftest import FIXTURES, FIXED_TIME, FakeUpstream, build_gate

from dabt_proxy.outcome import ToolResponse
from dabt_proxy.policy import HttpPolicyClient, InProcessPolicyClient

IBAN = "SA0380000000608010167519"


@pytest.fixture
def service_app(monkeypatch: pytest.MonkeyPatch) -> Any:
    """The real FastAPI app, told to also load the demo fixture manifest."""
    monkeypatch.setenv("DABT_MANIFEST_DIRS", str(FIXTURES))
    import importlib

    import dabt_api.main as main

    return importlib.reload(main).app


@pytest.fixture
def http_policy(service_app: Any) -> HttpPolicyClient:
    async def post(url: str, body: dict[str, Any]) -> Any:
        transport = httpx.ASGITransport(app=service_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://service") as client:
            response = await client.post(url, json=body)
            response.raise_for_status()
            return response.json()

    return HttpPolicyClient("", post)


async def test_service_loads_manifests_from_outside_the_package(service_app: Any) -> None:
    """The B2B path: an organisation supplies its own manifest by directory."""
    import dabt_api.main as main

    assert "demo-paas" in main.MANIFESTS


@pytest.mark.parametrize(
    ("tool", "arguments", "expected_decision", "expected_rule"),
    [
        (
            "create_database",
            {"region": "eu-west-1", "name": "customers"},
            "REVIEW",
            "PDPL-ART29-2C-INFERRED-RESIDENCY",
        ),
        ("delete_database", {"name": "production"}, "ALLOW", "ACTION-DEFAULT-ALLOW-NO-FINDING"),
        (
            "set_env_var",
            {"key": "BILLING", "value": IBAN},
            "ALLOW_WITH_REDACTION",
            "PDPL-ART11-3-MINIMISATION",
        ),
    ],
)
async def test_transports_agree(
    policy: InProcessPolicyClient,
    http_policy: HttpPolicyClient,
    tool: str,
    arguments: dict[str, Any],
    expected_decision: str,
    expected_rule: str,
) -> None:
    """One behaviour, two transports. A shared parser is why they cannot drift."""
    in_process = await policy.evaluate_action("demo-paas", tool, arguments, FIXED_TIME)
    over_http = await http_policy.evaluate_action("demo-paas", tool, arguments, FIXED_TIME)

    assert in_process.decision == over_http.decision == expected_decision
    assert in_process.decision_rule_id == over_http.decision_rule_id == expected_rule
    assert in_process.released_arguments == over_http.released_arguments
    assert in_process.rewritten == over_http.rewritten


async def test_http_client_denies_when_the_service_is_unreachable() -> None:
    """Fail closed: an unavailable gate must not become an open one."""

    async def post(url: str, body: dict[str, Any]) -> Any:
        raise httpx.ConnectError("connection refused")

    client = HttpPolicyClient("http://127.0.0.1:1", post)
    outcome = await client.evaluate_action("demo-paas", "delete_database", {}, FIXED_TIME)

    assert outcome.decision == "DENY"
    assert outcome.service_error is True
    assert outcome.releases is False
    assert outcome.detail_en and outcome.detail_ar


async def test_http_client_denies_on_an_unparseable_response() -> None:
    async def post(url: str, body: dict[str, Any]) -> Any:
        return {"unexpected": "shape"}

    client = HttpPolicyClient("http://service", post)
    outcome = await client.evaluate_action("demo-paas", "delete_database", {}, FIXED_TIME)

    assert outcome.decision == "DENY"
    assert outcome.service_error is True


async def test_in_process_client_denies_when_the_engine_raises(compliance_map: Any) -> None:
    class ExplodingEngine:
        def evaluate(self, *_: Any, **__: Any) -> Any:
            raise RuntimeError("map corrupted")

        def evaluate_result(self, *_: Any, **__: Any) -> Any:
            raise RuntimeError("map corrupted")

    client = InProcessPolicyClient(ExplodingEngine(), compliance_map.version)  # type: ignore[arg-type]

    request = await client.evaluate_action("demo-paas", "delete_database", {}, FIXED_TIME)
    result = await client.evaluate_action_result("demo-paas", "delete_database", {}, FIXED_TIME)

    assert request.decision == result.decision == "DENY"
    assert request.service_error and result.service_error


async def test_a_failing_policy_service_blocks_the_call(compliance_map: Any) -> None:
    """The gate's contract, not just the client's: no evaluation means no call."""

    async def post(url: str, body: dict[str, Any]) -> Any:
        raise httpx.ConnectError("connection refused")

    upstream = FakeUpstream()
    gate = build_gate(HttpPolicyClient("http://127.0.0.1:1", post), upstream)

    outcome = await gate.call_tool("delete_database", {"name": "production"})

    assert outcome.blocked is True
    assert outcome.decision == "DENY"
    assert upstream.calls == []
