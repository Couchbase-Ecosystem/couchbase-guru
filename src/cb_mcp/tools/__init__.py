"""
Couchbase MCP Tools.

This server exposes the Couchbase documentation search tool. Each tool is
declared once in ``_TOOL_SPECS`` together with its MCP annotations, and
:func:`register_tools` is the single place that adds them to a server.
"""

from collections.abc import Callable
from typing import NamedTuple

from fastmcp import FastMCP
from fastmcp.tools import FunctionTool
from mcp.types import ToolAnnotations

# Docs / API reference tool
from .docs import ask_couchbase_docs


class _ToolSpec(NamedTuple):
    """A tool function paired with its MCP annotations."""

    fn: Callable
    annotations: ToolAnnotations


# Every tool exposed by the server, with its annotations for MCP clients
# (readOnlyHint, destructiveHint, etc.). Add new tools here.
_TOOL_SPECS: tuple[_ToolSpec, ...] = (
    _ToolSpec(ask_couchbase_docs, ToolAnnotations(readOnlyHint=True)),
)

# Read-only views derived from _TOOL_SPECS, kept for backwards compatibility.
TOOLS: list[Callable] = [spec.fn for spec in _TOOL_SPECS]
ALL_TOOLS = TOOLS
TOOL_ANNOTATIONS: dict[str, ToolAnnotations] = {
    spec.fn.__name__: spec.annotations for spec in _TOOL_SPECS
}


def get_tools() -> list[Callable]:
    """Return the list of tools to register with the MCP server."""
    return [spec.fn for spec in _TOOL_SPECS]


def register_tools(mcp: FastMCP) -> int:
    """Register every tool, with its annotations, on ``mcp``.

    FastMCP 3.x ``add_tool`` has no annotations kwarg, so each function is
    wrapped in a :class:`FunctionTool` that carries them. Returns the number of
    tools registered.
    """
    for spec in _TOOL_SPECS:
        mcp.add_tool(FunctionTool.from_function(spec.fn, annotations=spec.annotations))
    return len(_TOOL_SPECS)


__all__ = [
    "ask_couchbase_docs",
    "TOOLS",
    "ALL_TOOLS",
    "TOOL_ANNOTATIONS",
    "get_tools",
    "register_tools",
]
