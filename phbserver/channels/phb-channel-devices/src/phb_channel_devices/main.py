"""Entry point for phb-channel-devices plugin."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from phb_channel_sdk import PluginTransport, log_setup
from phb_commons.constants.network import DEFAULT_LOCALHOST, PORT_OFFSET_PLUGIN, PORT_RANGE_START
from phb_commons.constants.storage import LOGS_DIR

from .plugin import DevicesChannel

_DEFAULT_LOG_DIR = str(Path.home() / ".phbcli" / LOGS_DIR)
_DEFAULT_PLUGIN_WS = f"ws://{DEFAULT_LOCALHOST}:{PORT_RANGE_START + PORT_OFFSET_PLUGIN}"

app = typer.Typer(
    name="phb-channel-devices",
    help="Private Home Box devices channel plugin.",
    add_completion=False,
)


@app.command()
def run(
    phb_ws: str = typer.Option(
        _DEFAULT_PLUGIN_WS,
        "--phb-ws",
        help="WebSocket URL of phbcli plugin server.",
        envvar="PHB_WS",
    ),
    log_dir: str = typer.Option(
        _DEFAULT_LOG_DIR,
        "--log-dir",
        help="Directory for rotating log files.",
    ),
) -> None:
    plugin = DevicesChannel()
    log_setup.init(f"plugin-{plugin.info.name}", Path(log_dir))
    transport = PluginTransport(plugin, phb_ws)
    asyncio.run(transport.run())


if __name__ == "__main__":
    app()
