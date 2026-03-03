
# Agent Manager

## Overview

The `AgentManager` is the LLM brain of phbcli. It runs as a long-lived asyncio
task alongside the `CommunicationManager` and `PluginManager`. On every inbound
text message it invokes a LangChain v1 `create_agent` instance, maintains
per-conversation memory, and pushes the reply back through the outbound queue
to the originating channel.

---

## Design goals

| Goal | How it is achieved |
|---|---|
| Provider agnostic | Provider and model are read from a config file; `init_chat_model` abstracts the provider package |
| Conversation memory | LangGraph `InMemorySaver` checkpointer; each conversation keyed by `channel:sender_id` |
| Graceful errors | LLM failures enqueue a human-readable fallback reply instead of dropping the message |
| Extensible | Tools list is empty now; any LangChain `@tool` can be added later |
| Config as files | All settings live under `~/.phbcli/agent/`; no env-var coupling |

---

## System diagram

```
CommunicationManager
  inbound_queue  ──►  AgentManager._process(msg)
                              │
                              ▼
                    LangChain create_agent
                    (model, system_prompt,
                     InMemorySaver checkpointer)
                              │
                         thread_id =
                    "channel:sender_id"
                              │
                              ▼
                       reply UnifiedMessage
                              │
  outbound_queue  ◄──  comm_manager.enqueue_outbound(reply)
```

---

## Configuration files

All agent configuration lives under `~/.phbcli/agent/`.  Files are created
with safe defaults on first run if they are absent.

### `~/.phbcli/agent/config.json`

```json
{
  "provider": "openai",
  "model": "gpt-4.1-mini",
  "temperature": 0.7,
  "max_tokens": 1024
}
```

| Field | Type | Description |
|---|---|---|
| `provider` | string | LangChain provider identifier (e.g. `openai`, `anthropic`, `ollama`) |
| `model` | string | Model name understood by the provider (e.g. `gpt-4.1-mini`, `claude-sonnet-4-5`) |
| `temperature` | float 0–2 | Sampling temperature |
| `max_tokens` | int | Maximum tokens in the generated reply |

The `provider` and `model` fields are combined internally as `"provider:model"`
and passed to `langchain.chat_models.init_chat_model`.

**Switching providers** requires the corresponding provider package to be
installed, e.g.:

```bash
# Anthropic
uv add langchain-anthropic

# Ollama (local)
uv add langchain-ollama
```

Then update `config.json`:

```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-5-20250929"
}
```

### `~/.phbcli/agent/system_prompt.md`

A plain markdown file loaded verbatim as the agent's system prompt.  Edit it
to change the agent's persona, tone, or domain focus.  The file is re-read
only on server restart.

Default content:

```
You are a helpful home assistant running on Private Home Box.
Answer questions concisely and helpfully.
```

---

## Message flow

```
1. Channel plugin receives a user message
        │
        ▼
2. PluginManager → CommunicationManager.receive()
        │  (validate, permission check)
        ▼
3. CommunicationManager.inbound_queue
        │
        ▼
4. AgentManager.run() dequeues the message
        │  content_type != "text" → silently ignored
        ▼
5. AgentManager._process(msg)
        │
        ├─ thread_id = f"{msg.channel}:{msg.sender_id}"
        │
        ├─ agent.ainvoke(
        │      {"messages": [{"role": "user", "content": msg.body}]},
        │      config={"configurable": {"thread_id": thread_id}}
        │  )
        │
        ├─ on success → reply_body = result["messages"][-1].content
        └─ on error   → reply_body = fallback error string
        │
        ▼
6. UnifiedMessage reply constructed:
        channel      = inbound.channel
        recipient_id = inbound.sender_id
        direction    = "outbound"
        content_type = "text"
        body         = reply_body
        id           = new uuid4
        timestamp    = now(UTC)
        │
        ▼
7. CommunicationManager.outbound_queue → PluginManager → channel plugin → user
```

---

## Conversation memory

The `AgentManager` creates one `InMemorySaver` checkpointer shared across all
conversations.  Each conversation is isolated by its `thread_id`
(`channel:sender_id`).  The checkpointer stores the full message history per
thread in memory.

**Limitation:** Memory is lost on server restart.  For persistence across
restarts, replace `InMemorySaver` with `SqliteSaver` or `PostgresSaver` from
LangGraph (future work).

---

## Lifecycle

`AgentManager` is constructed in `_server_process._main()` after
`CommunicationManager` is set up, then added to the server task group
alongside the other long-running coroutines:

```python
agent_manager = AgentManager(comm_manager)

# All coroutines run as a single gathered task so the server can cancel
# them cleanly when the stop_event fires.
server_task = asyncio.ensure_future(asyncio.gather(
    run_http_server(config, stop_event),
    plugin_manager.run(),
    comm_manager.run(),
    agent_manager.run(),   # ← single sequential worker
    return_exceptions=True,
))
await stop_event.wait()
await asyncio.sleep(1.5)   # give plugin_manager its graceful-shutdown window
server_task.cancel()
```

The `run()` loop is intentionally sequential (one message at a time) for
simplicity.  Concurrent processing per conversation (or per channel) can be
added later without changing the `CommunicationManager` interface.

---

## Adding tools

Tools are passed to `create_agent` at construction time.  To add a tool:

1. Define it in a new module, e.g. `phbcli/tools/home_control.py`:

```python
from langchain.tools import tool

@tool
def turn_on_light(room: str) -> str:
    """Turn on the light in the specified room."""
    # ... implementation ...
    return f"Light in {room} turned on."
```

2. Register it in `AgentManager._build_agent()`:

```python
from phbcli.tools.home_control import turn_on_light

return create_agent(
    model=model,
    tools=[turn_on_light],
    system_prompt=system_prompt,
    checkpointer=InMemorySaver(),
)
```

---

## Module reference

| File | Purpose |
|---|---|
| `phbcli/src/phbcli/agent_manager.py` | `AgentManager` class — asyncio worker |
| `phbcli/src/phbcli/agent_config.py` | `AgentConfig` model, path constants, file loaders |
| `~/.phbcli/agent/config.json` | Runtime: provider/model/params |
| `~/.phbcli/agent/system_prompt.md` | Runtime: agent system prompt |
