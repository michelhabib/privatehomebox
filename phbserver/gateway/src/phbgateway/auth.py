"""Authentication helpers for gateway connection handshakes."""

from __future__ import annotations

import base64
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def _b64_decode(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"), validate=True)


def _b64_encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _parse_iso8601_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return dt.astimezone(UTC)


def _load_public_key_b64(public_key_b64: str) -> Ed25519PublicKey:
    raw = _b64_decode(public_key_b64)
    if len(raw) != 32:
        raise ValueError("Ed25519 public key must be exactly 32 bytes")
    return Ed25519PublicKey.from_public_bytes(raw)


def generate_nonce() -> str:
    """Create a random challenge nonce encoded as hex."""
    return secrets.token_hex(32)


@dataclass
class AuthResult:
    ok: bool
    device_id: str | None = None
    reason: str | None = None


class GatewayAuthManager:
    """Stores desktop trust root and validates desktop/device auth payloads."""

    def __init__(
        self,
        *,
        state_file: Path,
        desktop_public_key_b64: str | None = None,
    ) -> None:
        self._state_file = state_file
        self._desktop_public_key: Ed25519PublicKey | None = None

        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_state_if_exists()

        if desktop_public_key_b64:
            self._desktop_public_key = _load_public_key_b64(desktop_public_key_b64)
            self._save_state()

    def is_claimed(self) -> bool:
        return self._desktop_public_key is not None

    def desktop_public_key_b64(self) -> str | None:
        if self._desktop_public_key is None:
            return None
        raw = self._desktop_public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        return _b64_encode(raw)

    def verify_desktop_claim(
        self,
        *,
        nonce_hex: str,
        public_key_b64: str,
        nonce_signature_b64: str,
    ) -> AuthResult:
        try:
            key = _load_public_key_b64(public_key_b64)
            key.verify(_b64_decode(nonce_signature_b64), bytes.fromhex(nonce_hex))
        except Exception:
            return AuthResult(ok=False, reason="desktop claim signature invalid")

        if self._desktop_public_key is not None:
            # Idempotent claim from the same desktop key is accepted.
            current = self._desktop_public_key.public_bytes(
                encoding=Encoding.Raw,
                format=PublicFormat.Raw,
            )
            incoming = key.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
            if current != incoming:
                return AuthResult(ok=False, reason="gateway already claimed by another desktop")
            return AuthResult(ok=True)

        self._desktop_public_key = key
        self._save_state()
        return AuthResult(ok=True)

    def verify_desktop_auth(self, *, nonce_hex: str, nonce_signature_b64: str) -> AuthResult:
        key = self._desktop_public_key
        if key is None:
            return AuthResult(ok=False, reason="gateway not claimed by desktop yet")
        try:
            key.verify(_b64_decode(nonce_signature_b64), bytes.fromhex(nonce_hex))
            return AuthResult(ok=True)
        except Exception:
            return AuthResult(ok=False, reason="desktop signature invalid")

    def verify_device_auth(
        self,
        *,
        nonce_hex: str,
        attestation_blob: str,
        desktop_signature_b64: str,
        nonce_signature_b64: str,
    ) -> AuthResult:
        root_key = self._desktop_public_key
        if root_key is None:
            return AuthResult(ok=False, reason="gateway not claimed by desktop yet")

        try:
            root_key.verify(
                _b64_decode(desktop_signature_b64),
                attestation_blob.encode("utf-8"),
            )
        except Exception:
            return AuthResult(ok=False, reason="attestation signature invalid")

        try:
            blob: dict[str, Any] = json.loads(attestation_blob)
        except Exception:
            return AuthResult(ok=False, reason="attestation blob is not valid JSON")

        device_id = blob.get("device_id")
        device_public_key_b64 = blob.get("device_public_key")
        expires_at = blob.get("expires_at")

        if not isinstance(device_id, str) or not device_id:
            return AuthResult(ok=False, reason="attestation missing device_id")
        if not isinstance(device_public_key_b64, str) or not device_public_key_b64:
            return AuthResult(ok=False, reason="attestation missing device_public_key")
        if not isinstance(expires_at, str) or not expires_at:
            return AuthResult(ok=False, reason="attestation missing expires_at")

        try:
            expiry = _parse_iso8601_utc(expires_at)
        except Exception:
            return AuthResult(ok=False, reason="attestation expires_at invalid")
        if expiry <= datetime.now(UTC):
            return AuthResult(ok=False, reason="attestation expired")

        try:
            device_key = _load_public_key_b64(device_public_key_b64)
            device_key.verify(_b64_decode(nonce_signature_b64), bytes.fromhex(nonce_hex))
        except Exception:
            return AuthResult(ok=False, reason="device nonce signature invalid")

        return AuthResult(ok=True, device_id=device_id)

    def _load_state_if_exists(self) -> None:
        if not self._state_file.exists():
            return
        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
            public_key_b64 = payload.get("desktop_public_key")
            if isinstance(public_key_b64, str) and public_key_b64:
                self._desktop_public_key = _load_public_key_b64(public_key_b64)
        except Exception:
            # Corrupt state should not crash startup; gateway can be re-claimed.
            self._desktop_public_key = None

    def _save_state(self) -> None:
        payload = {
            "desktop_public_key": self.desktop_public_key_b64(),
            "claimed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        self._state_file.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
