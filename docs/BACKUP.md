# Sauvegarde et restauration

`POST /api/filing/backup` écrit une archive locale : copie SQLite via l’API backup, documents du répertoire configuré, manifeste (version, révision de schéma, millésimes fiscaux et empreinte de leurs règles, tailles, SHA-256). Aucun secret d’environnement. Le zip est composé dans un fichier temporaire puis renommé.

`POST /api/filing/backup/restore` refuse un nom contenant `..`, un lien, un doublon, une archive trop grande, une empreinte fausse ou un schéma différent. La base extraite est contrôlée, puis écrite dans `restore-check.sqlite3` à côté de la base ouverte. Le fichier en service n’est pas remplacé tant que l’application tourne. Conserver plusieurs générations hors machine et chiffrer les archives qui contiennent des données personnelles.
