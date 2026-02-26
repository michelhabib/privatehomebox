# phbgateway

**Private Home Box Gateway** — WebSocket relay server.

Accepts connections from `phbcli` desktop clients and online apps, and relays
messages between them identified by `device_id`.

## Quick Start

```bash
# Install and run with uv
uv run phbgateway

# Or with custom host/port
uv run phbgateway --host 0.0.0.0 --port 8765
```

## How it works

1. A `phbcli` desktop client connects to `ws://<host>:<port>?device_id=<id>` and is registered.
2. An online app connects the same way and sends a JSON message with a `target_device_id` field.
3. The gateway looks up the target device in the registry and forwards the message.

## Message Format

```json
{
  "target_device_id": "uuid-of-the-target-device",
  "payload": { ... }
}
```

If `target_device_id` is omitted, the message is broadcast to all connected devices.
