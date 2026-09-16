# Sauvegarde et restauration

Phase 11 produira une archive locale contenant une sauvegarde cohérente SQLite, documents, manifeste (schéma/application/millésimes), tailles et SHA-256. Aucun secret d'environnement. Création dans un fichier temporaire à permissions restrictives puis renommage atomique.

La restauration refuse chemins absolus, `..`, liens, doublons, archives démesurées et empreintes invalides ; elle contrôle versions et base avant remplacement. Toujours tester sur copie, conserver plusieurs générations hors machine et chiffrer les archives contenant des données personnelles.
