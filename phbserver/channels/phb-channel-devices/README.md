# phb-channel-devices

Mandatory PHB channel plugin that owns the gateway WebSocket connection and
bridges gateway relay envelopes to/from `UnifiedMessage`.

## Direction mapping

- Inbound from gateway:
  - envelope: `{ sender_device_id, payload: <UnifiedMessage> }`
  - output to phbcli: `channel.receive` with `UnifiedMessage`
- Outbound from phbcli:
  - input: `channel.send` with `UnifiedMessage`
  - envelope to gateway: `{ target_device_id?, payload: <UnifiedMessage> }`

## Events emitted to phbcli

- `gateway_connected`
- `gateway_disconnected`
