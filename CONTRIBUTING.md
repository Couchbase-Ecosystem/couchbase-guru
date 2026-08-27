# Contributing to Couchbase Guru MCP Server

Thanks for your interest in contributing! This guide covers development setup and workflow for the Couchbase Guru documentation-search MCP server.

## 🚀 Development setup

### Prerequisites

- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/)** — package and environment manager
- **Git**

### Clone and install

```bash
git clone https://github.com/Couchbase-Ecosystem/couchbase-guru.git
cd couchbase-guru

# Install dependencies (including dev tools)
uv sync --extra dev

# Install pre-commit hooks (runs Ruff on every commit)
uv run pre-commit install
```

> External contributors don't have commit access to the main repository. [Fork the repo](https://github.com/Couchbase-Ecosystem/couchbase-guru/fork), then clone your fork.

## 🧹 Linting & formatting

We use **[Ruff](https://docs.astral.sh/ruff/)** for linting and formatting (88-char lines, import sorting, pyupgrade).

```bash
# Check (no changes)
./scripts/lint.sh          # or: uv run ruff check src/ tests/

# Auto-fix
./scripts/lint_fix.sh      # or: uv run ruff check src/ tests/ --fix && uv run ruff format src/ tests/
```

Ruff also runs automatically via pre-commit on every `git commit`.

## 🏗️ Project structure

```
couchbase-guru/
├── src/
│   ├── mcp_server.py            # Entry point: CLI options + tool registration
│   └── cb_mcp/
│       ├── __init__.py
│       ├── tools/
│       │   ├── __init__.py      # TOOLS, TOOL_ANNOTATIONS, get_tools()
│       │   └── docs.py          # ask_couchbase_docs tool
│       └── utils/
│           ├── __init__.py
│           ├── agent.py         # Agent backend client + per-device identity
│           ├── config.py        # Settings store (set_settings/get_settings)
│           └── constants.py     # Constants (server name, defaults, agent URL)
├── tests/
│   ├── conftest.py              # Integration fixtures (stdio MCP session)
│   ├── test_agent.py            # Unit: agent client (network mocked)
│   ├── test_docs.py             # Unit: ask_couchbase_docs tool
│   └── test_docs_tools.py       # Integration: end-to-end against a live agent
├── scripts/                     # lint.sh, lint_fix.sh, update_version.sh
├── Dockerfile
├── server.json                  # MCP Registry manifest
├── pyproject.toml               # Dependencies, Ruff, pytest config
├── README.md
└── CONTRIBUTING.md
```

The server exposes a single tool, `ask_couchbase_docs`, which forwards questions to a hosted documentation (RAG) agent via `cb_mcp.utils.agent.call_agent`. It does **not** connect to a Couchbase cluster.

## 🧪 Testing

Unit tests run offline — the agent backend is mocked, so no network is used:

```bash
uv run pytest tests/test_agent.py tests/test_docs.py -v
```

Integration tests exercise the tool end-to-end against a **live** agent backend and are opt-in:

```bash
# Uses the public default agent unless CB_AGENT_BASE_URL is set
CB_MCP_RUN_INTEGRATION=1 uv run pytest tests/test_docs_tools.py -v

# Or target a specific backend (e.g. staging)
CB_MCP_RUN_INTEGRATION=1 CB_AGENT_BASE_URL=https://your-agent.example.com \
  uv run pytest tests/test_docs_tools.py -v
```

Please add tests for new behavior and cover both success and error paths.

## 🛠️ Development workflow

1. Create a branch:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make changes, then check locally:

   ```bash
   ./scripts/lint.sh
   uv run pytest tests/test_agent.py tests/test_docs.py

   # Smoke-test the server
   uv run src/mcp_server.py --help
   ```

3. Commit (pre-commit hooks run Ruff automatically):

   ```bash
   git add .
   git commit -m "feat: describe your change"
   ```

4. Push your branch and open a PR describing **what** changed, **why**, and **how you tested it**.

### Adding a new tool

1. Create the tool function in a module under `src/cb_mcp/tools/`.
2. Register it in `tools/__init__.py`: import it, append to `TOOLS`, and add an entry to `TOOL_ANNOTATIONS`.
3. Add unit tests (and an integration test if it calls the backend).
4. Test it with a real MCP client.

## 🎨 Code style

- **Line length**: 88 (Ruff).
- **Imports**: isort-style grouping; import from the specific submodule (`cb_mcp.utils.constants`), not through the package.
- **Type hints & docstrings**: on public functions.
- **Logging**: use the hierarchical pattern `logging.getLogger(f"{MCP_SERVER_NAME}.module.name")`. Prefer logging clear failure context over raising where you can continue sensibly.

## 📦 Releasing

Maintainers only. Bump the version everywhere with the helper script, then tag:

```bash
./scripts/update_version.sh 0.1.1     # updates pyproject.toml, server.json, uv.lock
git add pyproject.toml server.json uv.lock && git commit -m "Bump version to 0.1.1"
git tag v0.1.1
git push origin main && git push origin v0.1.1
```

Pushing the tag triggers the PyPI, Docker Hub, and MCP Registry workflows. See [RELEASE.md](RELEASE.md) for details.

## 🆘 Getting help

- **[Open an issue](https://github.com/Couchbase-Ecosystem/couchbase-guru/issues)** for bugs or feature requests.
- **[Model Context Protocol docs](https://modelcontextprotocol.io/)** and **[Ruff docs](https://docs.astral.sh/ruff/)**.

Thank you for contributing! 🚀
