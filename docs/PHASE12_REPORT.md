# Phase 12 — parcours, sécurité, accessibilité, volume

Les scénarios A à J de `backend/tests/fixtures/scenarios.json` restent exécutés par `backend/tests/integration/test_scenarios.py` sur une base temporaire : ouverture explicite, ledger équilibré, continuité, isolation des millésimes, plafond d’amortissement, déficit séparé, prorata, cumul borné, ventilation d’emprunt, charge partielle, verrou de clôture, motif de réouverture, snapshot remplacé, FEC déterministe, traçabilité des cases, contrôle inter-formulaire, absence de télétransmission.

Le parcours navigateur (`e2e/`, Playwright, Chromium headless) parle à la même API avec une base temporaire hors de `data/`. Il enchaîne l’activité, un exercice dont la fin est d’abord antérieure au début, le SIREN, le bien, la banque, l’import CSV, les dotations, la centralisation, une réintégration, le calcul fiscal, la clôture, la feuille `research_only`, le FEC, les à-nouveaux de l’exercice suivant, puis une sauvegarde et une restauration. Les largeurs 320, 390, 768 et 1280 sont parcourues avec axe, sans violation, et sans défilement horizontal de la page. Ce job est dans la CI. Il n’est pas dans `scripts/check.py`.

Le message de dates d’exercice nomme la fin antérieure au début. L’année de clôture doit être celle de la date de fin. Le millésime n’est pas rejeté parce qu’il diffère de l’exercice.

La relecture de sécurité est dans [SECURITY.md](SECURITY.md). Les lectures de volume sont dans [PERFORMANCE.md](PERFORMANCE.md). Les limites et le cycle annuel sont dans [LIMITS.md](LIMITS.md) et [ANNUAL_CYCLE.md](ANNUAL_CYCLE.md).

Les millésimes 2025 et 2026 restent `research_only`. Aucune sortie de cette phase n’est annoncée comme déclarable. Il n’y a pas d’authentification tant que l’écoute reste locale. Le scénario d’emprunt (F) est couvert par le test d’API, pas par le navigateur. L’ouverture de la liasse peut journaliser une clé React dupliquée ; les montants du parcours restent ceux du ledger.
