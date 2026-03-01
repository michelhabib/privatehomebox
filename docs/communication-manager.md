# CommunicationManager

`phbcli/src/phbcli/communication_manager.py`

The central message router that sits between `PluginManager` and the application
core. All inbound messages from every channel pass through it before reaching any
consumer, and all outbound messages must be enqueued through it before being
dispatched back to a channel plugin.

---

## Responsibilities

| Concern | How |
|---|---|
| Inbound routing | Registered as `PluginManager`'s `on_message` callback; validates raw params → `UnifiedMessage`, permission check, → `inbound_queue` |
| Outbound routing | Outbound worker drains `outbound_queue`, permission check, → `plugin_manager.send_to_channel(...)` |
| Permission enforcement | Placeholder `_check_permissions(msg)` — raise `PermissionError` to block; will enforce user/channel ACLs once the permission system is designed |
| Lifecycle | `run()` coroutine runs the outbound worker; added to `asyncio.gather(...)` alongside `PluginManager` and the HTTP server |

---

## Queues

### `inbound_queue: asyncio.Queue[UnifiedMessage]`

Messages arriving **from** channel plugins land here after passing the permission
check. The future agent manager (or any consumer) reads from this queue.

### `outbound_queue: asyncio.Queue[UnifiedMessage]`

Messages to be sent **to** a channel plugin are placed here via
`enqueue_outbound(msg)`. The outbound worker picks them up and calls
`plugin_manager.send_to_channel(msg.channel, msg.model_dump(mode="json"))`.

---

## API

```python
comm = CommunicationManager()
plugin_manager = PluginManager(..., on_message=comm.receive)
comm.set_plugin_manager(plugin_manager)

# In asyncio.gather:
await asyncio.gather(..., comm.run())

# Send a reply from anywhere in the application:
await comm.enqueue_outbound(UnifiedMessage(
    channel="telegram",
    direction="outbound",
    sender_id="phbcli",
    recipient_id="123456789",
    body="Hello back!",
))
```

| Method / attribute | Description |
|---|---|
| `set_plugin_manager(pm)` | Late-bind `PluginManager` (called after both objects are constructed) |
| `async receive(data)` | `on_message` callback — validates dict → `UnifiedMessage`, permission check, enqueues inbound |
| `async enqueue_outbound(msg)` | Put a `UnifiedMessage` on the outbound queue |
| `async run()` | Start the outbound worker loop |
| `inbound_queue` | Public `asyncio.Queue[UnifiedMessage]` for downstream consumers |
| `outbound_queue` | Public `asyncio.Queue[UnifiedMessage]` (normally written to via `enqueue_outbound`) |

---

## Message flow

### Inbound

```
channel plugin
    │  channel.receive (JSON-RPC)
    ▼
PluginManager.on_message(params)
    │
    ▼
CommunicationManager.receive(params)
  [validate → UnifiedMessage]
  [_check_permissions]
    │
    ▼
inbound_queue
    │
    ▼
[consumer — future agent manager]
```

### Outbound

```
application core
    │
    ▼
CommunicationManager.enqueue_outbound(msg)
    │
    ▼  (outbound worker)
  [_check_permissions]
    │
    ▼
PluginManager.send_to_channel(msg.channel, msg.model_dump())
    │  channel.send (JSON-RPC)
    ▼
channel plugin → third-party API
```

---

## Permission checks (placeholder)

`_check_permissions(msg: UnifiedMessage)` is a module-level function called for
both inbound and outbound messages. Currently a no-op. Raise `PermissionError`
from it to silently drop a message with a warning log.

Once the permission system is designed it will enforce:
- Which channels are allowed to send inbound traffic
- Which senders / recipient IDs are authorised
- Rate limits or content-type restrictions per channel

---

## See also

- [channel-plugin-architecture.md](channel-plugin-architecture.md) — overall plugin
  system design, JSON-RPC protocol, and message flow diagrams
- `phbcli/plugin_manager.py` — `PluginManager`, which owns channel subprocesses and
  the low-level JSON-RPC transport
- `phb-channel-sdk/models.py` — `UnifiedMessage` schema
