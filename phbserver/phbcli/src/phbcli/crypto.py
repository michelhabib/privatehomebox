"""Cryptographic helpers for PHB desktop identity and attestations.

This module centralizes Ed25519 key handling used by phbcli as the trust root:
- desktop master key persistence
- nonce signing for gateway authentication
- device attestation creation/signing
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)

MASTER_KEY_FILE = "master_key.pem"


def _b64_encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64_decode(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"), validate=True)


def generate_private_key() -> Ed25519PrivateKey:
    """Generate a new Ed25519 private key."""
    return Ed25519PrivateKey.generate()


def public_key_to_b64(public_key: Ed25519PublicKey) -> str:
    """Encode an Ed25519 public key in base64 (raw 32-byte form)."""
    raw = public_key.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
    return _b64_encode(raw)


def private_key_to_pem(private_key: Ed25519PrivateKey) -> bytes:
    """Serialize a private key to unencrypted PKCS8 PEM."""
    return private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )


def load_private_key_pem(pem: bytes) -> Ed25519PrivateKey:
    """Load a private key from unencrypted PKCS8 PEM bytes."""
    key = load_pem_private_key(pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("Expected an Ed25519 private key")
    return key


def load_public_key_b64(public_key_b64: str) -> Ed25519PublicKey:
    """Load an Ed25519 public key from base64 raw bytes."""
    raw = _b64_decode(public_key_b64)
    if len(raw) != 32:
        raise ValueError("Ed25519 public key must be exactly 32 bytes")
    return Ed25519PublicKey.from_public_bytes(raw)


def load_public_key_pem(pem: bytes) -> Ed25519PublicKey:
    """Load an Ed25519 public key from PEM bytes."""
    key = load_pem_public_key(pem)
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("Expected an Ed25519 public key")
    return key


def load_or_create_master_key(app_dir: Path, filename: str = MASTER_KEY_FILE) -> Ed25519PrivateKey:
    """Load existing desktop master key or create one if absent."""
    app_dir.mkdir(parents=True, exist_ok=True)
    key_path = app_dir / filename
    if key_path.exists():
        return load_private_key_pem(key_path.read_bytes())

    private_key = generate_private_key()
    key_path.write_bytes(private_key_to_pem(private_key))
    try:
        key_path.chmod(0o600)
    except OSError:
        # Windows doesn't fully support POSIX perms via chmod.
        pass
    return private_key


def sign_bytes(private_key: Ed25519PrivateKey, data: bytes) -> str:
    """Sign arbitrary bytes and return a base64 signature."""
    return _b64_encode(private_key.sign(data))


def verify_signature(public_key: Ed25519PublicKey, data: bytes, signature_b64: str) -> bool:
    """Verify a base64 signature for arbitrary bytes."""
    try:
        signature = _b64_decode(signature_b64)
        public_key.verify(signature, data)
    except Exception:
        return False
    return True


def sign_nonce(private_key: Ed25519PrivateKey, nonce_hex: str) -> str:
    """Sign a hex nonce value from the gateway challenge."""
    nonce_bytes = bytes.fromhex(nonce_hex)
    return sign_bytes(private_key, nonce_bytes)


def desktop_public_key_b64(private_key: Ed25519PrivateKey) -> str:
    """Return the desktop public key in base64."""
    return public_key_to_b64(private_key.public_key())


def create_device_attestation(
    private_key: Ed25519PrivateKey,
    *,
    device_id: str,
    device_public_key_b64: str,
    expires_days: int = 30,
) -> dict[str, Any]:
    """Create and sign a device attestation blob.

    The blob is canonical JSON (stable key order, compact separators) to make
    signature verification deterministic across runtimes.
    """
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(days=expires_days)
    blob_obj = {
        "device_id": device_id,
        "device_public_key": device_public_key_b64,
        "issued_at": issued_at.isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
    }
    blob = json.dumps(blob_obj, separators=(",", ":"), sort_keys=True)
    signature = sign_bytes(private_key, blob.encode("utf-8"))
    return {"blob": blob, "desktop_signature": signature}
