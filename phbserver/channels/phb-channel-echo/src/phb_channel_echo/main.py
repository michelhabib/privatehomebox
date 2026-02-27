"""Entry point for the phb-channel-echo plugin process.

Invoked by phbcli's PluginManager as:
    phb-channel-echo --phb-ws ws://127.0.0.1:18081
"""

from __future__ import annotations

import asyncio
import logging
import sys

import typer

from phb_channel_sdk.transport import PluginTransport

from .plugin import EchoChannel

app = typer.Typer(
    name="phb-channel-echo",
    help="Private Home Box echo channel plugin.",
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
        help="WebSocket URL of phbcli's plugin server.",
        envvar="PHB_WS",
    ),
) -> None:
    """Connect to phbcli and start the echo channel."""
    plugin = EchoChannel()
    transport = PluginTransport(plugin, phb_ws)
    asyncio.run(transport.run())


if __name__ == "__main__":
    app()
