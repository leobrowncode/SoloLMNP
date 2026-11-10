"""Delete the Neon branches `preview/<git branch>` left behind by Vercel previews.

The Vercel-managed Neon integration creates one branch per previewed Git branch and
only deletes it with the last Vercel deployment of that branch. On the Free plan the
project holds 10 branches, so stale previews make every new preview fail with
"Resource provisioning failed", before the build.

Modes:
  --branch REF   delete `preview/REF`, unless REF is still the head of an open PR;
  --stale        delete every `preview/*` whose Git branch is gone, or whose PRs are
                 all closed or merged. A branch without any PR yet is kept.

Environment: NEON_API_KEY, NEON_PROJECT_ID, GITHUB_TOKEN, GITHUB_REPOSITORY.
Standard library only: the job runs without installing anything.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

PREFIX = "preview/"
NEON_API = "https://console.neon.tech/api/v2"
GITHUB_API = "https://api.github.com"
RETRY_STATUSES = {409, 423, 429, 500, 502, 503, 504}


class CleanupError(RuntimeError):
    """The job must fail. The message never contains a key."""


@dataclass(frozen=True)
class NeonBranch:
    id: str
    name: str
    parent_id: str | None
    default: bool
    primary: bool
    protected: bool

    @classmethod
    def from_api(cls, raw: Mapping[str, Any]) -> NeonBranch:
        return cls(
            id=str(raw["id"]),
            name=str(raw["name"]),
            parent_id=raw.get("parent_id"),
            default=bool(raw.get("default")),
            primary=bool(raw.get("primary")),
            protected=bool(raw.get("protected")),
        )

    @property
    def git_ref(self) -> str | None:
        if not self.name.startswith(PREFIX):
            return None
        return self.name[len(PREFIX) :] or None


def deletable(branch: NeonBranch, all_branches: Iterable[NeonBranch]) -> bool:
    if branch.git_ref is None or branch.default or branch.primary or branch.protected:
        return False
    return not any(other.parent_id == branch.id for other in all_branches)


def plan_stale(
    branches: list[NeonBranch],
    git_branches: set[str],
    open_heads: set[str],
    has_closed_pr: Callable[[str], bool],
) -> list[tuple[NeonBranch, str]]:
    """Return the preview branches to delete, each with a reason."""
    plan: list[tuple[NeonBranch, str]] = []
    for branch in branches:
        ref = branch.git_ref
        if ref is None or not deletable(branch, branches) or ref in open_heads:
            continue
        if ref not in git_branches:
            plan.append((branch, "branche git supprimée"))
        elif has_closed_pr(ref):
            plan.append((branch, "PR fermée ou mergée"))
    return plan


Opener = Callable[[urllib.request.Request, float], Any]


def _default_opener(request: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310


class Api:
    def __init__(
        self,
        base: str,
        headers: Mapping[str, str],
        *,
        opener: Opener = _default_opener,
        sleep: Callable[[float], None] = time.sleep,
        attempts: int = 5,
    ) -> None:
        if not base.startswith("https://"):
            raise CleanupError("Les API sont appelées en https seulement.")
        self._base = base
        self._headers = dict(headers)
        self._open = opener
        self._sleep = sleep
        self._attempts = attempts

    def request(self, method: str, path: str, *, missing_ok: bool = False) -> Any:
        url = f"{self._base}{path}"
        for attempt in range(1, self._attempts + 1):
            request = urllib.request.Request(  # noqa: S310
                url, method=method, headers=self._headers
            )
            try:
                with self._open(request, 30.0) as response:
                    body = response.read()
            except urllib.error.HTTPError as exc:
                if exc.code == 404 and missing_ok:
                    return None
                if exc.code in RETRY_STATUSES and attempt < self._attempts:
                    self._sleep(2.0 * attempt)
                    continue
                raise CleanupError(f"{method} {path} : HTTP {exc.code}.") from None
            except urllib.error.URLError as exc:
                if attempt < self._attempts:
                    self._sleep(2.0 * attempt)
                    continue
                raise CleanupError(f"{method} {path} : réseau ({exc.reason}).") from None
            return json.loads(body) if body else None
        raise CleanupError(f"{method} {path} : échec.")


class Neon:
    def __init__(self, api: Api, project_id: str) -> None:
        self._api = api
        self._project = urllib.parse.quote(project_id, safe="")

    def branches(self) -> list[NeonBranch]:
        data = self._api.request("GET", f"/projects/{self._project}/branches?limit=1000")
        return [NeonBranch.from_api(raw) for raw in (data or {}).get("branches", [])]

    def branches_limit(self) -> int | None:
        data = self._api.request("GET", f"/projects/{self._project}") or {}
        limit = (data.get("project") or {}).get("owner", {}).get("branches_limit")
        return limit if isinstance(limit, int) else None

    def delete(self, branch: NeonBranch) -> None:
        branch_id = urllib.parse.quote(branch.id, safe="")
        self._api.request(
            "DELETE", f"/projects/{self._project}/branches/{branch_id}", missing_ok=True
        )


class GitHub:
    def __init__(self, api: Api, repository: str) -> None:
        self._api = api
        self._repo = repository
        self._owner = repository.split("/", 1)[0]

    def _pages(self, path: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        separator = "&" if "?" in path else "?"
        for page in range(1, 51):
            batch = self._api.request("GET", f"{path}{separator}per_page=100&page={page}")
            items.extend(batch or [])
            if not batch or len(batch) < 100:
                return items
        raise CleanupError(f"GET {path} : plus de 5000 éléments.")

    def branches(self) -> set[str]:
        return {item["name"] for item in self._pages(f"/repos/{self._repo}/branches")}

    def open_heads(self) -> set[str]:
        pulls = self._pages(f"/repos/{self._repo}/pulls?state=open")
        return {
            pull["head"]["ref"]
            for pull in pulls
            if (pull["head"].get("repo") or {}).get("full_name") == self._repo
        }

    def has_closed_pr(self, ref: str) -> bool:
        head = urllib.parse.quote(f"{self._owner}:{ref}", safe="")
        pulls = self._api.request(
            "GET", f"/repos/{self._repo}/pulls?state=closed&head={head}&per_page=1"
        )
        return bool(pulls)


def run(
    neon: Neon,
    github: GitHub,
    *,
    ref: str | None,
    dry_run: bool,
    out: Callable[[str], None] = print,
) -> int:
    branches = neon.branches()
    open_heads = github.open_heads()
    if ref is not None:
        target = next((b for b in branches if b.git_ref == ref), None)
        if target is None:
            out(f"Aucune branche Neon {PREFIX}{ref}.")
            plan: list[tuple[NeonBranch, str]] = []
        elif ref in open_heads:
            out(f"{target.name} gardée : une PR ouverte utilise encore {ref}.")
            plan = []
        elif not deletable(target, branches):
            out(f"{target.name} gardée : branche protégée, par défaut ou parente.")
            plan = []
        else:
            plan = [(target, "PR fermée ou branche git supprimée")]
    else:
        plan = plan_stale(branches, github.branches(), open_heads, github.has_closed_pr)

    verb = "À supprimer" if dry_run else "Supprimée"
    for branch, reason in plan:
        if not dry_run:
            neon.delete(branch)
        out(f"{verb} : {branch.name} ({branch.id}), {reason}.")

    remaining = len(branches) - len(plan)
    limit = neon.branches_limit()
    quota = "" if limit is None else f", limite {limit}"
    out(f"Branches Neon : {len(branches)} avant, {remaining} après{quota}.")
    if limit is not None and remaining >= limit - 1:
        out(
            f"::warning::Projet Neon presque plein ({remaining}/{limit}) : "
            "les prochains aperçus Vercel échoueront au provisionnement."
        )
    return 0


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise CleanupError(f"Variable manquante : {name}.")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--branch", help="branche git dont supprimer preview/<branche>")
    mode.add_argument("--stale", action="store_true", help="balayer toutes les preview/*")
    parser.add_argument("--dry-run", action="store_true", help="lister sans supprimer")
    args = parser.parse_args(argv)
    try:
        neon = Neon(
            Api(
                NEON_API,
                {
                    "Authorization": f"Bearer {_env('NEON_API_KEY')}",
                    "Accept": "application/json",
                },
            ),
            _env("NEON_PROJECT_ID"),
        )
        github = GitHub(
            Api(
                GITHUB_API,
                {
                    "Authorization": f"Bearer {_env('GITHUB_TOKEN')}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            ),
            _env("GITHUB_REPOSITORY"),
        )
        ref = (args.branch or "").strip() or None
        if args.branch is not None and ref is None:
            raise CleanupError("--branch est vide.")
        return run(neon, github, ref=ref, dry_run=args.dry_run)
    except CleanupError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
