# Journal des exécutions

## 2026-10-19

- Référence : `main` `0a59960`. Branche `cursor/sololmnp-conformit-livraison-1423`, commits `787887c` et `a7b7377`. PR : https://github.com/leobrowncode/SoloLMNP/pull/22
- Anomalies confirmées :
  - P5 incomplète et P6–P12 absentes. Issues #6 à #13 ouvertes. Seule l'issue #4 est fermée.
  - Les à-nouveaux sont inutilisables sans clôture. Gravité P1, preuve `OpeningPosting.tsx` et `docs/PHASE5_REPORT.md`.
  - L'accueil, le README et `docs/DEPLOYMENT.md` présentaient l'inventaire, les états ou la comptabilité comme non livrés, et le README demandait la branche déjà fusionnée `feat/assets-depreciation`.
  - `scripts/start_local.py` et `SoloLMNP.bat` sont absents.
- Travail : correction du périmètre affiché, navigation qui désigne l'écran actif, aide du registre des biens vers Immobilisations, matrice initiale et questions Q-001 à Q-003.
- Tests exécutés : `python scripts/check.py --frontend-only` avec Node 24.22.0. ESLint, TypeScript, 52 tests frontend et build Vite réussis.
- Défaut confirmé pendant le parcours : le proxy Vite remplaçait Host, donc toute écriture locale recevait 403. Correction dans `frontend/vite.config.ts`. Chrome a ensuite créé un exercice synthétique (201) et parcouru inventaire, états, biens et immobilisations, y compris en 390 px. Suite backend et Docker non rejouées.
- Questions : Q-001, Q-002, Q-003, toutes `EN_ATTENTE_UTILISATEUR`.
- Bloquant : pas de clôture tant que Q-001 n'est pas tranchée.
- Prochaine priorité : si Q-001 répond A, spécifier puis livrer la clôture minimale auditée. Sinon, ne pas l'inventer.
