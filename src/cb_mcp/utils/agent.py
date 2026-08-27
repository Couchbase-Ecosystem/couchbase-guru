"""
Agent backend client.

Provides helpers for communicating with the external agent
(LLM-backed) service. Every MCP tool that needs to reach the
agent backend should go through :func:`call_agent` so that
HTTP calls, error handling, and configuration are centralised in one
place.

Configuration
-------------
The agent service base URL defaults to the public documentation agent
(:data:`~cb_mcp.utils.constants.DEFAULT_AGENT_BASE_URL`). Operators running
their own agent can override it via the ``--agent-base-url`` CLI option or the
``CB_AGENT_BASE_URL`` environment variable.
"""

import functools
import hashlib
import hmac
import json
import logging
import os
import uuid
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Any

import httpx
from fastmcp.server.dependencies import get_http_request

from cb_mcp.utils.config import get_settings
from cb_mcp.utils.constants import DEFAULT_AGENT_BASE_URL, MCP_SERVER_NAME

logger = logging.getLogger(f"{MCP_SERVER_NAME}.utils.agent")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_RAG_CHAT_ENDPOINT = "/docs/rag_chat"
_REQUEST_TIMEOUT_SECONDS = 120  # generous timeout for LLM-backed agents
# The agent backend requires a non-empty userId. There is no end-user identity
# for an MCP server, so requests are attributed to a stable service identifier.
_DEFAULT_USER_ID = "mcp-server"

# The distribution name (pyproject ``[project].name``) equals MCP_SERVER_NAME, so
# the server name, User-Agent product token, and version lookup share one source.
try:
    _MCP_VERSION = _pkg_version(MCP_SERVER_NAME)
except PackageNotFoundError:  # not installed as a distribution (e.g. source checkout)
    _MCP_VERSION = "0"


def _user_agent(user_id: str) -> str:
    """Build a structured ``User-Agent`` carrying the per-device id.

    AWS WAF rate-based rules can aggregate on this header (ideally paired with
    the source IP as a composite key), so the device id doubles as the
    rate-limit signal. The value is a well-formed UA string — ``product/version
    (device/<id>)`` — rather than a bare token, so it does not trip bot/managed
    rule detections the way an opaque User-Agent would.
    """
    return f"{MCP_SERVER_NAME}/{_MCP_VERSION} (device/{user_id or _DEFAULT_USER_ID})"


def get_agent_base_url() -> str:
    """Return the resolved agent base URL.

    Reads the ``agent_base_url`` setting, which the server entrypoint populates
    from the ``--agent-base-url`` option — Click also sources that option from the
    ``CB_AGENT_BASE_URL`` environment variable, so the env var is honoured without
    being read again here. Falls back to the built-in public default
    (``DEFAULT_AGENT_BASE_URL``) when unset.
    """
    return get_settings().get("agent_base_url") or DEFAULT_AGENT_BASE_URL


def _device_id_file() -> Path:
    """Resolve the per-user file that stores this device's id.

    Uses XDG_DATA_HOME on Linux/macOS and LOCALAPPDATA on Windows, falling
    back to ``~/.local/share`` / the home directory.
    """
    if os.name == "nt":
        base: str | Path = os.environ.get("LOCALAPPDATA") or Path.home()
    else:
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / "couchbase-guru" / "device_id"


@functools.lru_cache(maxsize=1)
def _persisted_device_id() -> str:
    """Stable per-device id persisted to a per-user file (stdio transport).

    A random id is generated once and persisted, so the same device reports the
    same id across reconnects and restarts. Only meaningful for stdio, where the
    server runs locally on the device. When the id cannot be persisted (e.g. a
    read-only filesystem), a process-lifetime id is used instead — still valid,
    but not stable across restarts.
    """
    path = _device_id_file()
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except OSError:
        pass

    device_id = f"mcp-{uuid.uuid4().hex}"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(device_id, encoding="utf-8")
        logger.info("Generated a new device id and stored it at %s", path)
    except OSError as exc:
        logger.warning(
            "Could not persist device id to %s (%s); it will not be stable "
            "across restarts.",
            path,
            exc,
        )
    return device_id


@functools.lru_cache(maxsize=1)
def _ip_hash_salt() -> bytes:
    """Return the secret salt used to pseudonymize IP addresses.

    Uses the configured salt (the ``--agent-ip-salt`` option / ``CB_AGENT_IP_SALT``
    env var) when set — required for consistent hashing across multiple server
    replicas; otherwise a random salt is generated and persisted so hashes stay
    stable across restarts on a single instance.
    """
    configured_salt = get_settings().get("agent_ip_salt")
    if configured_salt:
        return configured_salt.encode("utf-8")

    logger.info(
        "No agent IP salt configured; using a locally-stored one. Set "
        "--agent-ip-salt (env CB_AGENT_IP_SALT) to a shared secret for "
        "consistent IP hashing across multiple server instances or ephemeral "
        "deployments."
    )
    path = _device_id_file().with_name("ip_salt")
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing.encode("utf-8")
    except OSError:
        pass

    salt = uuid.uuid4().hex
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(salt, encoding="utf-8")
    except OSError as exc:
        logger.debug("Could not persist IP salt to %s: %s", path, exc)
    return salt.encode("utf-8")


def _hash_ip(ip: str) -> str:
    """Pseudonymize an IP address with a keyed hash (HMAC-SHA256, truncated).

    The same IP maps to the same id (so rate limiting works), but the raw
    address is never transmitted and cannot be recovered without the salt.
    """
    return hmac.new(_ip_hash_salt(), ip.encode("utf-8"), hashlib.sha256).hexdigest()[
        :16
    ]


def _http_device_id() -> str | None:
    """Per-device id from the (pseudonymized) source IP, or ``None`` if not HTTP.

    The IP is the only per-client signal a remote caller cannot change from its
    own configuration; it is hashed before use so the raw address never leaves
    the server while the same client still maps to a stable id.

    Note: this is the *direct connection* IP. Behind a reverse proxy / load
    balancer that address is the proxy's, collapsing all clients into one — in
    that setup, rate-limit at the proxy on the real client IP instead.
    """
    try:
        request = get_http_request()
    except RuntimeError:
        return None  # not an HTTP request (e.g. stdio) -> caller uses persisted id

    client_ip = request.client.host if request.client else ""
    return f"mcp-ip-{_hash_ip(client_ip)}" if client_ip else _DEFAULT_USER_ID


def device_user_id() -> str:
    """Return a per-device ``userId`` that works across stdio and HTTP transports.

    - **HTTP**: the source IP, pseudonymized via a keyed hash (``mcp-ip-<hash>``).
      Enforce limits at a gateway on the real connection where possible; the id
      is only as trustworthy as the IP behind it.
    - **stdio**: a random id persisted to a per-user file (the server is local to
      the device).
    """
    return _http_device_id() or _persisted_device_id()


def _build_agent_url(base_url: str | None = None) -> str:
    """Build the full URL for the agent RAG chat endpoint."""
    base = base_url or get_agent_base_url()
    return f"{base.rstrip('/')}{_RAG_CHAT_ENDPOINT}"


# ---------------------------------------------------------------------------
# Core HTTP helper
# ---------------------------------------------------------------------------


def call_agent(
    *,
    content: str,
    thread_id: str | None = None,
    user_id: str = "",
    run_id: str | None = None,
    extra_data: dict[str, Any] | None = None,
    extra_payload: dict[str, Any] | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Send a request to the RAG chat endpoint and return the parsed response.

    This is a shared helper so that every public tool converges on one
    well-tested HTTP call path, with consistent error handling.

    Args:
        content: The question text to send (mapped to the backend ``messages``).
        thread_id: Optional conversation thread ID (auto-generated if *None*).
        user_id: Optional user identifier. Also carried in the ``User-Agent``
            header as the per-device rate-limit signal.
        run_id: Optional run identifier (auto-generated if *None*).
        extra_data: Extra keys merged into the request ``data`` object (e.g. a
            ``rag_config`` block).
        extra_payload: Extra top-level keys to merge into the request body.
        base_url: Base URL of the agent service.  When *None* the value is
            resolved via :func:`get_agent_base_url` (env → default).

    Returns:
        Parsed JSON response body as a dict.

    Raises:
        ConnectionError: When the agent service is unreachable.
        RuntimeError: For any other HTTP / parsing failure.
    """
    url = _build_agent_url(base_url)
    thread_id = thread_id or str(uuid.uuid4())
    run_id = run_id or str(uuid.uuid4())

    body: dict[str, Any] = {
        "data": {
            "thread_id": thread_id,
            "user_id": user_id or _DEFAULT_USER_ID,
            "run_id": run_id,
            "messages": content,
        }
    }
    if extra_payload:
        body.update(extra_payload)
    if extra_data:
        body["data"].update(extra_data)

    headers = {"User-Agent": _user_agent(user_id)}

    logger.debug("POST %s — thread=%s run=%s", url, thread_id, run_id)

    try:
        response = httpx.post(
            url,
            json=body,
            headers=headers,
            timeout=_REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.ConnectError as exc:
        logger.error("Could not connect to agent service at %s", url)
        raise ConnectionError(
            f"Could not connect to the agent service at {url}. "
            "Ensure the service is running."
        ) from exc
    except httpx.TimeoutException as exc:
        logger.error("Request to %s timed out after %ss", url, _REQUEST_TIMEOUT_SECONDS)
        raise RuntimeError(
            f"Request to the agent service at {url} timed out after "
            f"{_REQUEST_TIMEOUT_SECONDS}s. The service may be overloaded."
        ) from exc
    except httpx.HTTPStatusError as exc:
        # Always log the full body (e.g. an nginx 502 page or FastAPI 422 detail)
        # so failures remain diagnosable, but keep the user-facing message clean.
        status = exc.response.status_code
        detail = exc.response.text[:1000]
        logger.error("Agent service returned HTTP %s: %s", status, detail)
        if status == 429:
            # Rate limited (e.g. by the WAF/gateway) — give a clear, calm message.
            retry_after = exc.response.headers.get("Retry-After")
            hint = f" (retry after {retry_after})" if retry_after else ""
            raise RuntimeError(
                "The documentation service is rate limiting requests. "
                f"Please wait a moment and try again.{hint}"
            ) from exc
        if status >= 500:
            # Server-side / transient error — don't surface the raw HTML page.
            raise RuntimeError(
                "The documentation service is temporarily unavailable. "
                "Please try again in a moment."
            ) from exc
        # Client-side (4xx): the body is usually short and actionable.
        raise RuntimeError(
            f"The agent service rejected the request (HTTP {status}): {detail}"
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Request to agent service failed: %s", exc)
        raise RuntimeError(f"Request to the agent service failed: {exc}") from exc

    try:
        resp_body = response.json()
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON from agent service: %s", exc)
        raise RuntimeError(
            f"The agent service returned an invalid JSON response: {exc}"
        ) from exc

    # Surface server-side errors
    if resp_body.get("error"):
        error_msg = str(resp_body["error"])
        logger.error("Agent service returned error: %s", error_msg)
        raise RuntimeError(f"Agent service error: {error_msg}")

    return resp_body


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def extract_answer(resp_body: dict[str, Any]) -> str:
    """Extract the human-readable answer from the RAG chat response.

    The ``/docs/rag_chat`` endpoint returns the answer under ``content``; this
    helper normalises the response into a single string.
    """
    # Preferred key for docs/RAG answers
    if resp_body.get("content"):
        return str(resp_body["content"])

    # Last resort — dump the full body so the caller can debug
    logger.warning("No recognised answer key in response: %s", resp_body)
    return json.dumps(resp_body, indent=2)


def format_sources(resp_body: dict[str, Any]) -> str:
    """Format the documentation source URLs returned by the RAG endpoint.

    ``/docs/rag_chat`` returns ``doc_source_urls`` as a list of (already
    deduplicated) URL strings. Returns a Markdown ``Sources`` section (leading
    separator) so it can be appended to the answer, or an empty string when
    there are no sources.
    """
    urls = resp_body.get("doc_source_urls")
    if not urls:
        return ""

    lines = ["\n\n---\n**Sources:**"]
    lines.extend(f"- {url}" for url in urls)
    return "\n".join(lines)
