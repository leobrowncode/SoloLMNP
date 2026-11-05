"""Local Ed25519 key used to imitate a Neon Auth access token. Not a credential."""

from __future__ import annotations

import base64
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jwt import PyJWKClient

from app.core import auth as auth_module

KID = "neon-test"


def ed25519_jwks(kid: str = KID) -> tuple[Ed25519PrivateKey, dict[str, object]]:
    private = Ed25519PrivateKey.generate()
    raw = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    document: dict[str, object] = {
        "keys": [
            {
                "kty": "OKP",
                "crv": "Ed25519",
                "x": base64.urlsafe_b64encode(raw).decode().rstrip("="),
                "kid": kid,
                "alg": "EdDSA",
                "use": "sig",
            }
        ]
    }
    return private, document


def install_jwks(monkeypatch: pytest.MonkeyPatch, document: dict[str, object]) -> None:
    monkeypatch.setattr(auth_module, "_jwks_clients", {})

    def fetch(self: PyJWKClient) -> dict[str, object]:
        del self
        return document

    monkeypatch.setattr(PyJWKClient, "fetch_data", fetch)


def sign_neon(
    private: Ed25519PrivateKey,
    *,
    issuer: str,
    audience: str | None,
    email: str | None,
    subject: str = "test-ada",
    kid: str = KID,
    expired: bool = False,
) -> str:
    """Claims follow the Neon Auth JWT example: iss and aud are the origin."""
    now = int(time.time())
    payload: dict[str, object] = {
        "iat": now,
        "name": "Ada Lovelace",
        "emailVerified": True,
        "role": "authenticated",
        "sub": subject,
        "iss": issuer,
        "exp": now - 120 if expired else now + 900,
    }
    if email is not None:
        payload["email"] = email
    if audience is not None:
        payload["aud"] = audience
    token = jwt.encode(payload, private, algorithm="EdDSA", headers={"kid": kid})
    if isinstance(token, bytes):
        return token.decode()
    return token
