# Clôture

`OPEN → READY_TO_CLOSE → CLOSED`. Le pré-contrôle vérifie opérations, écritures, pièces, actifs, terrain, amortissements, inventaire, balance, bilan, résultat, fiscalité, reports, mappings et FEC. Toute validation `ERROR` bloque ; les warnings exigent prise de connaissance. La fermeture transactionnelle fige numérotation et versions puis émet un AuditEvent.

Réouverture : confirmation forte, motif obligatoire, audit du statut précédent, passage à OPEN, invalidation des calculs/exports et marquage `SUPERSEDED` des snapshots. Les anciennes preuves restent lisibles. La clôture suivante crée une nouvelle génération, jamais une mutation du snapshot.
