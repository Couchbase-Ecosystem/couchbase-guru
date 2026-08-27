"""
Shared fixtures and utilities for MCP server integration tests.

Integration tests spawn the docs MCP server over stdio and exercise the
``ask_couchbase_docs`` tool against the live agent backend. They are opt-in:
set ``CB_MCP_RUN_INTEGRATION=1`` to run them.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

# Tools we expect the server to register.
EXPECTED_TOOLS = {
    "ask_couchbase_docs",
}

# Default timeout (seconds) to guard against hangs when the agent backend
# is unreachable or slow. Override with CB_MCP_TEST_TIMEOUT if needed.
DEFAULT_TIMEOUT = int(os.getenv("CB_MCP_TEST_TIMEOUT", "120"))


def _build_env() -> dict[str, str]:
    """Build the environment passed to the test server process."""
    if not os.getenv("CB_MCP_RUN_INTEGRATION"):
        pytest.skip(
            "Integration tests are opt-in. Set CB_MCP_RUN_INTEGRATION=1 to run "
            "them against the agent backend (the built-in public default, or "
            "CB_AGENT_BASE_URL if set)."
        )

    env = os.environ.copy()

    # Ensure the server module can be imported from the repo's src/ folder
    existing_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{SRC_DIR}{os.pathsep}{existing_path}" if existing_path else str(SRC_DIR)
    )

    # Force stdio transport for the test server to match stdio_client
    env["CB_MCP_TRANSPORT"] = "stdio"
    # Ensure unbuffered output to avoid stdout/stderr buffering surprises
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


@asynccontextmanager
async def create_mcp_session() -> AsyncIterator[ClientSession]:
    """Create a fresh MCP client session connected to the server over stdio."""
    env = _build_env()
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server"],
        env=env,
    )

    async with asyncio.timeout(DEFAULT_TIMEOUT):
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session


def extract_payload(response: Any) -> Any:
    """Extract a usable payload from a tool response.

    MCP tool responses can return data in different formats:
    - A single content block with JSON-encoded data (dict, list, etc.)
    - Multiple content blocks, one per list item (for list returns)

    This function handles both cases.
    """
    content = getattr(response, "content", None) or []
    if not content:
        return None

    # If there are multiple content blocks, collect them all as a list
    if len(content) > 1:
        items = []
        for block in content:
            text = getattr(block, "text", None)
            if text is not None:
                try:
                    items.append(json.loads(text))
                except json.JSONDecodeError:
                    items.append(text)
        return items if items else None

    # Single content block - try to parse as JSON
    first = content[0]
    raw = getattr(first, "text", None)
    if raw is None and hasattr(first, "data"):
        raw = first.data

    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    return raw
