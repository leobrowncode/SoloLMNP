# Agent State

> This file is a compact resume point for autonomous development agents.
> Git, GitHub PRs/issues and the actual repository remain the source of truth.

## Current project status

Current roadmap position:

- Completed through: liasse BIC 2025 recopiable, 17 octobre 2026
- Current phase: V1 livrée pour le LMNP réel simplifié, millésime 2025
- Current objective: conserver le refus de READY hors de ce périmètre

## Completed

- P0–P12 et liasse 2025 : 2033-A, B, C, D, E et renvoi 2031, cases lues sur les PDF archivés
- Le package et l’EFI passent à `ready` seulement si le registre vérifié est respecté et qu’aucun écart bloquant n’est présent
- Le calcul fiscal stocké, le millésime 2026 et la 2042-C-PRO restent `research_only`

## Active work

- Issue: résidus #7 (cession/TVA/PV), #10/#11 hors 2025, #12 restauration manuelle, #13 authentification
- Branch: branche de travail locale
- Pull request: none
- Status: V1 2025 recopiable ; pas de faux READY sur 2026 ni sur la 2042-C-PRO

## Important decisions

- Montants en centimes entiers. Le ledger est la seule source du journal, du bilan et du FEC.
- Les couches fiscales ne modifient pas les écritures.
- Aucun statut `ready` sur une case absente du registre, un millésime autre que 2025, ou un écart d’immobilisations, de classement, d’effectifs, de cession ou de TVA.
- 2042-C-PRO reste un produit séparé, non numéroté.
- Les comptes 120 et 129 ne sont pas créés automatiquement.
- La restauration écrit `restore-check.sqlite3` et ne remplace pas la base ouverte.
- SoloLMNP ne télétransmet pas.

## Known limitations / blockers

- Périmètre LMNP déclaré. Le LMP n’est pas calculé.
- Cession, TVA, plus-values et ventilation automatique du terrain : désactivées, et bloquantes si elles apparaissent
- 2026 : sources non archivées
- 2042-C-PRO : notice non archivée
- Pas d’authentification ; l’instance doit rester privée
- Remplacement de la base en service après restauration : action manuelle après arrêt

## Validation baseline

```bash
python scripts/check.py
```

- Backend tests: 253 passed le 17 octobre 2026 sur la suite `backend/tests`
- CI: non relancée sur ce lot

## Next action

Next run should:

1. Archiver les formulaires 2026 avant d’étendre `ready`.
2. Laisser la 2042-C-PRO non déclarable tant que sa notice n’est pas archivée.
3. Ne pas calculer de cotisation CVAE : la case 117 est une base, nulle sous 152 500 €.

## Last updated

- Date: 2026-10-17
- Main SHA: à renseigner après commit
- Active PR/commit: V1 liasse 2025
