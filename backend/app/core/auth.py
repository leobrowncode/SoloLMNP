"""Verify a Neon Auth JWT, a test token, or the single local dossier.

Production never accepts the test issuer. The test secret is not a Neon credential.
``AUTH_MODE=local`` returns one fixed account and only when ``APP_ENV`` is
``development`` and the process is not running on Vercel. It is not a password.

Neon Auth signs ``iss`` and ``aud`` with the origin of ``NEON_AUTH_BASE_URL``
(``https://ep.example``), not the managed path that ends in ``/neondb/auth``.
The JWKS URL keeps that path.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

from app.core.config import Settings, local_mode_allowed

logger = logging.getLogger(__name__)
_COMPACT_JWT = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")

TEST_ISSUER = "sololmnp-test"
TEST_EMAIL = "ada@sololmnp.test"
TEST_SUBJECT = "test-ada"
TEST_SECRET = "sololmnp-test-auth-secret"  # noqa: S105
OTHER_EMAIL = "bea@sololmnp.test"
OTHER_SUBJECT = "test-bea"
LOCAL_SUBJECT = "sololmnp-local"
LOCAL_EMAIL = "local@sololmnp.dev"

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
    if settings.auth_mode == "local":
        if not local_mode_allowed(settings):
            raise AuthError(401, "UNAUTHENTICATED", "Authentification locale refusée.")
        return Principal(subject=LOCAL_SUBJECT, email=LOCAL_EMAIL)
    if settings.auth_mode == "test":
        if settings.app_env != "test" or os.environ.get("VERCEL") == "1":
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
    # Docs: issuer and audience are the origin, e.g. https://ep.example
    # when the base URL is https://ep.example/neondb/auth.
    origin = _neon_origin(settings.neon_auth_base_url)
    try:
        signing_key = _jwks(settings.neon_auth_jwks_url).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["EdDSA"],
            issuer=origin,
            audience=origin,
            options={"require": ["exp", "sub", "iss", "aud"]},
            leeway=30,
        )
    except PyJWTError as exc:
        _log_rejected_neon_jwt(token, exc)
        raise AuthError(401, "INVALID_TOKEN", "Session expirée ou jeton refusé.") from exc
    return _principal(settings, payload)


def _neon_origin(base_url: str) -> str:
    parsed = urlsplit(base_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _log_rejected_neon_jwt(token: str, exc: PyJWTError) -> None:
    """Record alg, kid, iss and whether an email claim exists. Never the token."""
    try:
        alg, kid, issuer, has_email = _jwt_diagnostics(token)
    except Exception:
        logger.warning("Jeton Neon refusé error=%s", type(exc).__name__)
        return
    logger.warning(
        "Jeton Neon refusé alg=%s kid=%s iss=%s has_email=%s error=%s",
        alg or "-",
        kid or "-",
        issuer or "-",
        has_email,
        type(exc).__name__,
    )


def _jwt_diagnostics(token: str) -> tuple[str | None, str | None, str | None, bool]:
    header = _json_segment(token, 0)
    claims = _json_segment(token, 1)
    alg = _safe_label(header.get("alg")) if isinstance(header, dict) else None
    kid = _safe_label(header.get("kid")) if isinstance(header, dict) else None
    issuer = _safe_label(claims.get("iss")) if isinstance(claims, dict) else None
    email = claims.get("email") if isinstance(claims, dict) else None
    has_email = isinstance(email, str) and "@" in email and len(email) <= 320
    return alg, kid, issuer, has_email


def _json_segment(token: str, index: int) -> object:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    segment = parts[index]
    try:
        raw = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
        return json.loads(raw)
    except (ValueError, json.JSONDecodeError, UnicodeError):
        return None


def _safe_label(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 300 or _COMPACT_JWT.fullmatch(cleaned):
        return None
    return cleaned


def _allowed_emails(settings: Settings) -> set[str]:
    return {item.lower() for item in settings.allowed_emails}


def ensure_email_allowed(settings: Settings, email: str) -> str:
    """Return a normalized address or raise when it is outside ALLOWED_EMAILS."""
    normalized = email.strip().lower()
    if (
        not normalized
        or "@" not in normalized
        or len(normalized) > 320
        or any(char.isspace() for char in normalized)
    ):
        raise AuthError(400, "INVALID_EMAIL", "Indiquez une adresse e-mail valide.")
    if normalized not in _allowed_emails(settings):
        raise AuthError(403, "EMAIL_NOT_ALLOWED", "Cette adresse n’est pas autorisée.")
    return normalized


def _principal(settings: Settings, payload: object) -> Principal:
    if not isinstance(payload, dict):
        raise AuthError(401, "INVALID_TOKEN", "Jeton illisible.")
    subject = payload.get("sub")
    email = payload.get("email")
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 200:
        raise AuthError(401, "INVALID_TOKEN", "Jeton sans identifiant.")
    if not isinstance(email, str):
        raise AuthError(401, "INVALID_TOKEN", "Jeton sans adresse e-mail.")
    normalized = ensure_email_allowed(settings, email)
    return Principal(subject=subject.strip(), email=normalized)


def _jwks(url: str) -> PyJWKClient:
    client = _jwks_clients.get(url)
    if client is None:
        client = PyJWKClient(url, cache_keys=True, lifespan=3600)
        _jwks_clients[url] = client
    return client
