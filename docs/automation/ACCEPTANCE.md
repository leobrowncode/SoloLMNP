# Matrice d'acceptation

Contrôle initial du 19 octobre 2026 sur `main` (`0a59960`).

Une ligne n'est `VALIDÉ` que si une exécution de ce dépôt, rejouée pour ce contrôle, a vérifié le résultat. Les campagnes citées dans les rapports de phase sont des preuves historiques, pas une validation du jour. Aucune exigence n'est `VALIDÉ` à l'issue de ce premier contrôle.

| Exigence | Statut | Preuve | Manque |
|---|---|---|---|
| Installation Docker documentée et cohérente avec `main` | À_TESTER | `README.md`, `docs/DEPLOYMENT.md`, `docker-compose.yml` | Démarrage non rejoué. Le README n'envoie plus vers `feat/assets-depreciation`. |
| `scripts/start_local.py` et `SoloLMNP.bat` | NON_CONFORME | Absents du dépôt au 19 octobre 2026 | Le démarrage réel est Docker ou les commandes natives de `docs/DEPLOYMENT.md`. |
| Activité, biens, exercices, migrations 0001–0005 | À_TESTER | `backend/alembic/versions/`, `docs/PHASE1_REPORT.md` | Suite non rejouée. |
| Écritures validées équilibrées, correction par extourne | À_TESTER | `backend/app/services/ledger.py`, `backend/tests/integration/test_ledger.py` | Suite non rejouée. |
| Journal, grand livre, balance dérivés du ledger | À_TESTER | `frontend/src/features/LedgerPage.tsx`, tests ledger | Parcours navigateur non rejoué. |
| Recettes, dépenses, banque, emprunts ventilés | À_TESTER | `docs/PHASE3_REPORT.md`, `backend/tests/integration/test_operations.py` | Issue #4 fermée par la PR #16. Suite non rejouée. |
| Terrain 211 non amortissable, ventilation manuelle | À_TESTER | `backend/app/services/assets.py`, `backend/app/api/asset_schemas.py` | Suite non rejouée. |
| Dotations comptables dans le ledger | À_TESTER | `docs/PHASE4_REPORT.md`, `backend/tests/integration/test_assets.py` | Issue #5 encore ouverte. |
| Bilan et résultat uniquement depuis les écritures validées, déséquilibre bloqué | À_TESTER | `backend/app/services/statements.py`, `backend/tests/integration/test_statements.py` | Statut forcé `PROVISIONAL`. Présentation réglementaire absente. |
| Inventaire manuel justifié, revue, idempotence | À_TESTER | `backend/app/services/inventory.py`, `frontend/src/features/InventoryForm.tsx`, PR #19 et #21 | Pas de schémas CCA/PCA/FNP/PAR. Pièces non archivées. |
| À-nouveaux idempotents et continuité | BLOQUÉ | `backend/app/services/opening_posting.py`, `frontend/src/features/OpeningPosting.tsx` | L'API exige une source `CLOSED`. Aucun parcours de clôture. Les tests ferment l'exercice par fixture. |
| Clôture, réouverture auditée, immutabilité | NON_CONFORME | `docs/CLOSING_PROCESS.md` décrit le flux ; aucun service ni écran | Issue #8 ouverte. |
| Moteur fiscal versionné et reports | NON_CONFORME | `fiscal/2025/rules.yaml`, `fiscal/2026/rules.yaml`, paquets `domain/fiscal` vides | Statut `research_only` conservé. Issue #7 ouverte. |
| FEC reproductible | NON_CONFORME | `docs/FEC.md` seulement | Issue #9 ouverte. |
| Liasse 2031/2033 et feuille EFI | NON_CONFORME | `docs/TAX_FORMS.md`, `docs/FILING.md` | Issues #10 et #11 ouvertes. Aucun numéro de case inventé. |
| Sauvegarde et restauration vers une copie de contrôle | NON_CONFORME | `docs/BACKUP.md` | Issue #12 ouverte. `data/` non modifié. |
| Parcours A–J de bout en bout | NON_CONFORME | `backend/tests/golden/test_phase0_scenarios.py` est un catalogue | Issue #13 ouverte. Les golden tests ne valident aucun montant fiscal. |
| Télétransmission, LMP, cession, TVA, plus-values, ventilation automatique du terrain | HORS_PÉRIMÈTRE | Périmètre du dépôt et de la mission | Ne pas implémenter. |
| Millésime 2026 et 2042-C-PRO au statut `ready` | HORS_PÉRIMÈTRE | `backend/app/main.py` force `research_only` | Ne pas promouvoir sans preuves propres. |
| L'accueil décrit le périmètre réellement livré | À_TESTER | `frontend/src/App.tsx`, `frontend/src/App.test.tsx` | Le texte qui niait l'inventaire et la continuité a été corrigé le 19 octobre 2026. Test ajouté, exécution à enregistrer dans `RUN_LOG.md`. |
| Aucun float monétaire | À_TESTER | `backend/app/core/money.py`, `frontend/src/api/ledger.ts` | Recherche `float(` sans occurrence dans le code applicatif le 19 octobre 2026. Suite monétaire non rejouée. |
