# Agent State

> This file is a compact resume point for autonomous development agents.
> Git, GitHub PRs/issues and the actual repository remain the source of truth.

## Current project status

- Completed through: liasse LMNP IR conforme à la notice 2033, entrée du bien au premier exercice, dossier de contrôle FEC
- Current phase: exercice 2026 (premier exercice réel : achat 09/01/2026, location et exercice depuis le 06/04/2026)
- Current objective: saisie des données réelles 2026 par l’utilisateur, clôture début 2027, recopie EFI

## Completed

- P0–P12 et liasse 2025 : 2033-A, B, C, E, 2031 et 2031-bis, cases lues sur les PDF archivés
- 23/10/2026 : 370/372 = 352/354 (ligne 360 réservée à l’IS), ligne 350 = reprise d’amortissements 39 C antérieurs, 2033-D cadre II retiré, consignes de saisie (case 018…), état de suivi 39 C
- 2042-C-PRO revenus 2025 : 5NA / 5NY et 5GA (2015) à 5GJ (2024), lus sur le CERFA 11222*28 archivé. 5NK et 5NZ bloquées. Exercice 2026 : cases non publiées (`case_not_verified`)
- `POST /api/assets/properties/{id}/entry` : entrée du bien (immobilisations, emprunts, banque, frais d’avant début, 108), aperçu puis confirmation, extournable
- FEC nommé `SirenFECAAAAMMJJ.txt`, bloqué sans SIREN ; `GET /api/filing/years/{id}/archive` : zip FEC + description A47 A-1 + liasse + SHA256SUMS
- Contrôle immobilisations et 2033-E lus hors centralisation (bug qui bloquait toute clôture avec immobilisations)
- `test_first_exercise.py` : parcours complet achat → clôture → liasse `ready` → FEC → dossier

## Active work

- Issue: résidus #7 (cession/TVA/PV), #12 restauration manuelle, #13 authentification
- Branch: main (local)
- Status: produit utilisable pour la déclaration 2027 (exercice 2026), sous réserve de vérifier les cases sur le formulaire 2027

## Important decisions

- Montants en centimes entiers. Le ledger est la seule source du journal, du bilan et du FEC.
- Les couches fiscales ne modifient pas les écritures.
- `ready` exige : registre de cases respecté, aucun écart d’immobilisations, de classement, d’effectifs, de cession ou de TVA, et un SIREN.
- La liasse n’impute pas les déficits LMNP antérieurs ; le calcul interne garde une estimation FIFO au niveau du foyer.
- Les comptes 120 et 129 ne sont pas créés automatiquement.
- SoloLMNP ne télétransmet pas.

## Known limitations / blockers

- Périmètre LMNP déclaré. Le LMP n’est pas calculé.
- Cession, TVA, plus-values et ventilation automatique du terrain : désactivées, et bloquantes si elles apparaissent
- Millésime 2026 : formulaires 2027 non publiés au 30/10/2026 ; numéros de cases bloqués, non repris comme officiels
- SQLite refuse les écritures datées dans le futur : dotations au 31/12 validables à partir de cette date
- Pas d’authentification ; l’instance doit rester privée

## Validation baseline

```bash
python scripts/check.py
```

- 23/10/2026 : backend 255 tests, frontend 65 tests, ruff, mypy, ESLint, tsc et build verts

## Next action

1. Archiver les PDF 2031/2033 et 2042-C-PRO du millésime 2027 dès publication, puis créer `fiscal/2026/forms/cases.yaml`.
2. Comparer les numéros de cases avec le registre 2025 et ne publier que ceux lus sur le PDF.

## Last updated

- Date: 2026-10-30
