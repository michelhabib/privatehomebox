# phbcli

**Private Home Box CLI** — desktop server with WebSocket gateway client.

## Installation from PyPI

```bash
pip install phbcli
```

## Installation from source

```bash
uv tool install --editable ./phbcli
```

## Quick Start

```bash
# One-time setup: configure gateway, generate device ID, register auto-start
phbcli setup

# If needed on Windows, request UAC to create elevated scheduled task
phbcli setup --elevated-task

# Manual start / stop
phbcli start
phbcli stop

# Check status
phbcli status

# Cleanup auto-start and running process
phbcli teardown

# Full uninstall flow (teardown + prints final package uninstall command)
phbcli uninstall
```

## Commands

| Command | Description |
|---------|-------------|
| `setup` | Interactive first-time configuration. Creates `~/.phbcli/`, generates device ID, registers Windows auto-start, then starts the server. On Windows it tries Task Scheduler first, then falls back to HKCU Run key if needed. |
| `start` | Start the background server (FastAPI HTTP + WS client). |
| `stop`  | Stop the running server. |
| `status`| Show whether the server is running, WebSocket connection state, last connection time, and gateway URL. |
| `teardown`| Stop the server and remove auto-start entries (Task Scheduler + Registry). Optional: `--purge` to remove `~/.phbcli/`; `--elevated-task` for elevated task removal. |
| `uninstall`| Runs teardown, then prints package uninstall command (`uv tool uninstall phbcli` or `pip uninstall phbcli`). |

## Windows Auto-Start Behavior

- Default `setup` flow:
  1. Attempt Task Scheduler (`schtasks`, run-level `LIMITED`)
  2. If unavailable/denied, fall back to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- Use `--elevated-task` to request UAC and create/delete a `run-level: HIGHEST` scheduled task.

## App Directory

All runtime data is stored in `~/.phbcli/`:

- `config.json` — device ID and gateway URL
- `state.json` — live WebSocket connection state (updated by the running server)
- `phbcli.pid` — PID of the running server process

## HTTP API

When running, the server exposes a local HTTP API at `http://127.0.0.1:18080`:

- `GET /status` — returns server/connection status as JSON
