# Archive

Ces documents décrivent l'état du dépôt avant la refonte v1. Ils ne sont plus le contrat. Le contrat est `SPEC.md` à la racine. Le tag git `v0-archive` pointe sur `main` avant les retraits de cette refonte.

## Contenu

- `PHASE*_REPORT.md` : rapports de phase P0 à P12.
- `AGENT_STATE.md` : mémoire de travail des agents, hors v1.
- `audit/` : audits d'octobre et de novembre 2026, captures comprises.
- `hors-v1/gsheet/` : Apps Script Google Sheets. Sheets est hors v1.

## Legacy encore dans l'arbre

Auth Neon, Postgres, Vercel, Blob, corrections structurantes, sauvegarde et restauration, TVA, cession et LMP ne font pas partie de la v1. Leur code reste dans `backend/` et `frontend/` pour ne pas casser la suite legacy, et pour réutiliser le moteur fiscal, le FEC, la liasse et le plan de comptes. Le chemin v1 est `lmnp_core` : il ne les appelle pas. Les lancer n'est pas demandé par `SPEC.md`.
