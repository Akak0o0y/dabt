"""The whole path, over the real protocol.

An MCP client talks to the proxy, the proxy talks to a real MCP server, and both
hops use the actual MCP machinery - no fakes on either side, only an in-process
transport instead of a pipe. This is the demonstration the design promised,
written so it runs on every commit rather than in a meeting.

The harness is an explicit context manager rather than a fixture: the MCP client
and server each own an anyio task group, and an async-generator fixture is torn
down in a different task than it was entered in, which those task groups refuse.
"""

from __future__ import annotations

import io
import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from conftest import fixed_clock
from fixtures.paas_server import ENV_VARS, Recorder, build_server as build_paas
from mcp import Client

from dabt_proxy.gate import Gate
from dabt_proxy.server import AuditSink, build_server
from dabt_proxy.upstream import InProcessUpstream, connect

IBAN = "SA0380000000608010167519"


class Harness:
    def __init__(self, client: Client, recorder: Recorder, audit: io.StringIO) -> None:
        self.client = client
        self.recorder = recorder
        self.audit = audit

    @property
    def audit_records(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.audit.getvalue().splitlines() if line.strip()]


@asynccontextmanager
async def harness(policy: Any) -> AsyncIterator[Harness]:
    """A client attached to the gate, with a real PaaS MCP server behind it."""
    recorder = Recorder()
    audit = io.StringIO()

    async with connect(InProcessUpstream(build_paas(recorder))) as upstream:
        gate = Gate(
            policy=policy,
            upstream=upstream,
            server_id="demo-paas",
            clock=fixed_clock,
            context={"sector": "development"},
        )
        proxy = build_server(gate, AuditSink(stream=audit))
        async with Client(proxy) as client:
            yield Harness(client, recorder, audit)


async def test_tool_discovery_passes_through(policy):
    """An agent must see the upstream's tools, or the gate is just a wall."""
    async with harness(policy) as test:
        listed = await test.client.list_tools()

    assert {tool.name for tool in listed.tools} == {
        "create_database",
        "list_env_vars",
        "set_env_var",
        "delete_database",
    }


async def test_out_of_kingdom_provisioning_is_stopped_before_it_runs(policy):
    """The headline: the agent asks, and the call never reaches the server."""
    async with harness(policy) as test:
        result = await test.client.call_tool(
            "create_database", {"region": "eu-west-1", "name": "customers"}
        )
        calls = list(test.recorder.calls)

    assert result.is_error is True
    assert "PDPL-ART29-2C-INFERRED-RESIDENCY" in result.content[0].text
    assert calls == [], "nothing should have reached the PaaS server"


async def test_the_credential_stops_at_the_boundary(policy):
    """The write happens, and the connection string still does not reach the model."""
    async with harness(policy) as test:
        result = await test.client.call_tool(
            "create_database", {"region": "me-central-1", "name": "customers"}
        )
        called = list(test.recorder.called_tools)

    assert called == ["create_database"], "the write was permitted"
    assert result.is_error is True
    text = result.content[0].text
    assert "NCA-ECC-CREDENTIAL-DISCLOSURE" in text
    assert "s3cr3t" not in text
    assert "s3cr3t" not in json.dumps(result.structured_content, ensure_ascii=False)


async def test_a_regulated_value_is_masked_in_both_halves_of_the_response(policy):
    """The response leg releases the clean variables and masks only the IBAN."""
    async with harness(policy) as test:
        result = await test.client.call_tool("list_env_vars", {"app_id": "app-1"})

    assert result.is_error is False
    serialised = json.dumps(
        {
            "structured": result.structured_content,
            "content": [block.text for block in result.content],
        },
        ensure_ascii=False,
    )
    assert IBAN not in serialised, "the IBAN must not survive in either half"
    assert "PORT=8080" in serialised, "clean variables should still be readable"
    assert "masked, not the originals" in " ".join(block.text for block in result.content)


async def test_a_clean_call_round_trips_untouched(policy):
    async with harness(policy) as test:
        result = await test.client.call_tool("delete_database", {"name": "staging"})
        called = list(test.recorder.called_tools)

    assert result.is_error is False
    assert result.structured_content == {"status": "deleted"}
    assert called == ["delete_database"]


async def test_a_masked_argument_is_what_the_server_stores(policy):
    """Redaction on the request leg must change what the upstream actually receives."""
    async with harness(policy) as test:
        result = await test.client.call_tool("set_env_var", {"key": "PAYOUT", "value": IBAN})
        received = dict(test.recorder.calls[0][1])

    assert result.is_error is False
    assert IBAN not in received["value"]
    assert ENV_VARS["PAYOUT"] == received["value"]


async def test_every_call_leaves_a_bilingual_audit_record(policy):
    async with harness(policy) as test:
        await test.client.call_tool("create_database", {"region": "eu-west-1", "name": "c"})
        await test.client.call_tool("delete_database", {"name": "staging"})
        records = test.audit_records

    assert len(records) == 2
    for record in records:
        assert record["reason_en"] and record["reason_ar"]
        assert record["legal_review_disclaimer_en"] and record["legal_review_disclaimer_ar"]
        assert record["policy_map_version"] and record["manifest_version"]


async def test_the_audit_trail_never_contains_the_withheld_value(policy):
    async with harness(policy) as test:
        await test.client.call_tool("create_database", {"region": "me-central-1", "name": "c"})
        await test.client.call_tool("list_env_vars", {"app_id": "app-1"})
        trail = test.audit.getvalue()

    assert "s3cr3t" not in trail
    assert IBAN not in trail
