# Agent State

> Git, GitHub issues and the repository remain the source of truth.
> Product decisions live in `docs/automation/DECISIONS.md`.
> Acceptance evidence lives in `docs/automation/ACCEPTANCE.md`.

## Current project status

- Completed through: P0–P4 present on `main`; only issue #4 (P3) is closed.
- Current phase: P5, partial.
- Current objective: finish continuity by deciding how a year becomes CLOSED, then keep provisional statements honest.

## Completed

- P0–P4: foundation, ledger, operations, bank, loans, assets and depreciation.
- P5 partial: provisional statements, opening preview and idempotent generation, manual inventory API and form, receipt cleanup (#21).
- Issues #7–#13 (P6–P12) have no implementation.

## Active work

- Issue: #6 — inventaire, bilan, résultat et continuité
- Branch: `cursor/sololmnp-conformit-livraison-1423`
- Pull request: #22
- Status: review

## Important decisions

- Validated entries are balanced; corrections are reversals only.
- Closed years are immutable, but no public closing flow exists yet.
- Money is `Decimal` in Python, integer cents in SQLite, strings in the API and `BigInt` in the browser.
- Account 211 is not depreciable. Land and building are split manually.
- Accounts 120 and 129 are never created automatically.
- Fiscal vintages stay `research_only` until their own validation conditions exist.
- No electronic filing.

## Known limitations / blockers

- Opening generation cannot be used on a real file: it requires a CLOSED source year, and P7 is not built.
- Statements are account-level and `PROVISIONAL`, not a regulatory annual package.
- Result centralization and allocation are not specified as an approved closing behavior.
- `scripts/start_local.py` and `SoloLMNP.bat` are not in the repository. Startup is Docker Compose or the native commands in `docs/DEPLOYMENT.md`.
- The Vite dev proxy must keep the browser Host header. Changing it back to the API port rejects every write.
- Questions Q-001, Q-002 and Q-003 are waiting for the product owner. Do not treat the agent recommendation as approval.

## Validation baseline

```bash
python scripts/check.py
```

Historical baseline recorded in `docs/PHASE5_REPORT.md` on 2026-09-29: 222 backend tests, 51 frontend tests. Not re-executed on 2026-10-19 before the documentation and copy correction. Re-run the frontend checks on this branch after that correction.

## Next action

Next run should:

1. Read `docs/automation/DECISIONS.md` before choosing work.
2. If Q-001 is still unanswered, do not implement closing or a fiscal engine.
3. Continue independent P5 hardening only when a confirmed defect remains.
4. Do not reopen P2/P3/P4 feature work already on `main`.

## Last updated

- Date: 2026-10-19
- Main SHA: `0a59960`
- Active PR/commit: branch `cursor/sololmnp-conformit-livraison-1423`
