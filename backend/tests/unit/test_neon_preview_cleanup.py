import importlib.util
import io
import json
import re
import sys
import urllib.error
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _script() -> ModuleType:
    name = "sololmnp_neon_preview_cleanup"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / "neon_preview_cleanup.py"
    )
    if spec is None or spec.loader is None:
        raise AssertionError("neon_preview_cleanup.py introuvable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cleanup = _script()


def _branch(id_: str, name: str, **extra: Any) -> Any:
    return cleanup.NeonBranch.from_api({"id": id_, "name": name, **extra})


BRANCHES = [
    _branch("br-main", "main", default=True, primary=True),
    _branch("br-gone", "preview/cursor/merged-1", parent_id="br-main"),
    _branch("br-open", "preview/cursor/open-2", parent_id="br-main"),
    _branch("br-closed", "preview/cursor/closed-3", parent_id="br-main"),
    _branch("br-new", "preview/cursor/no-pr-4", parent_id="br-main"),
    _branch("br-prot", "preview/cursor/protected-5", parent_id="br-main", protected=True),
    _branch("br-parent", "preview/cursor/parent-6", parent_id="br-main"),
    _branch("br-child", "dev/child", parent_id="br-parent"),
    _branch("br-dev", "dev/leo", parent_id="br-main"),
]
GIT = {"main", "cursor/open-2", "cursor/closed-3", "cursor/no-pr-4"}
OPEN = {"cursor/open-2"}


def test_stale_plan_deletes_only_previews_without_open_pr() -> None:
    plan = cleanup.plan_stale(BRANCHES, GIT, OPEN, lambda ref: ref == "cursor/closed-3")
    assert [(b.id, reason) for b, reason in plan] == [
        ("br-gone", "branche git supprimée"),
        ("br-closed", "PR fermée ou mergée"),
    ]


class FakeNeon:
    def __init__(self, branches: list[Any], limit: int | None = 10) -> None:
        self._branches = branches
        self._limit = limit
        self.deleted: list[str] = []

    def branches(self) -> list[Any]:
        return list(self._branches)

    def branches_limit(self) -> int | None:
        return self._limit

    def delete(self, branch: Any) -> None:
        self.deleted.append(branch.id)


class FakeGitHub:
    def branches(self) -> set[str]:
        return set(GIT)

    def open_heads(self) -> set[str]:
        return set(OPEN)

    def has_closed_pr(self, ref: str) -> bool:
        return ref == "cursor/closed-3"


def _run(neon: FakeNeon, **kwargs: Any) -> list[str]:
    lines: list[str] = []
    assert cleanup.run(neon, FakeGitHub(), out=lines.append, **kwargs) == 0
    return lines


def test_branch_mode_deletes_the_closed_pr_preview() -> None:
    neon = FakeNeon(BRANCHES)
    lines = _run(neon, ref="cursor/closed-3", dry_run=False)
    assert neon.deleted == ["br-closed"]
    assert lines[-1] == "Branches Neon : 9 avant, 8 après, limite 10."


def test_branch_mode_keeps_a_branch_still_used_by_an_open_pr() -> None:
    neon = FakeNeon(BRANCHES)
    lines = _run(neon, ref="cursor/open-2", dry_run=False)
    assert neon.deleted == []
    assert "gardée" in lines[0]


def test_branch_mode_never_deletes_production_or_parents() -> None:
    neon = FakeNeon(BRANCHES)
    _run(neon, ref="cursor/parent-6", dry_run=False)
    _run(neon, ref="cursor/protected-5", dry_run=False)
    _run(neon, ref="cursor/unknown", dry_run=False)
    assert neon.deleted == []


def test_dry_run_lists_without_deleting() -> None:
    neon = FakeNeon(BRANCHES)
    lines = _run(neon, ref=None, dry_run=True)
    assert neon.deleted == []
    assert lines[0].startswith("À supprimer : preview/cursor/merged-1")
    assert lines[-1] == "Branches Neon : 9 avant, 7 après, limite 10."


def test_stale_mode_frees_the_slots_and_warns_when_still_nearly_full() -> None:
    neon = FakeNeon(BRANCHES)
    lines = _run(neon, ref=None, dry_run=False)
    assert neon.deleted == ["br-gone", "br-closed"]
    assert lines[-1] == "Branches Neon : 9 avant, 7 après, limite 10."
    full = FakeNeon(BRANCHES, limit=8)
    assert _run(full, ref=None, dry_run=False)[-1].startswith(
        "::warning::Projet Neon presque plein (7/8)"
    )


class _Response(io.BytesIO):
    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x", code, "err", {}, None)  # type: ignore[arg-type]


def test_api_retries_a_locked_project_then_succeeds() -> None:
    answers: list[Any] = [_http_error(423), _Response(b'{"ok": true}')]
    seen: list[str] = []

    def opener(request: Any, timeout: float) -> Any:
        seen.append(request.get_header("Authorization"))
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    api = cleanup.Api(
        "https://neon", {"Authorization": "Bearer k"}, opener=opener, sleep=lambda _: None
    )
    assert api.request("DELETE", "/projects/p/branches/b") == {"ok": True}
    assert seen == ["Bearer k", "Bearer k"]


def test_api_treats_a_missing_branch_as_done_and_hides_the_key() -> None:
    def gone(request: Any, timeout: float) -> Any:
        raise _http_error(404)

    def denied(request: Any, timeout: float) -> Any:
        raise _http_error(401)

    api = cleanup.Api("https://neon", {"Authorization": "Bearer secret-key"}, opener=gone)
    assert api.request("DELETE", "/b", missing_ok=True) is None
    api = cleanup.Api("https://neon", {"Authorization": "Bearer secret-key"}, opener=denied)
    with pytest.raises(cleanup.CleanupError) as error:
        api.request("GET", "/b")
    assert "HTTP 401" in str(error.value)
    assert "secret-key" not in str(error.value)
    with pytest.raises(cleanup.CleanupError):
        cleanup.Api("http://neon", {})


def test_missing_secret_fails_the_job(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEON_API_KEY", raising=False)
    assert cleanup.main(["--stale"]) == 1


def test_github_keeps_only_same_repository_heads() -> None:
    pulls = [
        {"head": {"ref": "cursor/a", "repo": {"full_name": "leo/SoloLMNP"}}},
        {"head": {"ref": "cursor/b", "repo": {"full_name": "fork/SoloLMNP"}}},
        {"head": {"ref": "cursor/c", "repo": None}},
    ]

    def opener(request: Any, timeout: float) -> Any:
        return _Response(json.dumps(pulls).encode())

    github = cleanup.GitHub(cleanup.Api("https://gh", {}, opener=opener), "leo/SoloLMNP")
    assert github.open_heads() == {"cursor/a"}


def test_workflow_runs_on_close_delete_and_schedule_with_pinned_actions() -> None:
    text = (ROOT / ".github" / "workflows" / "neon-preview-cleanup.yml").read_text(encoding="utf-8")
    for needle in ("types: [closed]", "delete:", "schedule:", "secrets.NEON_API_KEY"):
        assert needle in text
    uses = re.findall(r"uses: (\S+)", text)
    assert uses
    assert all(re.search(r"@[0-9a-f]{40}$", ref) for ref in uses)
    assert "scripts/neon_preview_cleanup.py" in text
