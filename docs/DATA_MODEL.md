# Schéma de données proposé

Toutes les tables ont clés entières/UUID, dates ISO, timestamps UTC, contraintes et index de clés étrangères. Argent : entier en centimes accompagné de devise EUR (choix persistant recommandé) et conversion `Decimal`; taux : chaîne décimale. SQLite : `foreign_keys=ON`, WAL et sauvegarde via API SQLite.

## Agrégats

- `rental_activity`, `property`, `fiscal_year` (`OPEN|READY_TO_CLOSE|CLOSED`, millésime obligatoire).
- `account`, `accounting_journal`, `accounting_entry`, `accounting_entry_line`; unicité `(fiscal_year_id,journal_code,entry_number)`.
- `revenue`, `expense` référencent bien, exercice et écriture ; montant comptable brut distinct de pourcentage/traitement fiscal.
- `bank_account`, `bank_import`, `bank_transaction` (empreinte de dédoublonnage), `reconciliation`.
- `loan`, `loan_payment` sépare principal, intérêts, assurance, frais et référence l'écriture.
- `asset`, `asset_component`, `depreciation_schedule`, `depreciation_period`; contraintes base, cumul et terrain.
- `tax_computation`, `fiscal_adjustment`, `depreciation_carry_forward`, `tax_loss_carry_forward` : lots et usages séparés, immuables après clôture.
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
