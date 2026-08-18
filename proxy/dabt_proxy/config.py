"""Configuration, validated before the gate accepts a single call.

A gate that starts misconfigured is worse than one that refuses to start: the
first silently gates the wrong thing, the second tells an operator what to fix.
So every check here is a startup failure, never a runtime default.

The manifest search path is what makes this generic. `dabt_core` ships manifests
it knows about, and `--manifest` adds more from anywhere on disk, so a new
organisation is gated by writing a YAML file - not by forking the engine.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import dabt_core
from dabt_core.action import ActionEngine
from dabt_core.loader import load_compliance_map
from dabt_core.manifest import ToolManifest, load_manifest

from .upstream import HttpUpstream, StdioUpstream, UpstreamTarget

CORE_DATA = Path(dabt_core.__file__).parent / "data"
DEFAULT_MAP = CORE_DATA / "compliance_map.yaml"
DEFAULT_MANIFEST_DIR = CORE_DATA / "manifests"


class ConfigError(ValueError):
    """The gate cannot be started as configured."""


@dataclass(frozen=True)
class EvaluationContext:
    """The declared circumstances of the calls this gate will evaluate.

    These are inputs to the policy engine, not decorations: `sector` selects the
    NDMO classification floor, and `lawful_basis` is read by PDPL rules. A
    deployment that misstates them gets decisions about a situation it is not in.
    """

    agent_id: str = "dabt-proxy"
    purpose: str = "action"
    lawful_basis: str = "consent"
    sector: str = "development"
    agent_authorised: bool = True
    requires_minimisation: bool = True

    def as_engine_context(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "purpose": self.purpose,
            "lawful_basis": self.lawful_basis,
            "sector": self.sector,
            "agent_authorised": self.agent_authorised,
            "requires_minimisation": self.requires_minimisation,
        }


@dataclass(frozen=True)
class ProxyConfig:
    server_id: str
    upstream: UpstreamTarget
    manifests: Mapping[str, ToolManifest]
    compliance_map: Any
    context: EvaluationContext = field(default_factory=EvaluationContext)
    policy_url: str | None = None
    audit_log: Path | None = None

    @property
    def manifest(self) -> ToolManifest:
        return self.manifests[self.server_id]

    def build_engine(self) -> ActionEngine:
        return ActionEngine(self.compliance_map, self.manifests)


def load_manifests(extra: Sequence[Path] = ()) -> dict[str, ToolManifest]:
    """Load the packaged manifests, then any supplied from outside the package.

    A later path wins on a server_id collision, so an operator can override a
    packaged manifest with a transcribed one without editing the package.
    """
    manifests: dict[str, ToolManifest] = {}
    packaged = sorted(DEFAULT_MANIFEST_DIR.glob("*.yaml")) if DEFAULT_MANIFEST_DIR.is_dir() else []
    for path in (*packaged, *extra):
        manifest = load_manifest(path)
        manifests[manifest.server_id] = manifest
    return manifests


def upstream_from_args(args: argparse.Namespace) -> UpstreamTarget:
    stdio, http = args.upstream_stdio, args.upstream_http
    if bool(stdio) == bool(http):
        raise ConfigError(
            "specify exactly one upstream: --upstream-stdio '<command>' or --upstream-http <url>"
        )
    if http:
        if not http.startswith(("http://", "https://")):
            raise ConfigError(f"--upstream-http must be an http(s) URL; got {http!r}")
        return HttpUpstream(url=http)

    env: dict[str, str] = {}
    for item in args.upstream_env or ():
        key, separator, value = item.partition("=")
        if not separator or not key:
            raise ConfigError(f"--upstream-env expects KEY=VALUE; got {item!r}")
        env[key] = value
    return StdioUpstream.from_command_line(stdio, env=env or None, cwd=args.upstream_cwd)


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--server-id",
        required=True,
        help="Manifest server id governing this upstream, e.g. the value under server.id",
    )
    parser.add_argument("--upstream-stdio", help="Command line of an MCP server to spawn")
    parser.add_argument("--upstream-http", help="URL of a streamable-HTTP MCP server")
    parser.add_argument(
        "--upstream-env", action="append", metavar="KEY=VALUE", help="Env var for a spawned upstream"
    )
    parser.add_argument("--upstream-cwd", help="Working directory for a spawned upstream")
    parser.add_argument(
        "--manifest",
        action="append",
        type=Path,
        metavar="PATH",
        help="Additional tool manifest to load; repeatable. Overrides a packaged manifest "
        "with the same server id.",
    )
    parser.add_argument("--compliance-map", type=Path, default=DEFAULT_MAP)


def add_gate_arguments(parser: argparse.ArgumentParser) -> None:
    add_common_arguments(parser)
    parser.add_argument(
        "--policy-url",
        help="Evaluate over HTTP against a running Dabt service instead of in-process. "
        "Note the service gates against the manifests it loaded, not --manifest.",
    )
    parser.add_argument("--audit-log", type=Path, help="Append bilingual audit records as JSON lines")
    parser.add_argument("--agent-id", default=EvaluationContext.agent_id)
    parser.add_argument("--purpose", default=EvaluationContext.purpose)
    parser.add_argument("--lawful-basis", default=EvaluationContext.lawful_basis)
    parser.add_argument(
        "--sector",
        default=EvaluationContext.sector,
        help="Declared sector; sets the NDMO classification floor for every gated call",
    )
    parser.add_argument("--agent-unauthorised", action="store_true")
    parser.add_argument("--no-minimisation", action="store_true")


def config_from_args(args: argparse.Namespace) -> ProxyConfig:
    """Build a validated configuration, or refuse with a reason."""
    upstream = upstream_from_args(args)

    try:
        compliance_map = load_compliance_map(args.compliance_map)
    except Exception as error:  # noqa: BLE001 - surfaced as a startup refusal
        raise ConfigError(f"compliance map could not be loaded: {error}") from error

    try:
        manifests = load_manifests(tuple(args.manifest or ()))
    except Exception as error:  # noqa: BLE001
        raise ConfigError(f"tool manifest could not be loaded: {error}") from error

    if args.server_id not in manifests:
        known = ", ".join(sorted(manifests)) or "none"
        raise ConfigError(
            f"no manifest declares server id {args.server_id!r} (loaded: {known}). "
            f"Write one, or generate a draft with: dabt-proxy scaffold --server-id "
            f"{args.server_id} ..."
        )

    context = EvaluationContext(
        agent_id=getattr(args, "agent_id", EvaluationContext.agent_id),
        purpose=getattr(args, "purpose", EvaluationContext.purpose),
        lawful_basis=getattr(args, "lawful_basis", EvaluationContext.lawful_basis),
        sector=getattr(args, "sector", EvaluationContext.sector),
        agent_authorised=not getattr(args, "agent_unauthorised", False),
        requires_minimisation=not getattr(args, "no_minimisation", False),
    )

    return ProxyConfig(
        server_id=args.server_id,
        upstream=upstream,
        manifests=manifests,
        compliance_map=compliance_map,
        context=context,
        policy_url=getattr(args, "policy_url", None),
        audit_log=getattr(args, "audit_log", None),
    )
