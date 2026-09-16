# SoloLMNP

Application libre, mono-utilisateur et auto-hébergeable de comptabilité LMNP au réel simplifié. **Phase 0 : architecture et recherche uniquement.** Elle ne produit encore ni déclaration ni FEC utilisable.

## Principes non négociables

Le flux est : événements métier → ledger en partie double → états comptables → retraitements fiscaux versionnés → formulaires → feuille de saisie EFI. Le ledger persistant est l'unique source du journal, grand livre, balance, bilan, résultat et FEC. Tous les montants utilisent `Decimal` côté Python et des chaînes décimales aux frontières JSON.

## Démarrage de développement

```bash
cp .env.example .env
docker compose up --build
```

Services liés par défaut à `127.0.0.1` : interface `:5173`, API et documentation `:8000/api/docs`. Pour les tests locaux : Python 3.12+, Node 22+, puis `make test lint typecheck`.

## État et limites

La phase 0 fournit les squelettes, contrats du ledger, documentation d'architecture, inventaire prudent des sources et scénarios de référence. Les définitions fiscales sont marquées `research_only`: aucune valeur ne doit être utilisée pour déposer une déclaration avant implémentation, revue des sources du millésime et validation métier.

Voir [l'architecture](ARCHITECTURE.md), la [roadmap](ROADMAP.md), la [sécurité](SECURITY.md) et le [processus déclaratif](docs/FILING.md).
