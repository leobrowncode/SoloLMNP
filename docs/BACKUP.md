# Sauvegarde et restauration

`POST /api/filing/backup` écrit une archive locale : copie SQLite via l’API backup, justificatifs enregistrés dans cette base (un fichier du dossier qui n’est pas en base, ou dont le nom commence par un point, comme `.gitkeep`, n’est pas archivé), manifeste (date, version, révision de schéma, millésimes fiscaux et empreinte de leurs règles, tailles, SHA-256). Aucun secret d’environnement. Le zip est composé dans un fichier temporaire puis renommé. Deux sauvegardes successives ne s’écrasent pas.

`GET /api/filing/backups` liste ces archives : date, taille, version de l’application, révision de schéma, empreinte SHA-256 et résultat du dernier contrôle d’intégrité (`unchecked`, `ok` ou `failed`). Un contrôle dont l’empreinte ne correspond plus au fichier redevient `unchecked`.

`POST /api/filing/backups/verify` rejoue les contrôles (chemins, doublons, taille, empreintes du manifeste, chemins de justificatifs, `PRAGMA integrity_check`, révision de schéma) et enregistre le résultat à côté des archives, dans `integrity.json`. Ce fichier n’entre pas dans l’archive. Le contrôle refuse une archive que la restauration refuserait.

`GET /api/filing/backups/preview?filename=` compare la base en service et l’archive : date de la sauvegarde, nombre d’écritures, nombre d’exercices. Rien n’est écrit.

`POST /api/filing/backup/restore` exige `confirmation: "RESTAURER"` et un fichier déjà présent dans la liste. Il refuse un nom contenant `..`, un lien, un doublon, une archive trop grande, une empreinte fausse, un schéma différent ou un chemin de justificatif qui n’est pas un seul nom de fichier sûr. Un nom de justificatif qui commence par un point (`.gitkeep` dans une archive déjà produite) est ignoré : il ne fait pas échouer la restauration. Avant le remplacement, une sauvegarde de l’état actuel est créée. La base extraite est contrôlée, les connexions sont fermées, le fichier SQLite est remplacé, puis les justificatifs du répertoire sont alignés sur l’archive. Les écritures validées ne sont pas modifiées une à une : la base entière est reprise telle qu’elle était. Si le remplacement échoue, la base et les justificatifs d’avant sont remis en place. Un échec de ce retour arrière est journalisé et remonté.

`GET /api/filing/documents` liste les justificatifs : nom, date, type, taille, empreinte SHA-256 et écriture liée (numéro, date, pièce). `GET /api/filing/entries` cherche une écriture par numéro, date ou pièce, sans exposer d’identifiant interne. `POST /api/filing/documents/{id}/link` enregistre cette liaison sur le justificatif seulement.

Conserver plusieurs générations hors machine et chiffrer les archives qui contiennent des données personnelles.
