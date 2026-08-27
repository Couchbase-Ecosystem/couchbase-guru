"""
Unit tests for the ask_couchbase_docs tool (cb_mcp.tools.docs).

The agent backend is mocked, so no network is used. Covers input validation,
the success path, progress heartbeats, and graceful error handling.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from cb_mcp.tools import docs


class _FakeCtx:
    """Minimal fake Context that records progress notifications."""

    def __init__(self):
        self.progress: list[float] = []

    async def report_progress(self, progress, total=None, message=None):
        self.progress.append(progress)


@pytest.mark.asyncio
async def test_empty_question_returns_error():
    out = await docs.ask_couchbase_docs(_FakeCtx(), "   ")
    assert out.startswith("Error")
    assert "question is required" in out.lower()


@pytest.mark.asyncio
async def test_success_returns_answer(monkeypatch):
    monkeypatch.setattr(docs, "device_user_id", lambda: "dev-1")
    monkeypatch.setattr(
        docs, "call_agent", lambda content, user_id: {"content": "the answer"}
    )
    out = await docs.ask_couchbase_docs(_FakeCtx(), "How do I create a bucket?")
    assert out == "the answer"


@pytest.mark.asyncio
async def test_success_appends_source_urls(monkeypatch):
    monkeypatch.setattr(docs, "device_user_id", lambda: "dev-1")
    monkeypatch.setattr(
        docs,
        "call_agent",
        lambda content, user_id: {
            "content": "the answer",
            "doc_source_urls": [
                "https://docs.couchbase.com/a",
                "https://docs.couchbase.com/b",
            ],
        },
    )
    out = await docs.ask_couchbase_docs(_FakeCtx(), "How do I create a bucket?")
    assert out.startswith("the answer")
    assert "**Sources:**" in out
    assert "https://docs.couchbase.com/a" in out
    assert "https://docs.couchbase.com/b" in out


@pytest.mark.asyncio
async def test_passes_device_user_id_to_agent(monkeypatch):
    captured = {}

    def fake_call_agent(content, user_id):
        captured["content"] = content
        captured["user_id"] = user_id
        return {"content": "ok"}

    monkeypatch.setattr(docs, "device_user_id", lambda: "device-xyz")
    monkeypatch.setattr(docs, "call_agent", fake_call_agent)
    await docs.ask_couchbase_docs(_FakeCtx(), "q")
    assert captured["user_id"] == "device-xyz"
    assert captured["content"] == "q"


@pytest.mark.asyncio
async def test_emits_progress_heartbeat(monkeypatch):
    monkeypatch.setattr(docs, "device_user_id", lambda: "dev-1")
    monkeypatch.setattr(docs, "call_agent", lambda content, user_id: {"content": "a"})
    ctx = _FakeCtx()
    await docs.ask_couchbase_docs(ctx, "q")
    assert len(ctx.progress) >= 1  # at least the initial heartbeat


@pytest.mark.asyncio
async def test_backend_error_returns_error_message(monkeypatch):
    def boom(content, user_id):
        raise RuntimeError("The documentation service is temporarily unavailable.")

    monkeypatch.setattr(docs, "device_user_id", lambda: "dev-1")
    monkeypatch.setattr(docs, "call_agent", boom)
    out = await docs.ask_couchbase_docs(_FakeCtx(), "q")
    assert out.startswith("Error")
    assert "temporarily unavailable" in out
