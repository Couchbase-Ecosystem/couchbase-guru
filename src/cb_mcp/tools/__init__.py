"""
Couchbase MCP Tools.

This server exposes the Couchbase documentation search tool. Additional tools
can be registered by appending to ``TOOLS`` and adding their annotations.
"""

from collections.abc import Callable

from mcp.types import ToolAnnotations

# Docs / API reference tool
from .docs import ask_couchbase_docs

# All tools exposed by the server.
TOOLS: list[Callable] = [
    ask_couchbase_docs,
]

# Backwards-compatible alias.
ALL_TOOLS = TOOLS

# Tool annotations for MCP clients (readOnlyHint, destructiveHint, etc.)
TOOL_ANNOTATIONS: dict[str, ToolAnnotations] = {
    "ask_couchbase_docs": ToolAnnotations(readOnlyHint=True),
}


def get_tools() -> list[Callable]:
    """Return the list of tools to register with the MCP server."""
    return list(TOOLS)


__all__ = [
    "ask_couchbase_docs",
    "TOOLS",
    "ALL_TOOLS",
    "TOOL_ANNOTATIONS",
    "get_tools",
]
