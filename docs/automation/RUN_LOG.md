# Journal des exécutions

## 2026-10-19

- Référence : `main` `0a59960`. Branche `cursor/sololmnp-conformit-livraison-1423`. PR : https://github.com/leobrowncode/SoloLMNP/pull/22
- Travail déjà proposé, non fusionné : périmètre affiché, navigation de l'écran actif, proxy Vite qui conserve l'en-tête Host.
- Questions Q-001, Q-002 et Q-003 laissées `EN_ATTENTE_UTILISATEUR`. Ne pas les traiter comme approuvées et ne pas refaire cette PR.

## 2026-10-20

- Référence : `main` `0a59960`. Branche `cursor/sololmnp-livraison-produit-5280`, commit `a999b4f`. PR : https://github.com/leobrowncode/SoloLMNP/pull/23
- Écarts confirmés, hors du lot du jour : pas de clôture (P1, à-nouveaux bloqués), P6–P12 absents, accueil et README en retard sur `main` (PR #22), proxy Vite qui rejette les écritures locales (PR #22), lanceurs `scripts/start_local.py` et `SoloLMNP.bat` absents.
- Écart traité : un refus Pydantic 422 remplaçait la phrase métier par « Opération refusée… ». L'écran des états disait encore que l'inventaire restait à contrôler.
- Travail : `refusalMessage` affiche `detail.message` ou la phrase française de `detail[].msg`, sans le préfixe `Value error, ` ni le corps saisi. Le texte des états distingue l'inventaire manuel, livré, de la clôture et des états réglementaires, absents.
- Tests exécutés avec Node 22.14.0 (le dépôt demande Node 24) : ESLint, TypeScript, 54 tests frontend et build Vite réussis. Le préfixe Pydantic a été reproduit avec Pydantic 2.13.5. Suite backend, Docker, CI et parcours navigateur non exécutés.
- Questions : Q-001, Q-002, Q-003, toujours sans réponse.
- Bloquant : pas de clôture tant que Q-001 n'est pas tranchée.
- Prochaine priorité : si Q-001 répond A, spécifier puis livrer la clôture minimale auditée. Sinon, corriger un défaut P5 confirmé qui ne dépend pas de cette décision.
