"""Config and state file management for phbcli.

Files live under ~/.phbcli/:
  config.json  — persistent settings (device_id, gateway_url, http_port)
  state.json   — runtime state updated by the running server process
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

APP_DIR = Path.home() / ".phbcli"
CONFIG_FILE = APP_DIR / "config.json"
STATE_FILE = APP_DIR / "state.json"
PID_FILE = APP_DIR / "phbcli.pid"


class Config(BaseModel):
    device_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gateway_url: str = "ws://localhost:8765"
    http_host: str = "127.0.0.1"
    http_port: int = 18080


class State(BaseModel):
    ws_connected: bool = False
    last_connected: Optional[str] = None  # ISO 8601
    gateway_url: Optional[str] = None


def ensure_app_dir() -> Path:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DIR


def load_config() -> Config:
    ensure_app_dir()
    if CONFIG_FILE.exists():
        return Config.model_validate_json(CONFIG_FILE.read_text(encoding="utf-8"))
    return Config()


def save_config(config: Config) -> None:
    ensure_app_dir()
    CONFIG_FILE.write_text(
        config.model_dump_json(indent=2), encoding="utf-8"
    )


def load_state() -> State:
    ensure_app_dir()
    if STATE_FILE.exists():
        try:
            return State.model_validate_json(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return State()


def save_state(state: State) -> None:
    ensure_app_dir()
    STATE_FILE.write_text(
        state.model_dump_json(indent=2), encoding="utf-8"
    )


def mark_connected(gateway_url: str) -> None:
    state = load_state()
    state.ws_connected = True
    state.last_connected = datetime.now(timezone.utc).isoformat()
    state.gateway_url = gateway_url
    save_state(state)


def mark_disconnected() -> None:
    state = load_state()
    state.ws_connected = False
    save_state(state)
