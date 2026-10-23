# Matrice d'acceptation

Contrôle du 23 octobre 2026 sur `main` (`0a59960`), complété par le filtre de rapprochement bancaire de cette branche.

Une ligne n'est `VALIDÉ` que si une exécution de ce dépôt, rejouée pour ce contrôle, a vérifié le résultat. Les campagnes citées dans les rapports de phase sont des preuves historiques, pas une validation du jour. Les corrections des PR #22 à #25 ne sont pas dans cette branche.

| Exigence | Statut | Preuve | Manque |
|---|---|---|---|
| Installation Docker documentée | À_TESTER | `README.md`, `docs/DEPLOYMENT.md`, `docker-compose.yml` | Démarrage Docker non rejoué. Le README de `main` demande encore la branche fusionnée `feat/assets-depreciation`. Correction déjà proposée dans la PR #22, non fusionnée. |
| `scripts/start_local.py` et `SoloLMNP.bat` | NON_CONFORME | Absents du dépôt | Le démarrage réel documenté est Docker Compose ou les commandes natives de `docs/DEPLOYMENT.md`. |
| Activité, biens, exercices, migrations 0001–0005 | À_TESTER | `backend/alembic/versions/` | 224 tests backend réussis le 23 octobre 2026. Parcours navigateur non rejoué. |
| Le terrain d'une construction se saisit à part, compte 211, et les frais d'un bien n'entrent pas dans le total terrain + bâtiment | NON_CONFORME | Le refus d'immobilisation sur `main` ne dit pas d'inscrire le terrain à part | Correction déjà dans la PR #25, non fusionnée et non rejouée ici. La règle de calcul, elle, est déjà appliquée. |
| Un chevauchement d'exercice, une année de clôture en double, un compte 164 ou 512 déjà pris expliquent la correction | NON_CONFORME | `backend/app/api/sessions.py` sur `main` renvoie encore le message générique d'intégrité | Correction déjà dans la PR #24, non fusionnée et non rejouée ici. |
| Écritures validées équilibrées, correction par extourne | À_TESTER | `backend/app/services/ledger.py` | Suite backend réussie le 23 octobre 2026, sans parcours navigateur. |
| Journal, grand livre, balance dérivés du ledger | À_TESTER | `frontend/src/features/LedgerPage.tsx` | 53 tests frontend réussis. Parcours navigateur non rejoué. |
| Recettes, dépenses, banque, emprunts ventilés | À_TESTER | `docs/PHASE3_REPORT.md`, issue #4 fermée | Suite backend réussie. Parcours navigateur non rejoué. |
| Le rapprochement ne propose que les écritures validées de même compte, montant signé et date | VALIDÉ | `frontend/src/features/OperationsPage.tsx`, `backend/app/services/operations.py`. Tests `test_match_states_why_same_amount_on_another_date_is_refused`, `test_match_states_that_a_reversed_entry_cannot_be_reconciled` et les deux tests d'écran réussis le 23 octobre 2026. | Une ligne déjà rapprochée n'est pas retirée de la liste avant l'envoi. Le refus `LINE_ALREADY_MATCHED` n'a pas de test dédié. Parcours navigateur non rejoué. |
| Terrain 211 non amortissable, ventilation manuelle | À_TESTER | `test_land_can_never_be_depreciated` fait partie des 224 tests réussis | La valeur du terrain n'est pas reprise automatiquement dans le registre. L'explication d'écran est dans la PR #25. |
| Dotations comptables dans le ledger | À_TESTER | `docs/PHASE4_REPORT.md` | Issue #5 encore ouverte. |
| Bilan et résultat uniquement depuis les écritures validées | À_TESTER | `backend/app/services/statements.py` | Statut forcé `PROVISIONAL`. Présentation réglementaire absente. |
| L'écran des états ne présente plus l'inventaire comme absent | NON_CONFORME | `frontend/src/features/StatementsPage.tsx` sur `main` dit encore que l'inventaire reste à contrôler | Correction déjà dans la PR #23, non fusionnée et non rejouée ici. |
| Inventaire manuel justifié, revue, idempotence | À_TESTER | `backend/app/services/inventory.py`, `frontend/src/features/InventoryForm.tsx` | Pas de schémas CCA/PCA/FNP/PAR. Pièces non archivées. Q-003 en attente. |
| À-nouveaux idempotents et continuité | BLOQUÉ | `backend/app/services/opening_posting.py` exige une source `CLOSED`. La prévisualisation exige un prédécesseur qui se termine la veille. | Aucun parcours de clôture. Q-001 en attente. |
| Clôture, réouverture auditée, immutabilité | NON_CONFORME | `docs/CLOSING_PROCESS.md` décrit le flux ; aucun service ni écran | Issue #8 ouverte. Q-001 et Q-002 en attente. |
| Moteur fiscal versionné et reports | NON_CONFORME | `fiscal/2025/rules.yaml`, `fiscal/2026/rules.yaml` | Statut `research_only` conservé. Issue #7 ouverte. |
| FEC reproductible | NON_CONFORME | `docs/FEC.md` seulement | Issue #9 ouverte. Dépend d'un exercice clôturé. |
| Liasse 2031/2033 et feuille EFI | NON_CONFORME | `docs/TAX_FORMS.md`, `docs/FILING.md` | Issues #10 et #11 ouvertes. |
| Sauvegarde et restauration vers une copie de contrôle | NON_CONFORME | `docs/BACKUP.md` | Issue #12 ouverte. |
| Parcours A–J de bout en bout | NON_CONFORME | `backend/tests/golden/test_phase0_scenarios.py` est un catalogue | Issue #13 ouverte. |
| Télétransmission, LMP, cession, TVA, plus-values, ventilation automatique du terrain | HORS_PÉRIMÈTRE | Périmètre du dépôt et de la mission | Ne pas implémenter. |
| Millésime 2026 et 2042-C-PRO au statut `ready` | HORS_PÉRIMÈTRE | `backend/app/main.py` force `research_only` | Ne pas promouvoir. |
| Un refus de validation Pydantic affiche la phrase métier | NON_CONFORME | `frontend/src/api/ledger.ts` sur `main` ignore `detail[].msg` | Correction déjà dans la PR #23, non fusionnée et non rejouée ici. |
| Écriture depuis le serveur de développement natif | NON_CONFORME | `frontend/vite.config.ts` sur `main` remplace l'en-tête Host | Correction déjà dans la PR #22, non rejouée ici. |
| L'accueil décrit le périmètre réellement livré | NON_CONFORME | `frontend/src/App.tsx` affiche encore « Phase 4 · Immobilisations » et dit que l'inventaire reste à développer | Correction déjà dans la PR #22. |
