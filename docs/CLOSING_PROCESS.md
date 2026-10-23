# Clôture

## Clôture minimale livrée

Décision Q-001 A du 23 octobre 2026 : `OPEN → CLOSED`, avec réouverture motivée. Depuis Comptabilité, « Clôturer l’exercice » exige une confirmation. La clôture refuse les brouillons et un ledger qui ne peut pas produire des états équilibrés. Elle ne crée aucune écriture, ne centralise pas les classes 6 et 7, et ne crée pas les comptes 120 ou 129.

Décision Q-002 A du même jour : à la génération des à-nouveaux, le résultat est repris seulement sur le compte 120 ou 129 choisi explicitement, avant toute affectation.

`POST /api/ledger/years/{id}/close` et `POST /api/ledger/years/{id}/reopen` écrivent un événement `YEAR_CLOSED` ou `YEAR_REOPENED`. La réouverture exige un motif d’au moins cinq caractères. Les écritures déjà validées restent modifiables uniquement par extourne.

## Contrôle complet encore à livrer

Le parcours documenté pour une clôture réglementaire reste `OPEN → READY_TO_CLOSE → CLOSED`. Son pré-contrôle doit encore vérifier opérations, écritures, pièces, actifs, terrain, amortissements, inventaire, balance, bilan, résultat, fiscalité, reports, mappings et FEC. Toute validation `ERROR` bloque ; les warnings exigent prise de connaissance. La fermeture transactionnelle fige numérotation et versions puis émet un AuditEvent. Ce contrôle n’est pas celui de la clôture minimale.

La réouverture du contrôle complet devra encore invalider les calculs et exports, puis marquer `SUPERSEDED` les snapshots. Les anciennes preuves resteront lisibles. La clôture suivante créera une nouvelle génération, jamais une mutation du snapshot. Ces snapshots n’existent pas encore.
