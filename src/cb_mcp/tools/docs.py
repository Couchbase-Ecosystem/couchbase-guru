"""
Tools for querying Couchbase documentation and API reference.

This module provides an MCP tool that routes user questions about Couchbase
documentation, SDK usage, configuration, best practices, and API reference
to an agent backend service.  The backend uses the question text to identify
the relevant product categories and versions, so the question must be
self-contained.
"""

import asyncio
import logging
from typing import Annotated, Any

from fastmcp import Context
from pydantic import Field

from cb_mcp.utils.agent import (
    call_agent,
    device_user_id,
    extract_answer,
    format_sources,
)
from cb_mcp.utils.constants import MCP_SERVER_NAME

logger = logging.getLogger(f"{MCP_SERVER_NAME}.tools.docs")

# How often to emit a progress heartbeat while waiting on the agent backend.
# Kept well under common MCP client tool-call timeouts (e.g. Cursor ~30s), which
# reset on each progress notification, so slow RAG searches don't time out.
_PROGRESS_INTERVAL_SECONDS = 5.0


# ---------------------------------------------------------------------------
# Public MCP tool
# ---------------------------------------------------------------------------


async def ask_couchbase_docs(
    ctx: Context,
    question: Annotated[
        str,
        Field(
            description=(
                "A complete, self-contained question about Couchbase products, SDKs, "
                "or services. Must include necessary context like product name, version, "
                "or programming language since the agent called by this tool lacks conversation history."
            ).strip(),
        ),
    ],
) -> str:
    """Search Couchbase documentation to answer questions about any Couchbase product, feature, SDK, service, tutorials or examples.
    Use this tool for all Couchbase how-to, conceptual, and reference questions. Not for direct cluster operations."""
    logger.debug("Docs search - question: %s", question)

    cleaned = question.strip() if question else ""
    if not cleaned:
        return (
            "Error: A question is required. "
            "Please ask a specific question about Couchbase."
        )

    try:
        resp_body = await _search_with_progress(ctx, cleaned)
    except (ConnectionError, RuntimeError) as exc:
        logger.error("Agent call failed: %s", exc)
        return f"Error: {exc}"

    return extract_answer(resp_body) + format_sources(resp_body)


async def _search_with_progress(ctx: Context, question: str) -> dict[str, Any]:
    """Run the blocking agent search in a thread while emitting progress.

    The agent/RAG backend can take tens of seconds. MCP clients reset their
    tool-call timeout when they receive a progress notification, so this
    heartbeat keeps slow searches from timing out (and keeps the HTTP stream
    active). Progress is best-effort — clients that don't request it ignore it.
    """
    search = asyncio.create_task(
        asyncio.to_thread(call_agent, content=question, user_id=device_user_id())
    )
    waited = 0.0
    # Emit an immediate heartbeat, then one every interval until the call returns.
    while True:
        try:
            await ctx.report_progress(
                progress=waited,
                message="Searching Couchbase documentation…",
            )
        except Exception:
            logger.debug("Progress notification not delivered (client opted out)")

        done, _ = await asyncio.wait({search}, timeout=_PROGRESS_INTERVAL_SECONDS)
        if done:
            return search.result()
        waited += _PROGRESS_INTERVAL_SECONDS
