# Phase 11 — justificatifs et sauvegarde

Un document PDF, JPEG ou PNG est déposé en base64 vers `documents_dir`. Le nom stocké est un identifiant et une extension. La taille est bornée par `max_upload_bytes`. Un chemin utilisateur, `..` ou un lien n’est pas accepté. Le texte de justification d’inventaire reste valable sans fichier.

Un PDF, JPEG ou PNG est accepté seulement si ses premiers octets correspondent au type annoncé. La sauvegarde copie SQLite avec l’API backup, joint les documents et un manifeste (y compris les millésimes fiscaux), puis renomme le zip. La restauration contrôle l’archive et écrit `restore-check.sqlite3` à côté de la base ouverte. Elle ne remplace pas le fichier en service. L’écran Conservation dépose un justificatif et lance ces deux opérations. Voir [BACKUP.md](BACKUP.md).

L’issue #12 reste ouverte sur le remplacement opérationnel après arrêt de l’application, qui reste une action de l’opérateur.
