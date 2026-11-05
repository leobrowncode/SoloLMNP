"""Neon Auth JWTs are signed for the origin of NEON_AUTH_BASE_URL, not its path."""

import logging

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.auth import TEST_EMAIL, TEST_SUBJECT, AuthError, verify_authorization
from app.core.config import Settings
from tests.neon_jwt import KID, ed25519_jwks, install_jwks, sign_neon

BASE = "https://ep.example/neondb/auth"
ORIGIN = "https://ep.example"
# Shape published for this project: path stays on the JWKS URL, not on iss/aud.
PROJECT_BASE = "https://ep-rapid-term-bawmvml8.neonauth.c-8.eu-central-1.aws.neon.tech/neondb/auth"
PROJECT_ORIGIN = "https://ep-rapid-term-bawmvml8.neonauth.c-8.eu-central-1.aws.neon.tech"


def _settings(settings: Settings, base: str = BASE) -> Settings:
    return settings.model_copy(
        update={
            "auth_mode": "neon",
            "neon_auth_base_url": base,
            "neon_auth_jwks_url": f"{base}/.well-known/jwks.json",
        }
    )


def _prepare(monkeypatch: pytest.MonkeyPatch) -> Ed25519PrivateKey:
    private, document = ed25519_jwks()
    install_jwks(monkeypatch, document)
    return private


def test_origin_issuer_and_audience_are_accepted(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = _prepare(monkeypatch)
    token = sign_neon(private, issuer=ORIGIN, audience=ORIGIN, email=TEST_EMAIL)
    principal = verify_authorization(_settings(settings), "Bearer " + token)
    assert principal.subject == TEST_SUBJECT
    assert principal.email == TEST_EMAIL


def test_project_auth_host_accepts_the_origin_only(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = _prepare(monkeypatch)
    token = sign_neon(private, issuer=PROJECT_ORIGIN, audience=PROJECT_ORIGIN, email=TEST_EMAIL)
    principal = verify_authorization(_settings(settings, PROJECT_BASE), "Bearer " + token)
    assert principal.email == TEST_EMAIL


def test_base_url_without_a_path_is_its_own_issuer(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = _prepare(monkeypatch)
    token = sign_neon(private, issuer=ORIGIN, audience=ORIGIN, email=TEST_EMAIL)
    principal = verify_authorization(_settings(settings, ORIGIN), "Bearer " + token)
    assert principal.email == TEST_EMAIL


def test_full_base_url_issuer_is_rejected(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    private = _prepare(monkeypatch)
    token = sign_neon(private, issuer=BASE, audience=ORIGIN, email=TEST_EMAIL)
    caplog.set_level(logging.WARNING, logger="app.core.auth")
    with pytest.raises(AuthError) as caught:
        verify_authorization(_settings(settings), "Bearer " + token)
    assert caught.value.status == 401
    assert caught.value.code == "INVALID_TOKEN"
    assert token not in caplog.text
    assert TEST_EMAIL not in caplog.text
    assert "alg=EdDSA" in caplog.text
    assert f"kid={KID}" in caplog.text
    assert f"iss={BASE}" in caplog.text
    assert "has_email=True" in caplog.text
    assert "InvalidIssuerError" in caplog.text


def test_token_shaped_issuer_is_not_logged(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    private = _prepare(monkeypatch)
    planted = "eyJhbGciOiJFZERTQSJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJl"
    token = sign_neon(private, issuer=planted, audience=ORIGIN, email=None)
    caplog.set_level(logging.WARNING, logger="app.core.auth")
    with pytest.raises(AuthError):
        verify_authorization(_settings(settings), "Bearer " + token)
    assert planted not in caplog.text
    assert token not in caplog.text
    assert "iss=-" in caplog.text
    assert "has_email=False" in caplog.text


def test_diagnostic_failure_still_hides_the_token(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    private = _prepare(monkeypatch)
    token = sign_neon(private, issuer=BASE, audience=ORIGIN, email=TEST_EMAIL)

    def explode(_token: str) -> tuple[str | None, str | None, str | None, bool]:
        raise RuntimeError("diagnostic")

    monkeypatch.setattr("app.core.auth._jwt_diagnostics", explode)
    caplog.set_level(logging.WARNING, logger="app.core.auth")
    with pytest.raises(AuthError) as caught:
        verify_authorization(_settings(settings), "Bearer " + token)
    assert caught.value.status == 401
    assert token not in caplog.text
    assert TEST_EMAIL not in caplog.text
    assert "error=InvalidIssuerError" in caplog.text


def test_wrong_audience_is_rejected(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    private = _prepare(monkeypatch)
    token = sign_neon(private, issuer=ORIGIN, audience=BASE, email=TEST_EMAIL)
    with pytest.raises(AuthError) as caught:
        verify_authorization(_settings(settings), "Bearer " + token)
    assert caught.value.status == 401
    assert caught.value.code == "INVALID_TOKEN"


def test_missing_audience_is_rejected(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    private = _prepare(monkeypatch)
    token = sign_neon(private, issuer=ORIGIN, audience=None, email=TEST_EMAIL)
    with pytest.raises(AuthError) as caught:
        verify_authorization(_settings(settings), "Bearer " + token)
    assert caught.value.status == 401


def test_missing_email_stays_unauthorized(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = _prepare(monkeypatch)
    token = sign_neon(private, issuer=ORIGIN, audience=ORIGIN, email=None)
    with pytest.raises(AuthError) as caught:
        verify_authorization(_settings(settings), "Bearer " + token)
    assert caught.value.status == 401
    assert caught.value.code == "INVALID_TOKEN"
    assert "e-mail" in caught.value.message


def test_email_outside_the_allowlist_is_forbidden(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = _prepare(monkeypatch)
    token = sign_neon(private, issuer=ORIGIN, audience=ORIGIN, email="intrus@example.com")
    with pytest.raises(AuthError) as caught:
        verify_authorization(_settings(settings), "Bearer " + token)
    assert caught.value.status == 403
    assert caught.value.code == "EMAIL_NOT_ALLOWED"


def test_wrong_signature_is_rejected(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare(monkeypatch)
    other, _document = ed25519_jwks("other-key")
    token = sign_neon(other, issuer=ORIGIN, audience=ORIGIN, email=TEST_EMAIL, kid=KID)
    with pytest.raises(AuthError) as caught:
        verify_authorization(_settings(settings), "Bearer " + token)
    assert caught.value.status == 401
    assert caught.value.code == "INVALID_TOKEN"


def test_expired_neon_jwt_is_rejected(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    private = _prepare(monkeypatch)
    token = sign_neon(private, issuer=ORIGIN, audience=ORIGIN, email=TEST_EMAIL, expired=True)
    with pytest.raises(AuthError) as caught:
        verify_authorization(_settings(settings), "Bearer " + token)
    assert caught.value.status == 401
    assert caught.value.code == "INVALID_TOKEN"
