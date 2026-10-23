# Phase 7 — clôture et réouverture

Transitions `OPEN → READY_TO_CLOSE → CLOSED`, puis réouverture motivée vers `OPEN`. Le pré-contrôle refuse les brouillons, un ledger déséquilibré, des dotations calculées non comptabilisées, l’absence de centralisation lorsqu’il reste des soldes de classes 6/7, un calcul fiscal absent ou périmé, un mapping en erreur et un FEC invalide. Un avertissement doit être accusé avant de préparer la clôture. Les informations (périmètre du FEC, statut fiscal non prêt) sont affichées et ne font pas partie de cet accusé. La confirmation littérale `CLOTURER` fige l’exercice.

Chaque transition écrit un `AuditEvent` append-only. La réouverture exige `ROUVRIR` et un motif d’au moins dix caractères. Elle invalide les calculs fiscaux et marque les snapshots `SUPERSEDED` sans les supprimer. La génération suivante est un nouveau numéro. Les à-nouveaux exigent désormais un exercice source réellement clôturé.

L’issue #8 reste ouverte : le libellé fiscal prêt est refusé tant qu’une règle bloquante est désactivée.
