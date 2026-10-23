# Agent State

> This file is a compact resume point for autonomous development agents.
> Git, GitHub PRs/issues and the actual repository remain the source of truth.

## Current project status

Current roadmap position:

- Completed through: P4 on `main` (`0a59960`). P5 partial: provisional statements, manual inventory, opening preview and generation.
- Current phase: P5. Minimal close is available. Regulatory close, FEC and fiscal forms are not.
- Current objective: keep the approved close behavior and do not invent the remaining tax scope.

## Completed

- Ledger, operations, bank CSV, loans, assets, depreciation, provisional statements, manual inventory and idempotent openings are on `main`.
- Open automation PRs, not merged and not to be redone: #22 scope and Vite Host, #23 Pydantic sentences, #24 exercise and dedicated-account messages, #25 land and acquisition-cost explanation.
- Bank reconciliation on this branch only offers same-date validated lines and names the refused condition.
- Minimal audited close and motivated reopen are on this branch. Result allocation stays on the explicit 120 or 129 account at opening generation.

## Active work

- Issue: #6 — inventaire, bilan, résultat et continuité
- Branch: `cursor/sololmnp-conformit-livraison-8484`
- Pull request: #26 — https://github.com/leobrowncode/SoloLMNP/pull/26
- Status: implementation, awaiting review

## Important decisions

- Validated entries are corrected only by reversal. Closed years stay immutable. Money is `Decimal` / integer cents / API strings / browser `BigInt`.
- Account 211 is never depreciated. Land and building are split manually. Do not create accounts 120 and 129 automatically.
- Fiscal vintages stay `research_only`. Do not invent tax-form boxes and do not implement electronic filing.
- Q-001 A and Q-002 A were approved on 2026-10-23. Minimal close is `OPEN` to `CLOSED`, with a motivated reopen. Do not centralize classes 6/7 and do not allocate the result. Opening entries still use an explicit account 120 or 129. Do not create those accounts automatically.
- Q-003 in `docs/automation/DECISIONS.md` stays `EN_ATTENTE_UTILISATEUR`. Do not add guided inventory templates.

## Known limitations / blockers

- Minimal close and motivated reopen exist. The regulatory pre-close checklist, FEC, fiscal engine, and backups do not.
- Q-003 is still unanswered. Do not add guided inventory templates.
- P6–P12 are not implemented. `scripts/start_local.py` and `SoloLMNP.bat` do not exist.
- This environment has Python 3.12 and Node 22, not Node 24.
- Do not modify `data/` or a real accounting database.

## Validation baseline

Relevant commands:

```bash
python scripts/check.py
```

Current known baseline on 2026-10-23:

- Backend tests: 226 passed, coverage 94 %
- Frontend tests: 54 passed
- CI: not re-run remotely. Docker and browser flows were not executed.

## Next action

Next run should:

1. Fetch latest GitHub state and read `docs/automation/`.
2. Check whether PRs #22, #23, #24, #25 and this branch's PR are still open.
3. Do not redo the minimal close. Q-001 A and Q-002 A are approved. Q-003 is still open.
4. Do not redo the open pull requests. The regulatory close checklist, FEC and backups remain unbuilt.

## Last updated

- Date: 2026-10-23
- Main SHA: `0a59960`
- Active PR/commit: PR #26, commit `777c890`
