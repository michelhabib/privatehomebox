"""Shared Pydantic models — the lingua franca of the plugin system."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class UnifiedMessage(BaseModel):
    """Canonical cross-channel message format.

    All channels translate their native format to and from this model.
    ``direction`` is always the perspective of phbcli:
      - "inbound"  — arriving FROM the third party (e.g., user sent a Telegram msg)
      - "outbound" — to be SENT TO the third party (e.g., send a Telegram reply)
    """

    id: str = Field(default_factory=lambda: uuid4().hex)
    channel: str
    direction: str  # "inbound" | "outbound"
    sender_id: str
    recipient_id: str | None = None
    content_type: str = "text"  # "text" | "image" | "audio" | "location" | "command"
    body: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class RpcRequest(BaseModel):
    """JSON-RPC 2.0 request or notification (notification when id is None)."""

    jsonrpc: str = "2.0"
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    id: str | int | None = None


class RpcResponse(BaseModel):
    """JSON-RPC 2.0 response."""

    jsonrpc: str = "2.0"
    result: Any = None
    error: dict[str, Any] | None = None
    id: str | int | None = None


class ChannelInfo(BaseModel):
    """Self-description that a channel sends on registration."""

    name: str
    version: str = "0.1.0"
    description: str = ""
