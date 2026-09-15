# Audit de sécurité initial — 2026-09-15

| Risque | Mesure d'architecture | Résiduel/action |
|---|---|---|
| Exposition sans authentification | ports Docker sur loopback | documenter proxy privé ; jamais Internet direct |
| Injection SQL | ORM et paramètres | interdire SQL concaténé, tests |
| XSS | React échappé/CSP future | interdire `dangerouslySetInnerHTML` |
| Traversée/upload | UUID, signature MIME, taille, hors webroot | scanner et tests Phase 11 |
| Désérialisation | YAML sûr, aucun pickle, DSL sans eval | revue des loaders |
| SSRF/command/XXE | aucune récupération URL utilisateur, aucun shell/XML | règles statiques |
| Corruption SQLite | transactions, FK, WAL, backup API | tests crash/restauration |
| Fuite Git | gitignore strict et fixtures fictives | secret scan CI à ajouter |
| Supply chain | versions bornées backend, audit npm | verrouiller hashes/lockfiles |
| Intégrité fiscale | sources/version/empreintes/golden tests | revue humaine obligatoire |

Les images conteneur ne sont pas encore durcies en utilisateur non-root et les dépendances `latest` du squelette frontend doivent être verrouillées par `package-lock.json` avant production. Aucun mécanisme applicatif d'authentification n'est prévu conformément au modèle mono-utilisateur.
