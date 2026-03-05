"""Config and state file management for phbcli.

All files live under the resolved workspace directory.  No module-level
path constants exist — every helper accepts a workspace_path: Path argument.

Workspace layout:
  <workspace>/
    config.json
    state.json
    master_key.pem
    logs/
    channels/
    agent/
    pairing_session.json
    devices.json
    phbcli.pid
    gateway instances are managed separately by phbgateway
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from phb_commons.constants.domain import (
    DEFAULT_ATTESTATION_EXPIRY_DAYS,
    DEFAULT_PAIRING_CODE_LENGTH,
    DEFAULT_PAIRING_CODE_TTL_SECONDS,
)
from phb_commons.constants.network import (
    DEFAULT_GATEWAY_PORT,
    DEFAULT_LOCALHOST,
    PORT_OFFSET_HTTP,
    PORT_OFFSET_PLUGIN,
    PORT_RANGE_START,
)
from phb_commons.constants.storage import CONFIG_FILENAME, LOGS_DIR, MASTER_KEY_FILENAME


class Config(BaseModel):
    device_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gateway_url: str = f"ws://localhost:{DEFAULT_GATEWAY_PORT}"
    http_host: str = DEFAULT_LOCALHOST
    http_port: int = PORT_RANGE_START + PORT_OFFSET_HTTP
    plugin_port: int = PORT_RANGE_START + PORT_OFFSET_PLUGIN
    master_key_file: str = MASTER_KEY_FILENAME
    pairing_code_length: int = DEFAULT_PAIRING_CODE_LENGTH
    pairing_code_ttl_seconds: int = DEFAULT_PAIRING_CODE_TTL_SECONDS
    attestation_expires_days: int = DEFAULT_ATTESTATION_EXPIRY_DAYS
    log_dir: str = ""
    log_levels: dict[str, str] = Field(default_factory=dict)


class State(BaseModel):
    ws_connected: bool = False
    last_connected: Optional[str] = None  # ISO 8601
    gateway_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def workspace_config_file(workspace_path: Path) -> Path:
    return workspace_path / CONFIG_FILENAME


def workspace_state_file(workspace_path: Path) -> Path:
    return workspace_path / "state.json"


def workspace_log_dir(workspace_path: Path) -> Path:
    return workspace_path / LOGS_DIR


def master_key_path(workspace_path: Path, config: Config) -> Path:
    return workspace_path / config.master_key_file


def resolve_log_dir(workspace_path: Path, config: Config) -> Path:
    """Return the effective log directory, falling back to <workspace>/logs/."""
    if config.log_dir:
        return Path(config.log_dir)
    return workspace_log_dir(workspace_path)


# ---------------------------------------------------------------------------
# Config I/O
# ---------------------------------------------------------------------------

def load_config(workspace_path: Path) -> Config:
    workspace_path.mkdir(parents=True, exist_ok=True)
    cfg_file = workspace_config_file(workspace_path)
    if cfg_file.exists():
        return Config.model_validate_json(cfg_file.read_text(encoding="utf-8"))
    return Config()


def save_config(workspace_path: Path, config: Config) -> None:
    workspace_path.mkdir(parents=True, exist_ok=True)
    workspace_config_file(workspace_path).write_text(
        config.model_dump_json(indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# State I/O
# ---------------------------------------------------------------------------

def load_state(workspace_path: Path) -> State:
    workspace_path.mkdir(parents=True, exist_ok=True)
    state_file = workspace_state_file(workspace_path)
    if state_file.exists():
        try:
            return State.model_validate_json(state_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return State()


def save_state(workspace_path: Path, state: State) -> None:
    workspace_path.mkdir(parents=True, exist_ok=True)
    workspace_state_file(workspace_path).write_text(
        state.model_dump_json(indent=2), encoding="utf-8"
    )


def mark_connected(workspace_path: Path, gateway_url: str) -> None:
    state = load_state(workspace_path)
    state.ws_connected = True
    state.last_connected = datetime.now(timezone.utc).isoformat()
    state.gateway_url = gateway_url
    save_state(workspace_path, state)


def mark_disconnected(workspace_path: Path) -> None:
    state = load_state(workspace_path)
    state.ws_connected = False
    save_state(workspace_path, state)
