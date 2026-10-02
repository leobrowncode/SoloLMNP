# Agent State

> This file is a compact resume point for autonomous development agents.
> Git, GitHub PRs/issues and the actual repository remain the source of truth.

## Current project status

Current roadmap position:

- Completed through: P12, implementation locale du 2 octobre 2026
- Current phase: P12 livrée dans le code ; issues GitHub #6 à #13 encore ouvertes
- Current objective: ne pas déclarer de statut fiscal prêt

## Completed

- P0–P4 : fondations, ledger, opérations, immobilisations
- P5 : états provisoires, inventaire, à-nouveaux, rubriques, centralisation et affectation
- P6–P12 : fiscalité `research_only`, clôture, FEC, mappings de travail, EFI, justificatifs, sauvegarde, scénarios A–J

## Active work

- Issue: #6 à #13 restent ouvertes
- Branch: branche de travail locale, non poussée
- Pull request: none
- Status: implémentation locale, CI distante non relancée

## Important decisions

- Montants en centimes entiers. Le ledger est la seule source du journal, du bilan et du FEC.
- Les couches fiscales ne modifient pas les écritures. Centralisation et affectation sont ignorées par le calcul fiscal.
- Aucun statut `READY`. Les règles bloquantes et les cases CERFA non sourcées restent désactivées.
- Les comptes 120 et 129 ne sont pas créés automatiquement.
- Le FEC exclut les écritures de centralisation, conformément à l’article A47 A-1 relu le 2 octobre 2026.
- La restauration écrit `restore-check.sqlite3` et ne remplace pas la base ouverte.

## Known limitations / blockers

- Qualification LMNP/LMP du foyer, cession, TVA, plus-values et ventilation automatique du terrain : désactivées
- Notices et cases officielles 2031/2033/2042-C-PRO non archivées
- Pas d’authentification ; l’instance doit rester privée
- Remplacement de la base en service après restauration : action manuelle après arrêt

## Validation baseline

Relevant commands:

```bash
python scripts/check.py
```

Current known baseline:

- Backend tests: 236 passed, couverture 92 %
- Frontend tests: 55 passed
- CI: inconnue pour ce lot, aucun push

## Next action

Next run should:

1. Lire les issues #6 à #13 avant d’en fermer une.
2. Ne pas passer `/api/status` à un état fiscal prêt.
3. Archiver les notices officielles du millésime avant d’activer une case CERFA.

## Last updated

- Date: 2026-10-02
- Main SHA: non poussé
- Active PR/commit: lot local P5–P12
