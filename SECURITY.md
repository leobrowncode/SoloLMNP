# Politique de sécurité

Projet en phase de conception : ne pas l'utiliser pour des données réelles. Signaler confidentiellement les vulnérabilités au mainteneur du dépôt.

Principes : écoute loopback, moindre privilège, CORS en liste fermée, requêtes SQLAlchemy paramétrées, CSP au proxy, aucun rendu HTML non assaini, aucun shell construit avec entrée utilisateur. Les uploads seront limités, détectés par signature et extension, renommés en UUID, créés sans écrasement hors webroot, hachés SHA-256 et jamais interprétés. YAML sera chargé via `safe_load`; pickle et XML avec entités sont interdits. Secrets et données personnelles sont exclus de Git.

Les backups sont sensibles : archive manifeste + base SQLite cohérente + documents, chiffrement recommandé hors application, restauration dans un répertoire temporaire validé avant remplacement atomique.
