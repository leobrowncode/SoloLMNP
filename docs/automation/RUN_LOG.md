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
- Écart traité : créer un exercice chevauchant, réutiliser une année de clôture, un compte 164 ou un compte 512 renvoyait un message d'intégrité générique.
- Questions : Q-001, Q-002, Q-003, toujours sans réponse.
- Ne pas refaire cette PR. La clôture n'est pas implémentée.

## 2026-10-22

- Référence : `main` `0a59960`. Branche `cursor/sololmnp-conformit-livraison-5df6`.
- Écarts confirmés, hors du lot : pas de clôture (P1), P6–P12 absents, accueil et README en retard (PR #22), proxy Vite (PR #22), messages Pydantic (PR #23), conflits d'exercice génériques (PR #24), lanceurs `scripts/start_local.py` et `SoloLMNP.bat` absents.
- Écart traité : une construction pouvait recevoir le terrain dans sa part non amortissable. Le refus parlait seulement de base, de durée et de compte 28. La fiche bien refusait aussi un total terrain + bâtiment qui incluait les frais, sans le dire.
- Travail : le refus d'immobilisation demande d'inscrire le terrain à part sur un compte 211. Le refus de bien précise que les frais ne s'ajoutent pas au prix. Les deux écrans énoncent la règle avant la saisie. La fiche bien affiche les frais enregistrés. Aucune règle de calcul, aucun schéma et aucune donnée de `data/` modifiés.
- Tests : `python scripts/check.py` réussi. Python 3.12.3, `pip check`, Ruff, mypy, 224 tests backend, couverture 95 %. Node 22.23.3 (le dépôt demande Node 24) : ESLint, TypeScript, 53 tests frontend, build Vite. Docker, CI distante et parcours navigateur non exécutés.
- Questions : Q-001, Q-002, Q-003, toujours sans réponse.
- Bloquant : pas de clôture tant que Q-001 n'est pas tranchée.
- Prochaine priorité : si Q-001 répond A, spécifier puis livrer la clôture minimale auditée. Sinon, fusionner d'abord les PR #22, #23 et #24, qui corrigent des blocages de saisie déjà prouvés.
