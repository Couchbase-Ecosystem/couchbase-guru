# Couchbase Guru MCP Server

An [MCP](https://modelcontextprotocol.io/) server that lets LLMs search the [Couchbase documentation](https://docs.couchbase.com/) from your MCP client. It exposes a single tool, `ask_couchbase_docs`, which forwards your question to a hosted retrieval-augmented (RAG) documentation agent and returns an answer with source links.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/) [![PyPI version](https://badge.fury.io/py/couchbase-guru.svg)](https://pypi.org/project/couchbase-guru/)

<!-- mcp-name: io.github.Couchbase-Ecosystem/couchbase-guru -->

> **No Couchbase cluster or credentials required.** The server talks only to the documentation agent backend, not to your data.

## Tool

| Tool Name | Description |
| --------- | ----------- |
| `ask_couchbase_docs` | Answer a question about any Couchbase product, feature, SDK, service, tutorial, or example by searching the official documentation. Returns a natural-language answer followed by the documentation source URLs. |

Ask complete, self-contained questions — the backend has no conversation history, so include the product, version, and language where relevant (e.g. _"How do I create a primary index with the Python SDK in Couchbase Server 7.6?"_).

## Prerequisites

- Python 3.10 or higher.
- [uv](https://docs.astral.sh/uv/) installed to run the server.
- An [MCP client](https://modelcontextprotocol.io/clients) such as [Claude Desktop](https://claude.ai/download), [Cursor](https://cursor.sh/), or [VS Code](https://code.visualstudio.com/).

## Configuration

The server can be run from the prebuilt PyPI package or from source with `uv`. It works with zero configuration — the public documentation agent is used by default.

### Running from PyPI

```json
{
  "mcpServers": {
    "couchbase-guru": {
      "command": "uvx",
      "args": ["couchbase-guru"]
    }
  }
}
```

> If you already have other MCP servers configured, add this entry to the existing `mcpServers` object.

### Running from Source

Clone the repository:

```bash
git clone https://github.com/Couchbase-Ecosystem/couchbase-guru.git
```

Then point your MCP client at it:

```json
{
  "mcpServers": {
    "couchbase-guru": {
      "command": "uv",
      "args": [
        "--directory",
        "path/to/cloned/repo/couchbase-guru/",
        "run",
        "src/mcp_server.py"
      ]
    }
  }
}
```

> `path/to/cloned/repo/couchbase-guru/` should be the path to the cloned repository on your machine. Don't forget the trailing slash.

### Options

All options are optional and can be set via CLI argument or environment variable:

| CLI Argument | Environment Variable | Description | Default |
| ------------ | -------------------- | ----------- | ------- |
| `--transport` | `CB_MCP_TRANSPORT` | Transport mode: `stdio` or `http` | `stdio` |
| `--host` | `CB_MCP_HOST` | Host for HTTP transport mode | `127.0.0.1` |
| `--port` | `CB_MCP_PORT` | Port for HTTP transport mode | `8000` |
| `--agent-base-url` | `CB_AGENT_BASE_URL` | Base URL of the documentation agent backend. Set this to run against your own self-hosted agent; if unset, the public agent is used. | Public agent |
| `--agent-ip-salt` | `CB_AGENT_IP_SALT` | Secret salt used to pseudonymize client IPs (HTTP transport). Set a shared value for consistent hashing across multiple instances; a local salt is generated when unset. | Auto-generated |

Check the installed version with:

```bash
uvx couchbase-guru --version
```

## Self-hosting the documentation agent

By default the server uses a shared, public documentation agent, so most users need no setup. If you run your own agent backend, point the server at it:

```bash
uvx couchbase-guru --agent-base-url https://your-agent.example.com
```

## Rate limiting & privacy

The public agent applies fair-use rate limits. To support this, the server sends a **pseudonymous** device identifier to the backend (in the `User-Agent` header):

- **stdio**: a random id generated once and stored in a per-user file on your machine.
- **HTTP**: a salted, one-way hash of the connecting IP — the raw address is never sent.

No question content or personal data is persisted by the MCP server itself. If you prefer not to share a rate-limit signal, self-host the agent (see above).

## Client-specific configuration

<details>
<summary>Claude Desktop</summary>

1. Edit the configuration file (see the [MCP quickstart guide](https://modelcontextprotocol.io/quickstart/user)):
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
2. Add the [configuration](#running-from-pypi) to the `mcpServers` section.
3. Restart Claude Desktop.

Logs: `~/Library/Logs/Claude` (macOS) or `%APPDATA%\Claude\Logs` (Windows).

</details>

<details>
<summary>Cursor</summary>

1. In Cursor, go to **Cursor Settings > Tools & Integrations > MCP Tools**.
2. Add the [configuration](#running-from-pypi) manually, or use the one-click [Install in Cursor][cursor-install-basic] link.
3. Save, then refresh to confirm the server is enabled.

[cursor-install-basic]: https://cursor.com/en-US/install-mcp?name=couchbase-guru&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJjb3VjaGJhc2UtZ3VydSJdfQ%3D%3D

Logs: in the bottom panel, click **Output** and select **Cursor MCP** from the dropdown.

</details>

<details>
<summary>Windsurf Editor</summary>

1. Open **Command Palette > Windsurf MCP Configuration Panel** (or **Settings > Advanced > Cascade > Model Context Protocol (MCP) Servers**).
2. Click **Add Server > Add custom server** and add the [configuration](#running-from-pypi).
3. Save, then refresh to confirm the server is enabled.

See the [Windsurf MCP documentation](https://docs.windsurf.com/windsurf/cascade/mcp) for details.

</details>

<details>
<summary>VS Code</summary>

1. Create `.vscode/mcp.json` in your workspace (or run **MCP: Open User Configuration** for a global config).
2. VS Code uses `servers` as the top-level key (not `mcpServers`):

   ```json
   {
     "servers": {
       "couchbase-guru": {
         "command": "uvx",
         "args": ["couchbase-guru"]
       }
     }
   }
   ```

3. Once saved, use the inline action list to `Start`/`Stop`/manage the server.

See the [VS Code MCP docs](https://code.visualstudio.com/docs/copilot/customization/mcp-servers) for details.

</details>

<details>
<summary>JetBrains IDEs</summary>

1. Install the [AI Assistant](https://www.jetbrains.com/help/ai-assistant/getting-started-with-ai-assistant.html) or [Junie](https://www.jetbrains.com/help/junie/get-started-with-junie.html) plugin.
2. Navigate to **Settings > Tools > AI Assistant or Junie > MCP Server**.
3. Click "+", add the [configuration](#running-from-pypi), and click **Save**, then **Apply**.

Logs: **Help > Show Log in Finder (Explorer) > mcp > couchbase-guru**.

</details>

## Streamable HTTP transport mode

The server can run in [Streamable HTTP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#streamable-http) mode so multiple clients can connect to one instance. Check that your MCP client supports this transport first.

```bash
uvx couchbase-guru --transport=http --port=8000
```

The server will be available at <http://localhost:8000/mcp>:

```json
{
  "mcpServers": {
    "couchbase-guru-http": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

> This mode does not include authorization support.

## Docker

Build the image:

```bash
docker build -t couchbase-guru .
```

Run it (stdio by default; no credentials needed):

```json
{
  "mcpServers": {
    "couchbase-guru-docker": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "couchbase-guru"]
    }
  }
}
```

For HTTP transport, publish the port and set the transport:

```bash
docker run --rm -i \
  -e CB_MCP_TRANSPORT=http \
  -e CB_MCP_HOST=0.0.0.0 \
  -e CB_MCP_PORT=8000 \
  -p 8000:8000 \
  couchbase-guru
```

## Risks associated with LLMs

- The use of large language models and similar technology involves risks, including the potential for inaccurate or harmful outputs.
- Couchbase does not review or evaluate the quality or accuracy of such outputs, and such outputs may not reflect Couchbase's views.
- You are solely responsible for determining whether to use large language models and related technology, and for complying with any applicable license terms, terms of use, and your organization's policies.

## Troubleshooting

- Confirm that `uv`/`uvx` is installed and on your `PATH`. You may need to provide an absolute path to `uv`/`uvx` in the `command` field.
- If a search times out, the documentation backend may be busy — retry in a moment.
- To rule out the public backend, run against your own agent with `--agent-base-url`.
- If running from source after updating the repo, run `uv sync` to refresh dependencies.
- Check your MCP client's logs (locations above) for errors.

## Testing

Unit tests run offline (the backend is mocked):

```bash
uv sync --extra dev
uv run pytest tests/
```

Integration tests exercise the tool end-to-end against a live agent backend and are opt-in:

```bash
CB_MCP_RUN_INTEGRATION=1 uv run pytest tests/test_docs_tools.py
```

By default they use the public agent; set `CB_AGENT_BASE_URL` to target a different backend.

---

## 👩‍💻 Contributing

Contributions are welcome! To report a bug, request a feature, or contribute improvements, [open a GitHub issue](https://github.com/Couchbase-Ecosystem/couchbase-guru/issues).

See [CONTRIBUTING.md](CONTRIBUTING.md) for developer setup (environment with `uv`, linting/formatting with Ruff, pre-commit hooks, and project structure).

```bash
# Clone and set up
git clone https://github.com/Couchbase-Ecosystem/couchbase-guru.git
cd couchbase-guru

# Install with development dependencies
uv sync --extra dev

# Install pre-commit hooks
uv run pre-commit install
```

---

## 📢 Support Policy

We appreciate your interest in this project! It is **Couchbase community-maintained**, which means it is **not officially supported** by our support team. Our engineers monitor and maintain this repo and will try to resolve issues on a best-effort basis. Please keep all inquiries within GitHub.
