import logging

import click

from .constants import MCP_SERVER_NAME

logger = logging.getLogger(f"{MCP_SERVER_NAME}.utils.config")


_CONFIG_STATE: dict[str, dict] = {"settings": {}}


def set_settings(settings: dict) -> None:
    """Set settings in module state."""
    _CONFIG_STATE["settings"] = settings


def get_settings() -> dict:
    """Get settings from Click context, or fall back to stored settings."""
    ctx = click.get_current_context(silent=True)
    if ctx is not None and ctx.obj:
        return ctx.obj
    return _CONFIG_STATE["settings"]
