# phbgateway

**Private Home Box Gateway** — WebSocket relay server.

Accepts connections from `phbcli` desktop clients and online apps, performs
challenge/response authentication, and relays messages between authenticated
devices identified by `device_id`.

## Quick Start

```bash
# Install and run with uv
uv run phbgateway

# Or with custom host/port and state dir
uv run phbgateway --host 0.0.0.0 --port 8765 --state-dir ./.gateway-state
```

## How it works

1. Every new socket receives an auth challenge nonce.
2. A desktop client authenticates using its master key (`auth_mode=desktop`) and can
   claim an uninitialized gateway by sending its public key once (`auth_mode=desktop_claim`).
3. A device client authenticates with desktop attestation + nonce signature
   (`auth_mode=device`).
4. Once authenticated, messages are relayed by `device_id`.

## Message Format

```json
{
  "target_device_id": "uuid-of-the-target-device",
  "payload": { ... }
}
```

If `target_device_id` is omitted, the message is broadcast to all connected devices.
