# MCP Server Constants
MCP_SERVER_NAME = "couchbase-guru"

# Default Configuration Values
DEFAULT_TRANSPORT = "stdio"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

# Public documentation agent backend used when the operator does not configure
# their own (via --agent-base-url / CB_AGENT_BASE_URL).
DEFAULT_AGENT_BASE_URL = "https://iq-fastapi-oss.prod.cbdevx.com/"

# Allowed Transport Types
ALLOWED_TRANSPORTS = ["stdio", "http"]
NETWORK_TRANSPORTS = ["http"]
NETWORK_TRANSPORTS_SDK_MAPPING = {
    "http": "streamable-http",
}

# Logging Configuration
# Change this to DEBUG, WARNING, ERROR as needed
DEFAULT_LOG_LEVEL = "INFO"
