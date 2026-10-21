# Journal des exécutions

## 2026-10-19

- Référence : `main` `0a59960`. Branche `cursor/sololmnp-conformit-livraison-1423`. PR : https://github.com/leobrowncode/SoloLMNP/pull/22
- Travail déjà proposé, non fusionné : périmètre affiché, navigation de l'écran actif, proxy Vite qui conserve l'en-tête Host.
- Questions Q-001, Q-002 et Q-003 laissées `EN_ATTENTE_UTILISATEUR`. Ne pas les traiter comme approuvées et ne pas refaire cette PR.

## 2026-10-20

- Référence : `main` `0a59960`. Branche `cursor/sololmnp-livraison-produit-5280`, commit `a999b4f`. PR : https://github.com/leobrowncode/SoloLMNP/pull/23
- Écart traité : un refus Pydantic 422 remplaçait la phrase métier par « Opération refusée… ». L'écran des états disait encore que l'inventaire restait à contrôler.
- Questions : Q-001, Q-002, Q-003, toujours sans réponse.
- Ne pas refaire cette PR.

## 2026-10-21

- Référence : `main` `0a59960`. Branche `cursor/sololmnp-conformit-livraison-54d3`, commit `d9811e9`. PR : https://github.com/leobrowncode/SoloLMNP/pull/24
- Écarts confirmés, hors du lot : pas de clôture (P1), P6–P12 absents, accueil et README en retard (PR #22), proxy Vite (PR #22), messages Pydantic (PR #23), lanceurs `scripts/start_local.py` et `SoloLMNP.bat` absents.
- Écart traité : créer un exercice chevauchant, réutiliser une année de clôture, un compte 164 ou un compte 512 renvoyait « Opération refusée par les contraintes d’intégrité. » Le formulaire ne disait pas que l'exercice suivant doit commencer le lendemain exact.
- Travail : ces quatre refus portent un code et une phrase de correction. Le formulaire d'exercice énonce la règle de continuité. Aucune règle comptable, aucun schéma et aucune donnée de `data/` modifiés.
- Tests : Python 3.12, `pip check`, Ruff, mypy, 224 tests backend, couverture 94 %. Node 22.23.3 (le dépôt demande Node 24) : ESLint, TypeScript, 52 tests frontend, build Vite. Docker, CI distante et création d'exercice dans le navigateur non exécutés. Le proxy Vite de `main` refuse toujours les écritures locales.
- Questions : Q-001, Q-002, Q-003, toujours sans réponse.
- Bloquant : pas de clôture tant que Q-001 n'est pas tranchée.
- Prochaine priorité : si Q-001 répond A, spécifier puis livrer la clôture minimale auditée. Sinon, corriger un autre défaut confirmé qui ne dépend pas de cette décision, sans reprendre les PR #22 et #23.
