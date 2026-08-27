"""
Couchbase Documentation MCP Server
"""

import logging

import click
from fastmcp import FastMCP
from fastmcp.tools import FunctionTool

from cb_mcp.tools import TOOL_ANNOTATIONS, get_tools
from cb_mcp.utils.config import set_settings
from cb_mcp.utils.constants import (
    ALLOWED_TRANSPORTS,
    DEFAULT_HOST,
    DEFAULT_LOG_LEVEL,
    DEFAULT_PORT,
    DEFAULT_TRANSPORT,
    MCP_SERVER_NAME,
    NETWORK_TRANSPORTS,
    NETWORK_TRANSPORTS_SDK_MAPPING,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, DEFAULT_LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(MCP_SERVER_NAME)


@click.command()
@click.option(
    "--transport",
    envvar="CB_MCP_TRANSPORT",
    type=click.Choice(ALLOWED_TRANSPORTS),
    default=DEFAULT_TRANSPORT,
    help="Transport mode for the server (stdio or http). Default is stdio",
)
@click.option(
    "--host",
    envvar="CB_MCP_HOST",
    default=DEFAULT_HOST,
    help="Host to run the server on (default: 127.0.0.1)",
)
@click.option(
    "--port",
    envvar="CB_MCP_PORT",
    default=DEFAULT_PORT,
    help="Port to run the server on (default: 8000)",
)
@click.option(
    "--agent-base-url",
    envvar="CB_AGENT_BASE_URL",
    default=None,
    help="Base URL of the documentation agent backend service that answers "
    "ask_couchbase_docs queries. Set this to your agent's URL for self hosted deployments. If unset, the server will use the default public agent.",
)
@click.option(
    "--agent-ip-salt",
    envvar="CB_AGENT_IP_SALT",
    default=None,
    help="Secret salt used to pseudonymize client IPs (HTTP transport). Set a "
    "shared value for consistent hashing across multiple instances; a local "
    "salt is generated when unset.",
)
@click.version_option(package_name=MCP_SERVER_NAME)
def main(transport, host, port, agent_base_url, agent_ip_salt):
    """Couchbase Documentation MCP Server"""

    # Store configuration for later retrieval via get_settings().
    set_settings(
        {
            "transport": transport,
            "host": host,
            "port": port,
            "agent_base_url": agent_base_url,
            "agent_ip_salt": agent_ip_salt,
        }
    )

    # Map user-friendly transport names to SDK transport names
    sdk_transport = NETWORK_TRANSPORTS_SDK_MAPPING.get(transport, transport)

    mcp = FastMCP(MCP_SERVER_NAME)

    # Register tools with their annotations. New tools are added by appending to
    # cb_mcp.tools.TOOLS; FastMCP 3.x add_tool has no annotations kwarg, so each
    # function is wrapped in a FunctionTool that carries the annotations.
    tools = get_tools()
    logger.info(f"Registering {len(tools)} tool(s)")
    for tool in tools:
        annotations = TOOL_ANNOTATIONS.get(tool.__name__)
        mcp.add_tool(FunctionTool.from_function(tool, annotations=annotations))
    logger.info(f"Registered {len(tools)} tool(s)")

    # For network transports, host/port are passed to run() (not the constructor).
    run_kwargs = {"host": host, "port": port} if transport in NETWORK_TRANSPORTS else {}

    # Run the server
    mcp.run(transport=sdk_transport, show_banner=False, **run_kwargs)  # type: ignore


if __name__ == "__main__":
    main()
