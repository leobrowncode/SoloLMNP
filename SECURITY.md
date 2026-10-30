# Politique de sécurité

Ne pas utiliser SoloLMNP comme base de déclaration. Les millésimes chargés restent en recherche. Signaler confidentiellement les vulnérabilités au mainteneur du dépôt. La relecture du 30 octobre 2026, les correctifs et les risques acceptés sont dans [docs/SECURITY.md](docs/SECURITY.md).

Principes : écoute loopback sur la machine hôte, moindre privilège, CORS en liste fermée, requêtes SQLAlchemy paramétrées, CSP au proxy, aucun rendu HTML non assaini, aucun shell construit avec entrée utilisateur. Les uploads sont limités, détectés par signature, renommés en UUID, créés sans écrasement hors webroot, hachés SHA-256 et jamais interprétés. YAML est chargé via `safe_load` ; pickle et XML avec entités sont interdits. Secrets et données personnelles sont exclus de Git.

Les backups sont sensibles : archive manifeste + base SQLite cohérente + documents, chiffrement recommandé hors application. La restauration contrôle l’archive, prend une sauvegarde préalable, puis remplace atomiquement le fichier SQLite. Elle ne réécrit pas une écriture validée en place.

Dans Compose, le conteneur API écoute `0.0.0.0` pour le proxy du frontend. Ce port n’est pas publié. L’interface publiée est liée à `127.0.0.1`.
