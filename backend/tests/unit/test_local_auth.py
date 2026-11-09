"""Local dossier mode stays impossible in production and on Vercel."""

import pytest
from pydantic import ValidationError

from app.core.auth import (
    LOCAL_EMAIL,
    LOCAL_SUBJECT,
    TEST_SECRET,
    AuthError,
    issue_test_token,
    verify_authorization,
)
from app.core.config import Settings
from app.main import create_app


def test_settings_accept_local_mode_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    settings = Settings(_env_file=None, app_env="development", auth_mode="local")
    assert settings.auth_mode == "local"
    principal = verify_authorization(settings, None)
    assert principal.subject == LOCAL_SUBJECT
    assert principal.email == LOCAL_EMAIL
    assert verify_authorization(settings, "Bearer n-importe-quoi") == principal


@pytest.mark.parametrize("app_env", ["production", "test"])
def test_settings_refuse_local_mode_outside_development(
    monkeypatch: pytest.MonkeyPatch, app_env: str
) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    with pytest.raises(ValidationError, match="AUTH_MODE=local"):
        Settings(_env_file=None, app_env=app_env, auth_mode="local")


def test_settings_refuse_local_mode_on_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(ValidationError, match="AUTH_MODE=local"):
        Settings(_env_file=None, app_env="development", auth_mode="local")


def _forced(settings: Settings, **updates: object) -> Settings:
    data = settings.model_dump()
    data.update(updates)
    return Settings.model_construct(**data)


def test_forced_local_mode_is_refused_in_production(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    forced = _forced(settings, app_env="production", auth_mode="local")
    with pytest.raises(RuntimeError, match="AUTH_MODE=local"):
        create_app(forced)
    with pytest.raises(AuthError) as caught:
        verify_authorization(forced, None)
    assert caught.value.status == 401
    assert caught.value.code == "UNAUTHENTICATED"


def test_forced_local_mode_is_refused_on_vercel(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VERCEL", "1")
    forced = _forced(settings, app_env="development", auth_mode="local")
    with pytest.raises(RuntimeError, match="AUTH_MODE=local"):
        create_app(forced)
    with pytest.raises(AuthError) as caught:
        verify_authorization(forced, "Bearer " + issue_test_token(TEST_SECRET))
    assert caught.value.code == "UNAUTHENTICATED"
    assert caught.value.status == 401


def test_production_neon_rejects_the_test_token(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    production = settings.model_copy(
        update={
            "app_env": "production",
            "auth_mode": "neon",
            "neon_auth_base_url": "",
            "neon_auth_jwks_url": "",
        }
    )
    with pytest.raises(AuthError) as missing:
        verify_authorization(production, None)
    assert missing.value.code == "UNAUTHENTICATED"
    with pytest.raises(AuthError) as forged:
        verify_authorization(production, "Bearer " + issue_test_token(TEST_SECRET))
    assert forged.value.code == "AUTH_NOT_CONFIGURED"
    with pytest.raises(AuthError) as local_header:
        verify_authorization(production, "Bearer local")
    assert local_header.value.code == "AUTH_NOT_CONFIGURED"
