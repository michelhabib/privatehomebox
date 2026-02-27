"""Entry point for the detached server process spawned by `phbcli start`.

Runs the FastAPI HTTP server and PluginManager concurrently inside a single
asyncio event loop.  Gateway connectivity is owned by the mandatory
`devices` channel plugin.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
import uuid
from datetime import UTC, datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("phbcli.server_process")


async def _main() -> None:
    from phbcli.config import APP_DIR, load_config, mark_connected, mark_disconnected
    from phbcli.crypto import create_device_attestation, load_or_create_master_key
    from phbcli.pairing import (
        ApprovedDevice,
        clear_pairing_session,
        load_pairing_session,
        upsert_approved_device,
    )
    from phbcli.plugin_manager import PluginManager
    from phbcli.process import write_pid
    from phbcli.server import run_http_server, set_channel_info_provider

    config = load_config()
    desktop_private_key = load_or_create_master_key(APP_DIR, filename=config.master_key_file)
    stop_event = asyncio.Event()
    write_pid()
    plugin_manager: PluginManager | None = None

    def _shutdown(*_: object) -> None:
        logger.info("Shutdown signal received.")
        stop_event.set()

    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, _shutdown)

    async def _on_channel_event(event: str, data: dict[str, object]) -> None:
        nonlocal plugin_manager
        if event == "gateway_connected":
            gateway_url = str(data.get("gateway_url") or config.gateway_url)
            mark_connected(gateway_url)
        elif event == "gateway_disconnected":
            mark_disconnected()
        elif event == "pairing_request":
            if plugin_manager is None:
                return
            request_id = data.get("request_id")
            pairing_code = data.get("pairing_code")
            device_public_key = data.get("device_public_key")
            if not isinstance(request_id, str) or not request_id:
                return
            if not isinstance(pairing_code, str) or not pairing_code:
                await plugin_manager.send_event_to_channel(
                    "devices",
                    "pairing_response",
                    {
                        "request_id": request_id,
                        "status": "rejected",
                        "reason": "invalid_pairing_code",
                    },
                )
                return
            if not isinstance(device_public_key, str) or not device_public_key:
                await plugin_manager.send_event_to_channel(
                    "devices",
                    "pairing_response",
                    {
                        "request_id": request_id,
                        "status": "rejected",
                        "reason": "invalid_device_public_key",
                    },
                )
                return

            session = load_pairing_session()
            if session is None:
                await plugin_manager.send_event_to_channel(
                    "devices",
                    "pairing_response",
                    {
                        "request_id": request_id,
                        "status": "rejected",
                        "reason": "no_active_pairing_session",
                    },
                )
                return

            if (not session.is_valid()) or (session.code != pairing_code):
                await plugin_manager.send_event_to_channel(
                    "devices",
                    "pairing_response",
                    {
                        "request_id": request_id,
                        "status": "rejected",
                        "reason": "pairing_code_invalid_or_expired",
                    },
                )
                return

            device_id = f"mobile-{uuid.uuid4().hex[:12]}"
            attestation = create_device_attestation(
                desktop_private_key,
                device_id=device_id,
                device_public_key_b64=device_public_key,
                expires_days=config.attestation_expires_days,
            )
            blob = json.loads(attestation["blob"])
            expires_at_raw = blob.get("expires_at")
            expires_at = None
            if isinstance(expires_at_raw, str):
                try:
                    expires_at = datetime.fromisoformat(
                        expires_at_raw.replace("Z", "+00:00")
                    ).astimezone(UTC)
                except Exception:
                    expires_at = None

            upsert_approved_device(
                ApprovedDevice(
                    device_id=device_id,
                    device_public_key=device_public_key,
                    paired_at=datetime.now(UTC),
                    expires_at=expires_at,
                    metadata={"source": "gateway_pairing"},
                )
            )
            clear_pairing_session()
            await plugin_manager.send_event_to_channel(
                "devices",
                "pairing_response",
                {
                    "request_id": request_id,
                    "status": "approved",
                    "device_id": device_id,
                    "attestation": attestation,
                },
            )

    plugin_manager = PluginManager(
        config,
        stop_event,
        on_event=_on_channel_event,
    )
    set_channel_info_provider(plugin_manager.get_channel_info)

    logger.info(
        "Starting phbcli server. HTTP: http://%s:%d/status  "
        "plugin WS: ws://127.0.0.1:%d  device_id: %s",
        config.http_host,
        config.http_port,
        config.plugin_port,
        config.device_id,
    )

    await asyncio.gather(run_http_server(config, stop_event), plugin_manager.run())

    mark_disconnected()
    logger.info("phbcli server exited.")


if __name__ == "__main__":
    asyncio.run(_main())
