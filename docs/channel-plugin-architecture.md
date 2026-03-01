# Channel Plugin Architecture

## Overview

Channel plugins are the mechanism by which Private Home Box connects to third-party
messaging platforms — Telegram, WhatsApp, a custom mobile app, and anything else that
can send and receive messages.

Each plugin is a **standalone Python package** that runs as a **subprocess** managed
by `phbcli`. It connects back to phbcli over a **local WebSocket** and speaks a
**JSON-RPC 2.0** protocol. The plugin is entirely responsible for translating between
the unified PHB message format and whatever the third party requires.

---

## Design goals

| Goal | How it is achieved |
|---|---|
| Dependency isolation | Each plugin is its own uv workspace member with its own virtualenv — no conflicts between e.g. `python-telegram-bot` and a WhatsApp SDK |
| Crash isolation | A plugin crash does not bring down phbcli or other plugins |
| Independent updates | Plugins are versioned and updated separately from the core server |
| Uniform interface | All plugins speak the same JSON-RPC 2.0 dialect over a local WebSocket |
| Developer ergonomics | `phb-channel-sdk` provides the full contract; authoring a new plugin requires implementing 4 methods |

---

## System diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│  phbcli (core server process)                                       │
│                                                                     │
│  ┌──────────────┐   local WS     ┌──────────────────────────────┐  │
│  │PluginManager │◄──────────────►│ phb-channel-telegram         │  │
│  │ :18081       │   JSON-RPC 2.0 │   (subprocess)               │  │
│  │              │                │   Telegram Bot API ◄────────►│  │
│  │              │   local WS     ├──────────────────────────────┤  │
│  │              │◄──────────────►│ phb-channel-whatsapp         │  │
│  │              │   JSON-RPC 2.0 │   (subprocess)               │  │
│  │              │                │   WhatsApp Cloud API ◄──────►│  │
│  │              │   local WS     ├──────────────────────────────┤  │
│  │              │◄──────────────►│ phb-channel-mobileapp        │  │
│  │              │   JSON-RPC 2.0 │   (subprocess)               │  │
│  └──────┬───────┘                │   Flutter WS ◄──────────────►│  │
│         │ on_message /           └──────────────────────────────┘  │
│         │ send_to_channel                                           │
│  ┌──────▼─────────────┐                                             │
│  │CommunicationManager│                                             │
│  │  inbound_queue  ───┼──► AgentManager                            │
│  │  outbound_queue ◄──┼─── enqueue_outbound(reply)                 │
│  │  permission check  │                                             │
│  └────────────────────┘                                             │
│                                                                     │
│  ┌─────────────────────────────────────────────────┐               │
│  │ AgentManager                                    │               │
│  │   create_agent (LangChain v1)                   │               │
│  │   InMemorySaver checkpointer                    │               │
│  │   thread_id = "channel:sender_id"               │               │
│  │   system_prompt  ←  ~/.phbcli/agent/            │               │
│  └─────────────────────────────────────────────────┘               │
│                                                                     │
│  ┌──────────────┐                                                   │
│  │ HTTP server  │  GET /status   GET /channels                      │
│  │ :18080       │                                                    │
│  └──────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Components

### phb-channel-sdk

The shared library that defines the contract between phbcli and every plugin.
It is a uv workspace member (`phbserver/phb-channel-sdk/`) and a declared dependency
of every channel package.

| Module | Exports | Purpose |
|---|---|---|
| `models.py` | `UnifiedMessage`, `ChannelInfo`, `RpcRequest`, `RpcResponse` | Pydantic data models |
| `base.py` | `ChannelPlugin` | Abstract base class plugins implement |
| `rpc.py` | `build_*`, `parse_message` | JSON-RPC 2.0 wire-format helpers |
| `transport.py` | `PluginTransport` | WS client that connects to phbcli and dispatches calls |

### PluginManager (phbcli)

Lives in `phbcli/plugin_manager.py`. On `phbcli start` it:

1. Opens a WebSocket server on `ws://127.0.0.1:<plugin_port>` (default `18081`).
2. Reads `~/.phbcli/channels/*.json` to discover enabled channels.
3. Spawns one subprocess per enabled channel, appending `--phb-ws <url>` and
   `--log-dir <path>`. Subprocess stdout/stderr are discarded — each plugin
   writes its own rotating log file to the log directory.
4. Accepts incoming connections from plugin processes.
5. Pushes the stored per-channel config (`config` field) to each plugin
   immediately after it registers.
6. Routes inbound messages from plugins to the configured `on_message` callback.
7. On shutdown: sends `channel.stop` to every plugin, waits 1 second, then
   terminates any remaining subprocesses.

### CommunicationManager (phbcli)

The central message router between `PluginManager` and the application core —
handles inbound/outbound queuing and permission checks.

See [communication-manager.md](communication-manager.md) for full details.

### AgentManager (phbcli)

The LLM worker that consumes text messages from the inbound queue, invokes
a LangChain v1 `create_agent` instance, and pushes replies to the outbound
queue.  Per-conversation memory is maintained using LangGraph's
`InMemorySaver` checkpointer, keyed by `channel:sender_id`.

See [agent-manager.md](agent-manager.md) for full details.

---

### Channel config files

Stored at `~/.phbcli/channels/<name>.json`:

```json
{
  "name": "telegram",
  "enabled": true,
  "command": ["phb-channel-telegram"],
  "config": {
    "bot_token": "123456:ABC-..."
  }
}
```

Managed via `phbcli channel setup|enable|disable|remove`.

---

## JSON-RPC 2.0 protocol

All messages are UTF-8 JSON over a single WebSocket connection per plugin.
A **notification** has no `"id"` field (fire-and-forget).
A **request** has an `"id"` and expects a **response** with the same `"id"`.

### Plugin → phbcli

| Method | Type | Params | When |
|---|---|---|---|
| `channel.register` | notification | `{name, version, description}` | First frame after connect — mandatory |
| `channel.receive` | notification | `UnifiedMessage` (dict) | Inbound message from third party |
| `channel.event` | notification | `{event: str, data: any}` | Status changes, delivery receipts, errors |

### phbcli → plugin

| Method | Type | Params | Purpose |
|---|---|---|---|
| `channel.send` | notification | `UnifiedMessage` (dict) | Send a message out through this channel |
| `channel.configure` | notification | `{config: {…}}` | Push credentials and settings |
| `channel.status` | request | — | Health probe — expects `{name, version, status}` |
| `channel.stop` | notification | — | Graceful shutdown signal |

### Example flow — inbound Telegram message

```
Telegram API ──► plugin polling loop
                      │
                      ▼
              plugin.emit(UnifiedMessage)
                      │
                      ▼  (PluginTransport)
   ws send: {"jsonrpc":"2.0","method":"channel.receive",
             "params":{...UnifiedMessage...}}
                      │
                      ▼
            PluginManager.on_message(params)
                      │
                      ▼
      CommunicationManager.receive(params)
        [validate → permission check]
                      │
                      ▼
          CommunicationManager.inbound_queue
                      │
                      ▼
              AgentManager.run()
          [text only → create_agent.ainvoke]
                      │
                      ▼
          CommunicationManager.outbound_queue
```

### Example flow — outbound message to Telegram

```
application core decides to send a message
        │
        ▼
CommunicationManager.enqueue_outbound(unified_msg)
        │
        ▼  (outbound worker — permission check)
PluginManager.send_to_channel("telegram", unified_msg)
        │
        ▼  (WS notification)
   {"jsonrpc":"2.0","method":"channel.send","params":{...UnifiedMessage...}}
        │
        ▼
plugin._dispatch → plugin.send(UnifiedMessage)
        │
        ▼
plugin translates → Telegram Bot API sendMessage
```

---

## UnifiedMessage format

```json
{
  "id": "a3f9c2d1...",
  "channel": "telegram",
  "direction": "inbound",
  "sender_id": "123456789",
  "recipient_id": null,
  "content_type": "text",
  "body": "Hello!",
  "metadata": {
    "chat_id": 123456789,
    "message_id": 42
  },
  "timestamp": "2026-02-27T10:00:00+00:00"
}
```

`direction` is always from phbcli's perspective:
- `"inbound"` — arriving FROM the third party (user sent something)
- `"outbound"` — to be SENT TO the third party

`content_type` values: `"text"`, `"image"`, `"audio"`, `"video"`, `"location"`, `"command"`, `"file"`.

`metadata` is channel-specific and freely structured.

---

## Plugin lifecycle

```
phbcli start
  │
  ├─ PluginManager starts WS server (:18081)
  │
  ├─ reads ~/.phbcli/channels/*.json
  │
  └─ for each enabled channel:
       │
       ├─ subprocess.Popen(
       │      ["phb-channel-telegram",
       │       "--phb-ws",   "ws://127.0.0.1:18081",
       │       "--log-dir",  "~/.phbcli/logs"],   ← passed by PluginManager
       │      stdout=DEVNULL, stderr=DEVNULL)      ← plugin writes its own log file
       │
       └─ plugin process starts
            │
            ├─ log_setup.init("plugin-telegram", log_dir)  ← rotating log file
            │
            ├─ PluginTransport.run()
            │     ├─ connects to ws://127.0.0.1:18081
            │     ├─ sends channel.register notification
            │     └─ calls plugin.on_start()
            │
            └─ [running — polling / webhooks / forwarding messages]
                 logs → ~/.phbcli/logs/plugin-telegram.log

phbcli stop
  │
  ├─ stop_event.set()
  │
  ├─ PluginManager sends channel.stop to each plugin
  │
  ├─ waits 1 second
  │
  └─ terminates any remaining subprocesses
```

---

## uv workspace layout

```
phbserver/
├── pyproject.toml              # workspace root: members = [..., "phb-channel-sdk", "channels/*"]
├── phb-channel-sdk/            # shared SDK (workspace member)
└── channels/
    ├── phb-channel-echo/       # echo test plugin (workspace member)
    ├── phb-channel-telegram/   # (future)
    └── phb-channel-whatsapp/   # (future)
```

Each channel package declares:

```toml
[project]
dependencies = ["phb-channel-sdk", "python-telegram-bot>=21"]

[tool.uv.sources]
phb-channel-sdk = { workspace = true }
```

This gives each plugin its own isolated virtualenv while sharing the same
resolved lockfile for the workspace's common dependencies.

---

## Adding a new channel — checklist

1. `phbcli channel install <name>` — install the package
2. `phbcli channel setup <name>` — configure command + credentials
3. Restart phbcli: `phbcli stop && phbcli start`
4. Verify: `phbcli channel status`
