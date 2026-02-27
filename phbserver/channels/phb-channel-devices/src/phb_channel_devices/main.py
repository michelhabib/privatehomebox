"""Entry point for phb-channel-devices plugin."""

from __future__ import annotations

import asyncio
import logging
import sys

import typer
from phb_channel_sdk import PluginTransport

from .plugin import DevicesChannel

app = typer.Typer(
    name="phb-channel-devices",
    help="Private Home Box devices channel plugin.",
    add_completion=False,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


@app.command()
def run(
    phb_ws: str = typer.Option(
        "ws://127.0.0.1:18081",
        "--phb-ws",
        help="WebSocket URL of phbcli plugin server.",
        envvar="PHB_WS",
    ),
) -> None:
    plugin = DevicesChannel()
    transport = PluginTransport(plugin, phb_ws)
    asyncio.run(transport.run())


if __name__ == "__main__":
    app()
