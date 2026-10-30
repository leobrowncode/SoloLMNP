# Schéma de données proposé

## Implémentation P1 (16 septembre 2026)

La migration `0001_foundation` crée uniquement `rental_activity`, `property`
et `fiscal_year`, plus la table de version Alembic. Le reste de ce document
décrit la cible, pas des fonctionnalités livrées.

Une activité au maximum par instance (clé 1), plusieurs biens, exercices liés
à l'activité et uniques par année. Les identifiants SIREN/SIRET sont facultatifs
au stade de préparation ; leur format et leur cohérence de préfixe sont contrôlés,
sans prétendre vérifier leur existence administrative.

Les valeurs monétaires sont des colonnes INTEGER, converties par le type
SQLAlchemy `Money` depuis/vers Decimal. Aucune conversion implicite de float,
aucun arrondi de sous-centime. Les CHECK refusent les montants négatifs et les
valeurs SQLite non entières. La ventilation terrain/bâtiment et les frais
d'acquisition restent des données administratives à valider en P4, pas une
base amortissable déjà approuvée.

Les timestamps sont stockés en UTC sans fuseau, selon la convention explicite
de l'adaptateur SQLite. L'API n'expose que santé et disponibilité ; pas de CRUD
métier ni de clôture à ce stade. Le schéma de statuts ne remplace pas les futurs
contrôles de chevauchement, de verrouillage et d'audit. Toute table cible future
sera ajoutée par une migration distincte.

Sources techniques : [SQLAlchemy SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html),
[Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html),
[Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/),
consultées le 15 septembre 2026.

Toutes les tables ont clés entières/UUID, dates ISO, timestamps UTC, contraintes et index de clés étrangères. Argent : entier en centimes accompagné de devise EUR (choix persistant recommandé) et conversion `Decimal`; taux : chaîne décimale. SQLite : `foreign_keys=ON`, WAL et sauvegarde via API SQLite.

## Agrégats

- `rental_activity`, `property`, `fiscal_year` (`OPEN|READY_TO_CLOSE|CLOSED`, millésime obligatoire).
- `account`, `accounting_journal`, `accounting_entry`, `accounting_entry_line`; unicité `(fiscal_year_id,journal_code,entry_number)`.
- `revenue`, `expense` référencent bien, exercice et écriture ; montant comptable brut distinct de pourcentage/traitement fiscal.
- `bank_account`, `bank_import`, `bank_transaction` (empreinte de dédoublonnage), `reconciliation`.
- `loan` conserve les termes contractuels (capital, taux, durée, mensualité et assurance
  mensuelles). Les échéances dans `business_operation` séparent principal, intérêts,
  assurance et frais et référencent chacune une écriture. Le capital restant est dérivé
  du compte 164, il n'est pas un second total modifiable.
- `asset`, `asset_component`, `depreciation_schedule`, `depreciation_period`; contraintes base, cumul et terrain.
- `fiscal_computation`, `depreciation_carry_forward`, `tax_loss_carry_forward`, `carry_forward_event` : le calcul, le stock créé par exercice, et l’historique des créations, utilisations et expirations. Une ligne d’historique appartient au calcul qui l’a constatée. L’invalidation de ce calcul la sort du solde. L’amortissement non déduit n’a pas de ligne `expired`.
- `tax_form`, `tax_form_field`, `tax_mapping`, `tax_form_field_result`, `tax_return_package`, `tax_return_snapshot`.
- `supporting_document`, plus tables d'association typées ; stockage UUID et empreinte SHA-256 unique contrôlée.
- `audit_event`, append-only ; `validation_result` est recalculable et rattaché à un run.

## Ledger

`accounting_entry` contient exercice, journal, numéro, dates, pièce, libellé, source type/id, statut, timestamps. `accounting_entry_line` contient ordre, compte, libellé, débit et crédit. Une transaction applicative verrouille l'exercice, contrôle chaque ligne puis les totaux avant `validated_at`. SQLite ne pouvant exprimer une somme inter-lignes avec CHECK, service + trigger défensif de transition seront testés.

## Fiscalité et traçabilité

Chaque résultat de case stocke valeur, expression évaluée, comptes, écritures et Rule IDs. Le package sérialise données triées et versions ; le snapshot stocke JSON canonique et SHA-256 des exports. La réouverture marque les snapshots `SUPERSEDED`, sans suppression.

## Package, snapshot et audit

`TaxReturnPackage` est une valeur calculée : exercice/millésime, empreinte du ledger, résultat comptable, retraitements, résultat fiscal, formulaires/champs, validations, versions application/règles/mappings et date. Sa sérialisation canonique trie clés et listes métier.

`TaxReturnSnapshot` est l'enveloppe persistée immuable : identifiant de package, versions, JSON canonique, empreintes d'exports, statut `CURRENT|SUPERSEDED`. Une nouvelle clôture crée un nouvel objet.

`AuditEvent` est append-only : timestamp UTC, entité/id, action, champ, anciennes/nouvelles valeurs JSON, motif et métadonnées. Les valeurs sensibles sont minimisées ; les événements de clôture, réouverture et snapshot ne peuvent être purgés par l'UI.


## Schéma P2

La migration 0002_ledger ajoute account, accounting_journal, accounting_entry, accounting_entry_line et ledger_event. AccountingEntry porte DRAFT/VALIDATED, une version optimiste, sequence, entry_number et reversal_of_id. Les libellés sont figés lors de la validation. Les lignes contiennent des centimes INTEGER. LedgerEvent est append-only et survit à la suppression d’un brouillon. Voir [le rapport](PHASE2_REPORT.md).

## Schéma P3

La migration `0003_operations` ajoute comptes bancaires, mouvements importés, rapprochements, emprunts et opérations métier. `BusinessOperation.accounting_entry_id` est unique ; `request_id` rend les créations idempotentes. `BankMatch` est une relation un-à-un entre mouvement et ligne comptable. Les opérations, les mouvements bancaires et les rapprochements restent immuables. Les emprunts, comptes bancaires, biens et locataires acceptent une correction auditée tant que leur verrou métier ne s’applique pas. Les suppressions de migration sont refusées dès qu'elles contiennent des données. Voir [PHASE3_REPORT.md](PHASE3_REPORT.md).

## Schéma P4

La migration `0004_assets` persiste `asset`, `asset_component`,
`depreciation_schedule` et `depreciation_period`. Les deux premières tables conservent
les hypothèses documentées, le plan les fige et la période porte le résultat exact par
exercice ainsi que le lien unique vers l'écriture. Une construction décomposée ne reçoit
pas elle-même de plan : seuls ses composants sont amortis. Voir
[PHASE4_REPORT.md](PHASE4_REPORT.md).

## Corrections contrôlées

La migration `0009_structuring` remplace les triggers d’interdiction totale de
`UPDATE` sur l’immobilisation, le composant, le plan, l’emprunt et le compte
bancaire. La suppression reste interdite : aucune route `DELETE`. Un plan qui a
une période `POSTED` refuse encore la modification de la valeur, de la durée,
des dates et des comptes (`ASSET_HAS_POSTED_DEPRECIATION`,
`COMPONENT_HAS_POSTED_DEPRECIATION`, `SCHEDULE_IMMUTABLE`). Un emprunt déjà
mouvementé garde son capital initial, sa date de départ, son bien et son compte
164. Un numéro bancaire qui a des mouvements reste en place. Les colonnes
financières d’un bien qui a déjà une immobilisation ne bougent plus. Le nom, le
loyer et la date d’entrée d’un locataire qui a des quittances non plus.

L’API `PATCH` est le chemin supporté. Elle écrit un `audit_event` (`CORRECTED`,
avant, après, motif). Elle efface les périodes `CALCULATED` d’un exercice ouvert,
réaligne le plan sur la fiche, invalide les calculs fiscaux ouverts, repasse
`READY_TO_CLOSE` à `OPEN` et marque `SUPERSEDED` les instantanés ouverts. Les
écritures validées, et donc le FEC, ne sont pas réécrites. Un calcul fiscal
clôturé qui a mémorisé la base n’est ni invalidé ni recalculé : la valeur et la
durée sont refusées jusqu’à réouverture.

## Historique des reports

La migration `0010_carry_events` ajoute `carry_forward_event`. Chaque ligne est
un mouvement `created`, `used` ou `expired`, rattaché au calcul qui l’a
constaté. L’invalidation de ce calcul sort le mouvement du solde. Le registre
`depreciation_carry_forward` ou `tax_loss_carry_forward` conserve le montant
créé par exercice d’origine. Un amortissement non déduit n’a pas de mouvement
`expired`. Un recalcul du même exercice remplace ses mouvements.

## Index de lecture du journal

La migration `0011_entry_year_status` ajoute `ix_accounting_entry_year_status_date` sur `accounting_entry` (`fiscal_year_id`, `status`, `accounting_date`, `sequence`). Le journal, la balance, les états et le FEC filtrent les écritures validées d’un exercice puis les trient par date. L’index évite de parcourir toutes les écritures du fichier quand plusieurs exercices sont stockés.
