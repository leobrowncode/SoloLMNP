# Agent State

> Git, GitHub issues and the repository remain the source of truth.
> Product decisions live in `docs/automation/DECISIONS.md`.
> Acceptance evidence lives in `docs/automation/ACCEPTANCE.md`.

## Current project status

- Completed through: P0–P4 present on `main`; only issue #4 (P3) is closed.
- Current phase: P5, partial.
- Current objective: keep the land split understandable, and wait for Q-001 before any closing flow.

## Completed

- P0–P4: foundation, ledger, operations, bank, loans, assets and depreciation.
- P5 partial: provisional statements, opening preview and idempotent generation, manual inventory API and form, receipt cleanup (#21).
- Issues #7–#13 (P6–P12) have no implementation.

## Active work

- Issue: #6 — inventaire, bilan, résultat et continuité
- Branch: `cursor/sololmnp-conformit-livraison-5df6`
- Pull request: to be opened for the land-split explanations
- Earlier pull requests: #22 (displayed scope and Vite Host), #23 (validation sentences) and #24 (exercise and dedicated-account conflicts) remain open and must not be redone.

## Important decisions

- Validated entries are balanced; corrections are reversals only.
- Closed years are immutable, but no public closing flow exists yet.
- Money is `Decimal` in Python, integer cents in SQLite, strings in the API and `BigInt` in the browser.
- Account 211 is not depreciable. Land and building are split manually. A depreciable asset cannot carry a non-depreciable portion.
- Property land plus building must equal the acquisition price. Acquisition costs stay informational and do not change that total.
- Accounts 120 and 129 are never created automatically.
- Fiscal vintages stay `research_only` until their own validation conditions exist.
- No electronic filing.

## Known limitations / blockers

- Opening generation cannot be used on a real file: it requires a CLOSED source year, and P7 is not built.
- The next exercise must start the day after the previous one ends. On `main`, overlap and a reused 164 or 512 account still return a generic integrity message. PR #24 explains them.
- Statements are account-level and `PROVISIONAL`, not a regulatory annual package.
- Result centralization and allocation are not specified as an approved closing behavior.
- `scripts/start_local.py` and `SoloLMNP.bat` are not in the repository. Startup is Docker Compose or the native commands in `docs/DEPLOYMENT.md`.
- Questions Q-001, Q-002 and Q-003 are waiting for the product owner. Do not treat the agent recommendation as approval.

## Validation baseline

```bash
python scripts/check.py
```

On 2026-10-22: 224 backend tests, coverage 95 %, Ruff, mypy and pip check passed. Frontend lint, TypeScript, 53 tests and the Vite build passed on Node 22.23.3. The repository asks for Node 24. Docker and a browser pass were not run.

## Next action

Next run should:

1. Read `docs/automation/DECISIONS.md` before choosing work.
2. Leave PR #22, PR #23 and PR #24 untouched. Do not repeat their scope, Vite Host proxy, Pydantic message, or integrity-conflict work.
3. If Q-001 is still unanswered, do not implement closing, result allocation, or a fiscal engine.
4. Continue independent P5 hardening only when a confirmed defect remains.

## Last updated

- Date: 2026-10-22
- Main SHA: `0a59960`
- Active PR/commit: land-split explanations on `cursor/sololmnp-conformit-livraison-5df6`
