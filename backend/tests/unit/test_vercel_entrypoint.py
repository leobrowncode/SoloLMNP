import importlib.util
import json
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

ROOT = Path(__file__).resolve().parents[3]


def _entrypoint():
    path = ROOT / "asgi.py"
    spec = importlib.util.spec_from_file_location("sololmnp_vercel_asgi", path)
    if spec is None or spec.loader is None:
        raise AssertionError("asgi.py introuvable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_vercel_entrypoint_serves_health(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    module = _entrypoint()
    source = (ROOT / "asgi.py").read_text(encoding="utf-8")
    assert "app.frontend(" in source
    assert 'fallback="index.html"' in source
    with TestClient(module.app, base_url="http://localhost") as client:
        response = client.get("/api/health")
        modeles = client.get("/api/v1/modeles")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert modeles.status_code != 404


def test_vercel_project_serves_static_frontend_and_a_long_api_function() -> None:
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["framework"] == "fastapi"
    assert "outputDirectory" not in config
    assert config["functions"]["asgi.py"]["maxDuration"] == 300
    included = config["functions"]["asgi.py"]["includeFiles"]
    assert "fiscal/**" in included
    assert "lmnp_core/**" in included
    assert "golden/**" in included
    assert project["tool"]["vercel"]["entrypoint"] == "asgi:app"
    assert project["tool"]["vercel"]["fastapi"]["static"]["cdn"] is True
    nginx = (ROOT / "scripts" / "nginx.conf").read_text(encoding="utf-8")
    assert "connect-src 'self' https://vercel.com" in nginx
    lock = _lock_versions(ROOT / "backend" / "requirements.lock")
    for dependency in project["project"]["dependencies"]:
        name, version = dependency.split("==", 1)
        assert lock[name.split("[", 1)[0].lower()] == version


def _lock_versions(path: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "==" not in line or line.startswith((" ", "#")):
            continue
        name, version = line.split("==", 1)
        versions[name.lower()] = version.strip()
    return versions


def test_vercel_refuses_test_auth_even_outside_production(monkeypatch, settings) -> None:
    monkeypatch.setenv("VERCEL", "1")
    assert settings.app_env == "test"
    assert settings.auth_mode == "test"
    with pytest.raises(RuntimeError, match="AUTH_MODE=test"):
        create_app(settings)


def test_preview_host_is_accepted_and_https_origin_matches(monkeypatch, settings) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_URL", "preview.example.vercel.app")
    configuration = settings.model_copy(update={"auth_mode": "neon", "app_env": "production"})
    application = create_app(configuration)
    headers = {
        "Host": "preview.example.vercel.app",
        "Origin": "https://preview.example.vercel.app",
        "X-Forwarded-Proto": "https",
        "X-SoloLMNP-Request": "1",
    }
    with TestClient(application) as client:
        health = client.get("/api/health", headers={"Host": "preview.example.vercel.app"})
        assert health.status_code == 200
        assert client.post("/api/status", headers=headers).status_code == 401
        rejected = dict(headers)
        rejected["Origin"] = "https://evil.example"
        assert client.post("/api/status", headers=rejected).status_code == 403


def test_forwarded_proto_is_ignored_off_vercel(monkeypatch, settings) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    configuration = settings.model_copy(update={"auth_mode": "neon"})
    with TestClient(create_app(configuration)) as client:
        response = client.post(
            "/api/status",
            headers={
                "Origin": "https://testserver",
                "X-Forwarded-Proto": "https",
                "X-SoloLMNP-Request": "1",
            },
        )
    assert response.status_code == 403
