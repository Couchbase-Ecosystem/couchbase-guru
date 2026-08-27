"""
Unit tests for the agent backend client (cb_mcp.utils.agent).

Covers device-id derivation (stdio persisted + HTTP IP hashing), IP
pseudonymization, call_agent request building + error mapping, and answer
extraction. No network is used — HTTP is mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import httpx
import pytest

from cb_mcp.utils import agent, config


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    """Isolate the on-disk device id / salt, settings, and caches per test."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.delenv("CB_AGENT_BASE_URL", raising=False)
    # A dummy agent URL so call_agent-path tests can resolve one; HTTP is mocked.
    config.set_settings({"agent_base_url": "http://agent.test"})
    agent._persisted_device_id.cache_clear()
    agent._ip_hash_salt.cache_clear()
    yield
    config.set_settings({})
    agent._persisted_device_id.cache_clear()
    agent._ip_hash_salt.cache_clear()


# --------------------------------------------------------------------------
# Persisted device id (stdio)
# --------------------------------------------------------------------------


def test_persisted_device_id_stable_across_restart():
    first = agent._persisted_device_id()
    agent._persisted_device_id.cache_clear()  # simulate a fresh process
    second = agent._persisted_device_id()
    assert first == second
    assert first.startswith("mcp-")


def test_persisted_device_id_unique_per_device(tmp_path, monkeypatch):
    first = agent._persisted_device_id()
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "other-device"))
    agent._persisted_device_id.cache_clear()
    assert agent._persisted_device_id() != first


def test_persisted_device_id_fallback_when_unwritable(tmp_path, monkeypatch):
    # Parent is a file, so mkdir()/write_text() raise OSError -> fallback id.
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    monkeypatch.setattr(agent, "_device_id_file", lambda: blocker / "sub" / "id")
    agent._persisted_device_id.cache_clear()
    val = agent._persisted_device_id()
    assert val.startswith("mcp-")


# --------------------------------------------------------------------------
# Transport routing: device_user_id()
# --------------------------------------------------------------------------


def test_device_user_id_stdio_uses_persisted(monkeypatch):
    def _no_http():
        raise RuntimeError("No active HTTP request found.")

    monkeypatch.setattr(agent, "get_http_request", _no_http)
    assert agent.device_user_id() == agent._persisted_device_id()


def test_device_user_id_http_uses_hashed_ip(monkeypatch):
    req = SimpleNamespace(client=SimpleNamespace(host="203.0.113.7"), headers={})
    monkeypatch.setattr(agent, "get_http_request", lambda: req)
    uid = agent.device_user_id()
    assert uid.startswith("mcp-ip-")
    assert "203.0.113.7" not in uid  # raw IP is not exposed


# --------------------------------------------------------------------------
# IP pseudonymization
# --------------------------------------------------------------------------


def test_hash_ip_is_deterministic():
    assert agent._hash_ip("1.2.3.4") == agent._hash_ip("1.2.3.4")


def test_hash_ip_differs_by_ip():
    assert agent._hash_ip("1.2.3.4") != agent._hash_ip("5.6.7.8")


def test_hash_ip_salt_changes_output():
    before = agent._hash_ip("1.2.3.4")
    config.set_settings({"agent_ip_salt": "a-different-secret"})
    agent._ip_hash_salt.cache_clear()
    assert agent._hash_ip("1.2.3.4") != before


# --------------------------------------------------------------------------
# call_agent: request building + error mapping (HTTP mocked)
# --------------------------------------------------------------------------


class _FakeResp:
    def __init__(
        self,
        status: int,
        text: str = "",
        json_data: dict | None = None,
        headers: dict | None = None,
    ):
        self.status_code = status
        self.text = text
        self._json = json_data if json_data is not None else {}
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                str(self.status_code),
                request=httpx.Request("POST", "http://agent.test/docs/rag_chat"),
                response=self,
            )

    def json(self):
        return self._json


def _mock_post(monkeypatch, resp=None, exc=None, capture=None):
    def fake_post(url, json=None, headers=None, timeout=None, follow_redirects=None):
        if capture is not None:
            capture["url"] = url
            capture["body"] = json
            capture["headers"] = headers or {}
        if exc is not None:
            raise exc
        return resp

    monkeypatch.setattr(agent.httpx, "post", fake_post)


def test_call_agent_success_returns_body(monkeypatch):
    capture: dict = {}
    _mock_post(
        monkeypatch, resp=_FakeResp(200, json_data={"content": "hi"}), capture=capture
    )
    body = agent.call_agent(content="what is a bucket?", user_id="dev-1")
    assert body["content"] == "hi"
    # RAG chat endpoint contract: snake_case keys, "messages" carries the query.
    assert capture["body"]["data"]["messages"] == "what is a bucket?"
    assert capture["body"]["data"]["user_id"] == "dev-1"


def test_call_agent_targets_rag_chat_endpoint(monkeypatch):
    capture: dict = {}
    _mock_post(
        monkeypatch, resp=_FakeResp(200, json_data={"content": "x"}), capture=capture
    )
    agent.call_agent(content="q", user_id="dev-1")
    assert capture["url"].endswith("/docs/rag_chat")


def test_call_agent_sets_user_agent_with_device_id(monkeypatch):
    capture: dict = {}
    _mock_post(
        monkeypatch, resp=_FakeResp(200, json_data={"content": "x"}), capture=capture
    )
    agent.call_agent(content="q", user_id="mcp-ip-abc123")
    ua = capture["headers"].get("User-Agent", "")
    assert ua.startswith("couchbase-guru/")
    assert "device/mcp-ip-abc123" in ua  # device id is carried for WAF aggregation


def test_call_agent_userid_defaults_non_empty(monkeypatch):
    capture: dict = {}
    _mock_post(
        monkeypatch, resp=_FakeResp(200, json_data={"content": "x"}), capture=capture
    )
    agent.call_agent(content="q", user_id="")
    assert capture["body"]["data"]["user_id"]  # falls back to a non-empty default


def test_call_agent_5xx_gives_clean_message(monkeypatch):
    _mock_post(monkeypatch, resp=_FakeResp(502, "<html>502 Bad Gateway</html>"))
    with pytest.raises(RuntimeError, match="temporarily unavailable"):
        agent.call_agent(content="q")


def test_call_agent_4xx_keeps_detail(monkeypatch):
    _mock_post(monkeypatch, resp=_FakeResp(422, '{"detail":"userId required"}'))
    with pytest.raises(RuntimeError, match="422"):
        agent.call_agent(content="q")


def test_call_agent_429_gives_rate_limit_message(monkeypatch):
    _mock_post(
        monkeypatch,
        resp=_FakeResp(429, "Too Many Requests", headers={"Retry-After": "30"}),
    )
    with pytest.raises(RuntimeError, match=r"rate limiting requests.*retry after 30"):
        agent.call_agent(content="q")


def test_call_agent_connection_error(monkeypatch):
    _mock_post(monkeypatch, exc=httpx.ConnectError("no route"))
    with pytest.raises(ConnectionError):
        agent.call_agent(content="q")


def test_call_agent_timeout(monkeypatch):
    _mock_post(monkeypatch, exc=httpx.ReadTimeout("slow"))
    with pytest.raises(RuntimeError, match="timed out"):
        agent.call_agent(content="q")


def test_call_agent_surfaces_server_error_field(monkeypatch):
    _mock_post(monkeypatch, resp=_FakeResp(200, json_data={"error": "boom"}))
    with pytest.raises(RuntimeError, match="boom"):
        agent.call_agent(content="q")


# --------------------------------------------------------------------------
# extract_answer
# --------------------------------------------------------------------------


def test_extract_answer_uses_content():
    assert agent.extract_answer({"content": "the answer"}) == "the answer"


def test_extract_answer_falls_back_to_dump():
    out = agent.extract_answer({"unexpected": "shape"})
    assert "unexpected" in out


def test_format_sources_empty_when_absent():
    assert agent.format_sources({"content": "x"}) == ""
    assert agent.format_sources({"doc_source_urls": []}) == ""


def test_format_sources_lists_urls_in_order():
    out = agent.format_sources({"doc_source_urls": ["https://a", "https://b"]})
    assert "**Sources:**" in out
    assert "- https://a" in out
    assert "- https://b" in out
    assert out.index("https://a") < out.index("https://b")  # backend order preserved


# --------------------------------------------------------------------------
# Agent base URL (server configuration)
# --------------------------------------------------------------------------


def test_agent_base_url_from_settings():
    config.set_settings({"agent_base_url": "https://agent.example.test"})
    assert agent.get_agent_base_url() == "https://agent.example.test"


def test_agent_base_url_ignores_raw_env(monkeypatch):
    # CB_AGENT_BASE_URL is resolved by Click into the settings, not read here
    # directly — so a bare env var with nothing in settings does not apply.
    config.set_settings({})
    monkeypatch.setenv("CB_AGENT_BASE_URL", "https://from-env.example")
    assert agent.get_agent_base_url() == agent.DEFAULT_AGENT_BASE_URL


def test_agent_base_url_defaults_when_unset(monkeypatch):
    config.set_settings({})
    monkeypatch.delenv("CB_AGENT_BASE_URL", raising=False)
    assert agent.get_agent_base_url() == agent.DEFAULT_AGENT_BASE_URL
