# Stage 1: Build the distribution wheel from source
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim AS wheel-builder

WORKDIR /src

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN uv build --wheel --out-dir /wheels

# Stage 2: Create venv, install pinned deps from lock file, then install pre-built wheel
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim AS builder

# Set uv configuration
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build

# Copy dependency files for reproducible, pinned installs
COPY pyproject.toml README.md uv.lock ./
COPY --from=wheel-builder /wheels/ /wheels/

# Install locked dependencies, then the pre-built wheel (deps already resolved)
RUN UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --frozen --no-install-project --no-dev && \
    uv pip install --python /opt/venv/bin/python --no-deps /wheels/couchbase_guru-*.whl

# Runtime stage - use Python image with same version as builder
FROM python:3.13-slim-trixie AS runtime

# Accept build arguments for labels
ARG GIT_COMMIT_HASH="unknown"
ARG BUILD_DATE="unknown"

# Add metadata labels
LABEL org.opencontainers.image.revision="${GIT_COMMIT_HASH}" \
    org.opencontainers.image.created="${BUILD_DATE}" \
    org.opencontainers.image.title="Couchbase Guru MCP Server" \
    org.opencontainers.image.description="MCP server for searching Couchbase documentation" \
    org.opencontainers.image.source="https://github.com/Couchbase-Ecosystem/couchbase-guru"\
    io.modelcontextprotocol.server.name="io.github.Couchbase-Ecosystem/couchbase-guru"

# Create non-root user
RUN useradd --system --uid 1001 mcpuser

WORKDIR /app

# Copy virtual environment and application from builder
COPY --from=builder /opt/venv /opt/venv

# Set up Python environment
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Change ownership to non-root user
RUN chown -R mcpuser:mcpuser /app /opt/venv

# Switch to non-root user
USER 1001

# Environment variables with stdio defaults (override for network mode)
ENV CB_MCP_TRANSPORT="stdio" \
    CB_MCP_PORT="8000"

# Expose default port for HTTP/SSE mode
EXPOSE 8000

# Use the installed console script
ENTRYPOINT ["couchbase-guru"]
