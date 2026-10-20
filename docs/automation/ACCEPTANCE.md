# Matrice d'acceptation

Contrôle du 20 octobre 2026 sur `main` (`0a59960`), complété par la correction des messages de refus.

Une ligne n'est `VALIDÉ` que si une exécution de ce dépôt, rejouée pour ce contrôle, a vérifié le résultat. Les campagnes citées dans les rapports de phase sont des preuves historiques, pas une validation du jour.

| Exigence | Statut | Preuve | Manque |
|---|---|---|---|
| Installation Docker documentée | À_TESTER | `README.md`, `docs/DEPLOYMENT.md`, `docker-compose.yml` | Démarrage non rejoué le 20 octobre 2026. Le README de `main` demande encore la branche fusionnée `feat/assets-depreciation`. Correction déjà proposée dans la PR #22, non fusionnée. |
| `scripts/start_local.py` et `SoloLMNP.bat` | NON_CONFORME | Absents du dépôt | Le démarrage réel documenté est Docker Compose ou les commandes natives de `docs/DEPLOYMENT.md`. |
| Activité, biens, exercices, migrations 0001–0005 | À_TESTER | `backend/alembic/versions/`, `docs/PHASE1_REPORT.md` | Suite non rejouée. |
| Écritures validées équilibrées, correction par extourne | À_TESTER | `backend/app/services/ledger.py` | Suite non rejouée. |
| Journal, grand livre, balance dérivés du ledger | À_TESTER | `frontend/src/features/LedgerPage.tsx` | Parcours navigateur non rejoué. |
| Recettes, dépenses, banque, emprunts ventilés | À_TESTER | `docs/PHASE3_REPORT.md`, issue #4 fermée | Suite non rejouée. |
| Terrain 211 non amortissable, ventilation manuelle | À_TESTER | `backend/app/services/assets.py`, `backend/app/api/asset_schemas.py` | Suite non rejouée. |
| Dotations comptables dans le ledger | À_TESTER | `docs/PHASE4_REPORT.md` | Issue #5 encore ouverte. |
| Bilan et résultat uniquement depuis les écritures validées | À_TESTER | `backend/app/services/statements.py` | Statut forcé `PROVISIONAL`. Présentation réglementaire absente. |
| L'écran des états ne présente plus l'inventaire comme absent | VALIDÉ | `frontend/src/features/StatementsPage.tsx` et test « shows provisional statements… » | Le calcul chiffré des états reste `À_TESTER`. |
| Inventaire manuel justifié, revue, idempotence | À_TESTER | `backend/app/services/inventory.py`, `frontend/src/features/InventoryForm.tsx` | Pas de schémas CCA/PCA/FNP/PAR. Pièces non archivées. |
| À-nouveaux idempotents et continuité | BLOQUÉ | `backend/app/services/opening_posting.py` exige `SOURCE_NOT_CLOSED` | Aucun parcours de clôture. Q-001 en attente. |
| Clôture, réouverture auditée, immutabilité | NON_CONFORME | `docs/CLOSING_PROCESS.md` décrit le flux ; aucun service ni écran | Issue #8 ouverte. Q-001 et Q-002 en attente. |
| Moteur fiscal versionné et reports | NON_CONFORME | `fiscal/2025/rules.yaml`, `fiscal/2026/rules.yaml` | Statut `research_only` conservé. Issue #7 ouverte. |
| FEC reproductible | NON_CONFORME | `docs/FEC.md` seulement | Issue #9 ouverte. |
| Liasse 2031/2033 et feuille EFI | NON_CONFORME | `docs/TAX_FORMS.md`, `docs/FILING.md` | Issues #10 et #11 ouvertes. |
| Sauvegarde et restauration vers une copie de contrôle | NON_CONFORME | `docs/BACKUP.md` | Issue #12 ouverte. |
| Parcours A–J de bout en bout | NON_CONFORME | `backend/tests/golden/test_phase0_scenarios.py` est un catalogue | Issue #13 ouverte. |
| Télétransmission, LMP, cession, TVA, plus-values, ventilation automatique du terrain | HORS_PÉRIMÈTRE | Périmètre du dépôt et de la mission | Ne pas implémenter. |
| Millésime 2026 et 2042-C-PRO au statut `ready` | HORS_PÉRIMÈTRE | `backend/app/main.py` force `research_only` | Ne pas promouvoir. |
| Un refus de validation affiche la phrase métier, pas seulement un message générique | VALIDÉ | `frontend/src/api/ledger.ts`. Pydantic 2.13.5 produit `Value error, ` suivi de la phrase française. Tests `ledger.test.ts` et « shows the property split refusal » : 54 tests frontend réussis le 20 octobre 2026. | Le contrôle serveur reste inchangé. Les messages Pydantic anglais hors `Value error` restent affichés tels quels. Parcours navigateur non rejoué. |
| Écriture depuis le serveur de développement natif | NON_CONFORME | `frontend/vite.config.ts` sur `main` remplace l'en-tête Host | Correction déjà dans la PR #22, non rejouée ici. |
| L'accueil décrit le périmètre réellement livré | NON_CONFORME | `frontend/src/App.tsx` affiche encore « Phase 4 · Immobilisations » et dit que l'inventaire reste à développer | Correction déjà dans la PR #22. |
