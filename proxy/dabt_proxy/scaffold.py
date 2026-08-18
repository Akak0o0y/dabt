"""Draft a tool manifest from a live MCP server's own tool list.

This is the onboarding path for a new organisation: point it at their MCP
server, get a manifest skeleton, hand it to someone who reviews each line.

Everything it emits is a guess, and it says so in the file it writes. Every
entry is `needs_verification`, which the compliance map turns into a hard floor:
`ACTION-DEFAULT-ALLOW-NO-FINDING` requires `tool_confidence: verified`, so a
scaffolded manifest resolves every call to REVIEW until a human raises it. An
inaccurate draft therefore fails safe - it cannot permit anything.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

# Verb prefixes to operations. A guess from a name, which is why nothing here is
# ever emitted as verified.
_OPERATION_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("create", "add", "new", "provision", "deploy", "insert", "upload"), "create"),
    (("get", "list", "read", "fetch", "describe", "search", "query", "show", "find"), "read"),
    (("update", "set", "patch", "edit", "modify", "rename", "configure"), "update"),
    (("delete", "remove", "destroy", "drop", "purge", "revoke"), "delete"),
)

_REGION_HINTS = ("region", "location", "zone", "datacenter", "datacentre", "availability_zone")
_REFERENCE_SUFFIXES = ("_id", "_ref", "_uuid", "_arn", "_key")
_NAME_HINTS = ("name", "title", "slug", "label")
_CREDENTIAL_HINTS = (
    "password",
    "secret",
    "token",
    "credential",
    "connection_string",
    "api_key",
    "apikey",
    "private_key",
)


def infer_operation(tool_name: str) -> str:
    lowered = tool_name.lower()
    for prefixes, operation in _OPERATION_HINTS:
        if any(lowered.startswith(prefix) or f"_{prefix}" in lowered for prefix in prefixes):
            return operation
    return "execute"


def infer_parameter_role(name: str) -> str:
    lowered = name.lower()
    if any(hint in lowered for hint in _REGION_HINTS):
        return "deployment_region"
    if any(hint in lowered for hint in _CREDENTIAL_HINTS):
        return "credential_reference"
    if lowered.endswith(_REFERENCE_SUFFIXES) or lowered in {"id", "ref"}:
        return "resource_reference"
    if any(hint == lowered or lowered.endswith(f"_{hint}") for hint in _NAME_HINTS):
        return "resource_name"
    return "opaque_payload"


def infer_return_role(name: str) -> str:
    lowered = name.lower()
    if any(hint in lowered for hint in _CREDENTIAL_HINTS):
        return "credential"
    if lowered in {"id", "name", "status", "created_at", "updated_at"}:
        return "resource_metadata"
    return "opaque_payload"


def _properties(schema: Any) -> dict[str, Any]:
    if isinstance(schema, Mapping):
        properties = schema.get("properties")
        if isinstance(properties, Mapping):
            return dict(properties)
    return {}


def _is_array(schema: Any) -> bool:
    return isinstance(schema, Mapping) and schema.get("type") == "array"


def _parameter_lines(tool: Any) -> list[str]:
    properties = _properties(getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None))
    if not properties:
        return []
    lines = ["    parameters:"]
    for name in properties:
        role = infer_parameter_role(name)
        # Masking a region or a resource name produces nonsense rather than a
        # redacted call, so only opaque payloads are proposed as maskable.
        maskable = "true" if role == "opaque_payload" else "false"
        lines.append(f"      {name}: {{ role: {role}, maskable: {maskable} }}")
    return lines


def _return_lines(tool: Any) -> list[str]:
    schema = getattr(tool, "output_schema", None) or getattr(tool, "outputSchema", None)
    properties = _properties(schema)
    if not properties:
        # No output schema: the server returns unstructured content blocks. Declaring
        # MCP's own `content` field as an inspected collection is what lets the
        # detectors read a text response at all. Leave it undeclared and every
        # response resolves to REVIEW as an undeclared field.
        return [
            "    returns:",
            "      content:",
            "        role: opaque_payload",
            "        inspect_content: true",
            "        collection: true",
            "        maskable: true",
        ]
    lines = ["    returns:"]
    for name, field_schema in properties.items():
        role = infer_return_role(name)
        lines.append(f"      {name}:")
        lines.append(f"        role: {role}")
        if role == "credential":
            lines.append("        declared_sensitive: true")
        else:
            lines.append("        inspect_content: true")
        if _is_array(field_schema):
            lines.append("        collection: true")
        lines.append("        maskable: true")
    return lines


def draft_manifest(server_id: str, tools: Iterable[Any], source: str) -> str:
    """Render a reviewable manifest draft. Never emits `verified`."""
    tool_list = list(tools)
    lines = [
        f"# DRAFT tool manifest for {server_id}, generated from {source}.",
        "#",
        "# GENERATED, NOT TRANSCRIBED. Every field below except the tool and",
        "# parameter names is inferred from naming and JSON Schema shape. Operation,",
        "# resource_type, persists_data, roles and maskability are guesses that a",
        "# human must check against the vendor's published documentation.",
        "#",
        "# Every entry is needs_verification, and the compliance map's action ALLOW",
        "# rule requires tool_confidence: verified. So this manifest gates every call",
        "# to REVIEW until someone raises an entry deliberately. That is the point:",
        "# an unreviewed draft cannot permit anything.",
        "#",
        "# To put a tool into service: verify its semantics, correct the fields, then",
        "# change its confidence_level to verified.",
        f'version: "0.1.0-{server_id}-draft"',
        "server:",
        f"  id: {server_id}",
        f'  description: "{source}"',
        "",
        "tools:",
    ]

    if not tool_list:
        lines.append(
            "  # The server advertised no tools. A manifest needs at least one entry,"
        )
        lines.append("  # so nothing usable could be generated.")
        return "\n".join(lines) + "\n"

    for tool in tool_list:
        name = getattr(tool, "name", None) or str(tool)
        operation = infer_operation(name)
        description = (getattr(tool, "description", None) or "").strip().splitlines()
        lines.append(f"  {name}:")
        if description:
            lines.append(f"    # upstream description: {description[0][:160]}")
        lines.append(f"    operation: {operation}")
        lines.append("    resource_type: unknown  # REVIEW: name the resource this acts on")
        persists = "true" if operation in {"create", "update", "delete"} else "false"
        lines.append(f"    persists_data: {persists}  # REVIEW: inferred from the operation")
        lines.append("    confidence_level: needs_verification")
        lines.append("    requires_legal_review: true")
        lines.extend(_parameter_lines(tool))
        lines.extend(_return_lines(tool))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
