"""Verify a Neon Auth JWT, or a test token when the app is explicitly in test mode.

Production never accepts the test issuer. The test secret is not a Neon credential.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

from app.core.config import Settings

TEST_ISSUER = "sololmnp-test"
TEST_EMAIL = "ada@sololmnp.test"
TEST_SUBJECT = "test-ada"
TEST_SECRET = "sololmnp-test-auth-secret"  # noqa: S105
OTHER_EMAIL = "bea@sololmnp.test"
OTHER_SUBJECT = "test-bea"

_jwks_clients: dict[str, PyJWKClient] = {}


@dataclass(frozen=True)
class Principal:
    subject: str
    email: str


class AuthError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def issue_test_token(
    secret: str,
    *,
    email: str = TEST_EMAIL,
    subject: str = TEST_SUBJECT,
    expired: bool = False,
) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "email": email,
        "iss": TEST_ISSUER,
        "iat": now,
        "exp": now - 60 if expired else now + 3600,
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    if isinstance(token, bytes):
        return token.decode()
    return token


def verify_authorization(settings: Settings, header: str | None) -> Principal:
    if settings.auth_mode == "test":
        if settings.app_env != "test":
            raise AuthError(401, "UNAUTHENTICATED", "Authentification d’essai refusée.")
        return _verify_test(settings, _bearer(header))
    return _verify_neon(settings, _bearer(header))


def _bearer(header: str | None) -> str:
    if header is None or not header.lower().startswith("bearer "):
        raise AuthError(401, "UNAUTHENTICATED", "Connectez-vous pour continuer.")
    token = header.split(" ", 1)[1].strip()
    if not token:
        raise AuthError(401, "UNAUTHENTICATED", "Connectez-vous pour continuer.")
    return token


def _verify_test(settings: Settings, token: str) -> Principal:
    if not settings.auth_test_secret:
        raise AuthError(
            401, "AUTH_NOT_CONFIGURED", "L’authentification d’essai n’est pas configurée."
        )
    try:
        payload = jwt.decode(
            token,
            settings.auth_test_secret,
            algorithms=["HS256"],
            issuer=TEST_ISSUER,
            options={"require": ["exp", "sub", "iss"]},
            leeway=30,
        )
    except PyJWTError as exc:
        raise AuthError(401, "INVALID_TOKEN", "Session expirée ou jeton refusé.") from exc
    return _principal(settings, payload)


def _verify_neon(settings: Settings, token: str) -> Principal:
    if not settings.neon_auth_base_url or not settings.neon_auth_jwks_url:
        raise AuthError(401, "AUTH_NOT_CONFIGURED", "L’authentification n’est pas configurée.")
    issuer = settings.neon_auth_base_url
    try:
        signing_key = _jwks(settings.neon_auth_jwks_url).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["EdDSA"],
            issuer=issuer,
            options={"require": ["exp", "sub", "iss"], "verify_aud": False},
            leeway=30,
        )
    except PyJWTError as exc:
        raise AuthError(401, "INVALID_TOKEN", "Session expirée ou jeton refusé.") from exc
    return _principal(settings, payload)


def _principal(settings: Settings, payload: object) -> Principal:
    if not isinstance(payload, dict):
        raise AuthError(401, "INVALID_TOKEN", "Jeton illisible.")
    subject = payload.get("sub")
    email = payload.get("email")
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 200:
        raise AuthError(401, "INVALID_TOKEN", "Jeton sans identifiant.")
    if not isinstance(email, str) or "@" not in email or len(email) > 320:
        raise AuthError(401, "INVALID_TOKEN", "Jeton sans adresse e-mail.")
    normalized = email.strip().lower()
    allowed = {item.lower() for item in settings.allowed_emails}
    if normalized not in allowed:
        raise AuthError(403, "EMAIL_NOT_ALLOWED", "Cette adresse n’est pas autorisée.")
    return Principal(subject=subject.strip(), email=normalized)


def _jwks(url: str) -> PyJWKClient:
    client = _jwks_clients.get(url)
    if client is None:
        client = PyJWKClient(url, cache_keys=True, lifespan=3600)
        _jwks_clients[url] = client
    return client
