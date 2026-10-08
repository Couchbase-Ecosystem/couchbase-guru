# Agent Instructions for couchbase-guru

Guidance for AI agents and automated maintainers working in this repository. Human contributors should start with [CONTRIBUTING.md](CONTRIBUTING.md); release steps live in [RELEASE.md](RELEASE.md).

## What this repo is

- A Python MCP server (`couchbase-guru` on PyPI) exposing one tool, `ask_couchbase_docs`, which forwards questions to a hosted documentation (RAG) agent.
- It does **not** connect to a Couchbase cluster and has no Couchbase SDK dependency. No cluster or Couchbase credentials are needed for development or validation.
- Entry point: `src/mcp_server.py` (`couchbase-guru = "mcp_server:main"`). Package code: `src/cb_mcp/`.

## Dependencies

- Package manager is **uv** with a committed `uv.lock`. Do not switch to pip-tools, Poetry, or another workflow, and always commit `pyproject.toml` and `uv.lock` together.
- Runtime dependencies (`click`, `fastmcp`, `httpx`) use ranges in `pyproject.toml`. Refresh the lock within those ranges with `uv lock --upgrade`. Changing an upper bound (for example a new `fastmcp` major) changes what PyPI users install, so do it in its own PR and run the live integration test.
- Dev dependencies under `[project.optional-dependencies].dev` are exact pins. When bumping `ruff`, also bump the `ruff-pre-commit` `rev` in `.pre-commit-config.yaml` to the same version.
- `requires-python = ">=3.10,<3.15"`. CI tests Python 3.10 and 3.13. When testing locally against a specific interpreter, set `UV_PYTHON=<version>` so `uv run` does not recreate `.venv` with the `.python-version` default (3.13).
- GitHub Actions are pinned by commit SHA with a version comment. Keep that format when updating actions.

## Validation

Run the same gates CI runs (`.github/workflows/test.yml`):

```bash
uv sync --extra dev
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run pytest tests/ -v --tb=short
```

Unit tests mock the agent backend and need no network. The live integration test is skipped unless opted in:

```bash
CB_MCP_RUN_INTEGRATION=1 uv run pytest tests/test_docs_tools.py -v
```

For dependency or server changes, also do manual MCP validation:

1. `uv run src/mcp_server.py --help` and `uv run couchbase-guru --version`.
2. Call `ask_couchbase_docs` through a real MCP client over **stdio** (`uv run src/mcp_server.py`) and over **HTTP** (`uv run src/mcp_server.py --transport http --port <port>`, endpoint `http://127.0.0.1:<port>/mcp`). A `fastmcp.Client` script works for this. Ask a harmless docs question (for example "What is a primary index in Couchbase Server?") and confirm a non-error answer with source links.
3. When the `Dockerfile` or dependencies change, run `docker build -t couchbase-guru .` (CI builds the image on PRs without pushing it).

The public documentation agent applies fair-use rate limits and can be slow or unavailable. If the live test or a smoke call fails because of the backend (timeouts, 429, 5xx), record the exact error rather than reporting success. There is no browser UI. `/mcp` is a protocol endpoint, so screenshot or browser evidence does not apply.

## Releases

- Pushing a `v*` tag publishes to PyPI (`release.yml`) and TestPyPI (`test_release.yml`), pushes the Docker Hub image (`docker.yml`), and then updates the MCP Registry (`update-mcp-registry.yml`). Merging to `main` publishes nothing.
- Version bumps go through `./scripts/update_version.sh <version>`, which keeps `pyproject.toml`, `server.json`, and `uv.lock` in sync.
- Agents must **not** create tags or GitHub releases, dispatch release workflows, publish to PyPI or Docker Hub, or update the MCP Registry without explicit maintainer approval. Leave versions unchanged in dependency PRs unless asked.

## Pull requests

- Keep PRs scoped: dependency refreshes, minimal compatibility fixes, and related docs. Never commit `.env` files, `.venv/`, caches, or logs.
- In the PR body, list the commands you ran with their results, plus the manual stdio/HTTP smoke results.
