"""Dabt reference MCP gate: a stdio MCP server that gates another MCP server.

Generic by construction. The proxy carries no knowledge of any particular
vendor: which server it gates is a `--server-id` naming an entry in a validated
tool manifest, and a manifest may be supplied from outside the package so a new
organisation can be gated without forking `dabt_core`.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
