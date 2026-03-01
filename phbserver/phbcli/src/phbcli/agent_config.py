"""Agent configuration management for phbcli.

Files live under ~/.phbcli/agent/:
  config.json       — LLM provider, model name, and generation parameters
  system_prompt.md  — markdown system prompt loaded verbatim into the agent
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .config import APP_DIR

logger = logging.getLogger(__name__)

AGENT_DIR = APP_DIR / "agent"
AGENT_CONFIG_FILE = AGENT_DIR / "config.json"
AGENT_SYSTEM_PROMPT_FILE = AGENT_DIR / "system_prompt.md"

_DEFAULT_SYSTEM_PROMPT = """\
You are a helpful home assistant running on Private Home Box.
Answer questions concisely and helpfully.
"""

_DEFAULT_CONFIG: dict[str, Any] = {
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "temperature": 0.7,
    "max_tokens": 1024,
}


class AgentConfig(BaseModel):
    """LLM provider and generation settings for the agent."""

    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1)

    @property
    def model_string(self) -> str:
        """Return the 'provider:model' identifier used by init_chat_model."""
        return f"{self.provider}:{self.model}"


def ensure_agent_dir() -> Path:
    AGENT_DIR.mkdir(parents=True, exist_ok=True)
    return AGENT_DIR


def load_agent_config() -> AgentConfig:
    """Load agent config from file, writing defaults if absent."""
    ensure_agent_dir()
    if AGENT_CONFIG_FILE.exists():
        try:
            return AgentConfig.model_validate_json(
                AGENT_CONFIG_FILE.read_text(encoding="utf-8")
            )
        except Exception as exc:
            logger.warning("Failed to parse agent config, using defaults: %s", exc)
    else:
        _write_default_config()
    return AgentConfig()


def save_agent_config(config: AgentConfig) -> None:
    ensure_agent_dir()
    AGENT_CONFIG_FILE.write_text(
        config.model_dump_json(indent=2), encoding="utf-8"
    )


def load_system_prompt() -> str:
    """Load the system prompt from file, writing the default if absent."""
    ensure_agent_dir()
    if AGENT_SYSTEM_PROMPT_FILE.exists():
        return AGENT_SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
    _write_default_system_prompt()
    return _DEFAULT_SYSTEM_PROMPT.strip()


def _write_default_config() -> None:
    ensure_agent_dir()
    AGENT_CONFIG_FILE.write_text(
        json.dumps(_DEFAULT_CONFIG, indent=2), encoding="utf-8"
    )
    logger.info("Created default agent config at %s", AGENT_CONFIG_FILE)


def _write_default_system_prompt() -> None:
    ensure_agent_dir()
    AGENT_SYSTEM_PROMPT_FILE.write_text(_DEFAULT_SYSTEM_PROMPT, encoding="utf-8")
    logger.info("Created default system prompt at %s", AGENT_SYSTEM_PROMPT_FILE)
