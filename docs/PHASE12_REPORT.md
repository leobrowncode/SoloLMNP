# Phase 12 — durcissement

Les assertions nommées des scénarios A à J de `backend/tests/fixtures/scenarios.json` sont exécutées sur une base temporaire : ouverture explicite, ledger équilibré, continuité après clôture réelle, isolation des millésimes, plafond d’amortissement, déficit séparé, prorata, cumul borné, ventilation d’emprunt, charge partielle, verrou, motif de réouverture, snapshot remplacé, FEC déterministe, traçabilité des cases, contrôle inter-formulaire et absence de télétransmission.

Les formulaires d’états, d’inventaire et de clôture ont un nom accessible. Une erreur reçoit le focus. Le journal, les états et le rendu FEC restent sous un plafond de 40 requêtes SQL pour le volume du test.

Les risques résiduels sont notés dans [SECURITY_AUDIT.md](SECURITY_AUDIT.md). L’issue #13 reste ouverte : il n’y a pas d’authentification, et le statut fiscal prêt est toujours refusé.
