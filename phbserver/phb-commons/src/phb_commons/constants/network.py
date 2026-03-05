"""Network and port constants shared across all PHB packages."""

from __future__ import annotations

DEFAULT_GATEWAY_PORT: int = 8765
DEFAULT_GATEWAY_HOST: str = "0.0.0.0"
DEFAULT_LOCALHOST: str = "127.0.0.1"

# Workspace port allocation — 3 ports per slot, starting at PORT_RANGE_START.
#   http_port    = PORT_RANGE_START + slot * PORTS_PER_SLOT + PORT_OFFSET_HTTP
#   plugin_port  = PORT_RANGE_START + slot * PORTS_PER_SLOT + PORT_OFFSET_PLUGIN
#   gateway_port = PORT_RANGE_START + slot * PORTS_PER_SLOT + PORT_OFFSET_GATEWAY
#
# Example (slot 0): http=18080, plugin=18081, gateway=18082
PORT_RANGE_START: int = 18080
PORTS_PER_SLOT: int = 3
PORT_OFFSET_HTTP: int = 0
PORT_OFFSET_PLUGIN: int = 1
PORT_OFFSET_GATEWAY: int = 2
