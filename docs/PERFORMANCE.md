# Performance sur un volume fictif

Mesures du 30 octobre 2026, machine de développement, Python 3.12, SQLite, `scripts/bench_volume.py`. Rien n’est écrit dans `data/`. Ce script n’est pas dans la CI.

Jeu de données : trois exercices (2024, 2025, 2026), 800 écritures validées par exercice (2 400 au total), 40 mobiliers. Les dates de 2026 s’arrêtent en juin, donc avant la date de la mesure. Le calcul fiscal 2025 répond `research_only`, `declarable=false`, `output_status=recherche`.

## Lectures API (second appel)

| Lecture | Durée | Requêtes SQL |
| --- | ---: | ---: |
| Journal, 50 écritures validées de 2025 | 7,4 ms | 5 |
| Balance 2025 | 45,6 ms | 5 |
| États 2025 | 23,7 ms | 4 |
| Grand livre du compte 706000 | 22,5 ms | 5 |
| Liste des immobilisations (40) | 5,5 ms | 6 |
| Second calcul fiscal 2025 | 120,5 ms | — |

Le premier calcul fiscal est plus long : il construit le résultat. Le second relit un calcul déjà stocké. La création des 2 400 écritures a pris 8,6 s.

`EXPLAIN QUERY PLAN` du journal et de la balance utilise l’index couvrant `ix_accounting_entry_year_status_date` (`fiscal_year_id`, `status`, `accounting_date`, `sequence`), migration `0011_entry_year_status`. La balance ne construit plus le grand livre complet pour le jeter ensuite. Le grand livre d’un compte filtre ce compte en SQL.

La liste des immobilisations chargeait auparavant composants, plans, compteurs et verrous pièce par pièce (242 requêtes pour 40 fiches). Elle précharge maintenant ces lectures (6 requêtes).

## Pages

Même base, Vite en développement, Chromium headless. Temps jusqu’au titre de niveau 1 :

| Page | Durée |
| --- | ---: |
| Vue d’ensemble | 395 ms |
| Journal | 218 ms |
| Balance | 206 ms |
| Biens | 211 ms |
| Immobilisations | 184 ms |
| États | 197 ms |
| Fiscalité | 187 ms |

Ce sont des temps de serveur de développement, pas un build de production. Le journal affiché reste paginé.
