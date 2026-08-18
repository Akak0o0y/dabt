"""Startup validation. A gate that starts misconfigured gates the wrong thing."""

from __future__ import annotations

import pytest
from conftest import DEMO_MANIFEST

from dabt_proxy.__main__ import build_parser
from dabt_proxy.config import ConfigError, config_from_args, load_manifests
from dabt_proxy.upstream import HttpUpstream, StdioUpstream


def parse(*argv: str):
    return build_parser().parse_args(["gate", *argv])


def test_unknown_server_id_refuses_to_start():
    args = parse("--server-id", "nobody", "--upstream-http", "https://example.test/mcp")

    with pytest.raises(ConfigError) as error:
        config_from_args(args)

    message = str(error.value)
    assert "nobody" in message
    # The refusal has to say what to do next, or it is just an obstacle.
    assert "scaffold" in message


def test_missing_upstream_refuses_to_start():
    args = parse("--server-id", "cranl")

    with pytest.raises(ConfigError, match="exactly one upstream"):
        config_from_args(args)


def test_two_upstreams_refuse_to_start():
    args = parse(
        "--server-id",
        "cranl",
        "--upstream-http",
        "https://example.test/mcp",
        "--upstream-stdio",
        "node server.js",
    )

    with pytest.raises(ConfigError, match="exactly one upstream"):
        config_from_args(args)


def test_non_http_upstream_url_refuses_to_start():
    args = parse("--server-id", "cranl", "--upstream-http", "ftp://example.test")

    with pytest.raises(ConfigError, match="http"):
        config_from_args(args)


def test_malformed_upstream_env_refuses_to_start():
    args = parse(
        "--server-id", "cranl", "--upstream-stdio", "node server.js", "--upstream-env", "NOEQUALS"
    )

    with pytest.raises(ConfigError, match="KEY=VALUE"):
        config_from_args(args)


def test_external_manifest_is_loaded_and_gateable():
    """The B2B path: a manifest from outside the package makes its server gateable."""
    args = parse(
        "--server-id",
        "demo-paas",
        "--upstream-http",
        "https://example.test/mcp",
        "--manifest",
        str(DEMO_MANIFEST),
    )

    config = config_from_args(args)

    assert config.manifest.server_id == "demo-paas"
    assert isinstance(config.upstream, HttpUpstream)
    # Packaged manifests remain available alongside it.
    assert "cranl" in config.manifests


def test_external_manifest_overrides_a_packaged_one(tmp_path):
    """A transcribed manifest must be able to supersede a reconstructed one."""
    override = tmp_path / "cranl.yaml"
    override.write_text(
        DEMO_MANIFEST.read_text(encoding="utf-8").replace("id: demo-paas", "id: cranl"),
        encoding="utf-8",
    )

    manifests = load_manifests((override,))

    assert manifests["cranl"].version == "0.1.0-demo-paas"


def test_stdio_command_line_is_split_into_command_and_arguments():
    args = parse("--server-id", "cranl", "--upstream-stdio", "npx -y @acme/mcp-server --port 3000")

    config = config_from_args(args)

    assert isinstance(config.upstream, StdioUpstream)
    assert config.upstream.command == "npx"
    assert config.upstream.args == ("-y", "@acme/mcp-server", "--port", "3000")


def test_declared_context_reaches_the_engine():
    """Sector is a policy input, not a label: it sets the classification floor."""
    args = parse(
        "--server-id",
        "cranl",
        "--upstream-http",
        "https://example.test/mcp",
        "--sector",
        "financial",
        "--agent-id",
        "claude-code-7f2a",
    )

    context = config_from_args(args).context.as_engine_context()

    assert context["sector"] == "financial"
    assert context["agent_id"] == "claude-code-7f2a"
    assert context["agent_authorised"] is True
