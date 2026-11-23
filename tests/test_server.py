"""
Offline tests for the assembled MCP server (mcp_server.create_server).

These drive the real server through an in-memory fastmcp Client, so tool
registration, annotations, and the tool call path are covered over the MCP
protocol without spawning a process or reaching the agent backend.
"""

from __future__ import annotations

import pytest
from conftest import EXPECTED_TOOLS
from fastmcp import Client

from cb_mcp.tools import docs
from mcp_server import create_server


@pytest.mark.asyncio
async def test_server_registers_expected_tools_with_annotations():
    async with Client(create_server()) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    assert set(tools) == EXPECTED_TOOLS
    annotations = tools["ask_couchbase_docs"].annotations
    assert annotations is not None
    assert annotations.readOnlyHint is True


@pytest.mark.asyncio
async def test_server_tool_call_returns_answer_with_sources(monkeypatch):
    monkeypatch.setattr(docs, "device_user_id", lambda: "dev-1")
    monkeypatch.setattr(
        docs,
        "call_agent",
        lambda content, user_id: {
            "content": f"answer to: {content}",
            "doc_source_urls": ["https://docs.couchbase.com/a"],
        },
    )

    async with Client(create_server()) as client:
        result = await client.call_tool(
            "ask_couchbase_docs", {"question": "  What is a primary index?  "}
        )

    text = result.content[0].text
    assert text.startswith("answer to: What is a primary index?")
    assert "- https://docs.couchbase.com/a" in text
