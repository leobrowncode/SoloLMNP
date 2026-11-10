# Agent State

> This file is a compact resume point for autonomous development agents.
> Git, GitHub PRs/issues and the actual repository remain the source of truth.

## Current project status

- Completed through: liasse LMNP IR, entrée du bien, dossier FEC, enchaînement SIRET → exercice → bien → banque (#118), Neon Auth + Postgres + `owner_id` (#123 à #130), déploiement https://sololmnp.vercel.app
- Current phase: P0 du parcours corrigé (dossier local sans secret Neon). Les P1 de `docs/archive/audit/2026-11/PARCOURS.md` restent ouverts.
- Current objective: ne pas coder les P1 tant qu’ils ne sont pas demandés. Les millésimes 2025 et 2026 restent en recherche.

## Completed

- P0 a P12 et liasse 2025, cases lues sur les PDF archivés
- Correctifs UX du 31/10/2026 (#108 à #117) et initialisation en une suite (#118)
- Auth de production : Neon Auth (e-mail et Google), `ALLOWED_EMAILS`, isolation `owner_id`, Vercel Blob, JWT dont l’émetteur est l’origine (#130)
- Audit 05/11/2026 : parcours rejoué en local (mode d’essai) et connexion prod ouverte. Le lanceur README sans secrets Neon s’arrête sur « L’authentification n’est pas configurée. »

## Active work

- Issue: #7 (moteur fiscal, cession, TVA, plus-values) et #11 (feuille EFI et 2042-C-PRO). Seules issues ouvertes.
- Branch: audit documentaire `docs/archive/audit/2026-11/PARCOURS.md`
- Status: pas de réécriture d’auth. Neon Auth + Postgres partagé + `owner_id` est le choix retenu. Pas d’Argon2 local, pas d’une base SQLite par utilisateur.

## Important decisions

- Montants en centimes entiers. Le ledger est la seule source du journal, du bilan et du FEC.
- Les couches fiscales ne modifient pas les écritures.
- `ready` exige : registre de cases respecté, aucun écart d’immobilisations, de classement, d’effectifs, de cession ou de TVA, et un SIREN.
- La liasse n’impute pas les déficits LMNP antérieurs.
- SoloLMNP ne télétransmet pas.
- Auth : Neon Auth en production. `AUTH_MODE=local` ouvre un seul dossier si `APP_ENV=development` et hors Vercel. `AUTH_MODE=test` reste réservé aux essais et refusé en production.

## Known limitations / blockers

- Périmètre LMNP déclaré. Le LMP n’est pas calculé.
- Cession, TVA, plus-values et ventilation automatique du terrain : désactivées, et bloquantes si elles apparaissent
- Millésime 2026 : formulaires 2027 non publiés ; cases non reprises comme officielles
- P0 d’audit corrigé : README et Docker ouvrent le dossier local sans secret Neon. Production et Vercel restent sur Neon Auth.

## Validation baseline

```bash
python scripts/check.py
```

L’audit de novembre est documentaire : pas de changement applicatif, donc pas de nouveau passage de `scripts/check.py` pour cette PR.

## Next action

1. Faire relire `docs/archive/audit/2026-11/PARCOURS.md`.
2. Ensuite seulement : P0 premier écran (explication Neon, pas une nouvelle auth), puis P1 de saisie et de parcours, dans l’ordre du document.
3. #7 et #11 restent hors de ces PR tant qu’une source et un test ne les justifient pas.

## Last updated

- Date: 2026-11-05
