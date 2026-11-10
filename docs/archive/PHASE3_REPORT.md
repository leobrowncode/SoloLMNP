# Phase 3 — Opérations, banque et emprunts

## Périmètre livré

La version 0.4.0 ajoute les biens nécessaires à l'affectation analytique, les recettes,
les dépenses, leurs règlements, les comptes bancaires, l'import CSV, le rapprochement
et les emprunts. Toutes les opérations comptabilisées créent une
`AccountingEntry` validée ; aucun total comptable concurrent n'est maintenu.

L'interface sépare Transactions, Banque, Biens et Emprunts. Elle impose une étape de
revue avant l'enregistrement d'une opération définitive. Les requêtes de création
utilisent un identifiant idempotent : répéter exactement une requête retourne la même
opération, tandis qu'une réutilisation avec un contenu différent est refusée.

## Chaîne de comptabilisation

- Recette non réglée : débit 411, crédit d'un compte de classe 7 choisi.
- Dépense non réglée : débit d'un compte de classe 6 choisi, crédit 401.
- Recette ou dépense réglée immédiatement : contrepartie dans le compte 512 choisi.
- Règlement ultérieur : apurement du 411 ou du 401 contre 512, sans constater une
  deuxième fois le produit ou la charge.
- Déblocage d'emprunt : débit 512, crédit du compte 164 dédié.
- Échéance : débit 164 pour le capital, comptes 6 distincts pour intérêts, assurance
  et frais, puis crédit 512 pour le total.

Le solde de capital d'un emprunt est calculé depuis les lignes validées du compte 164.
Une échéance ne peut pas rembourser davantage que ce solde. Le déblocage initial est
unique et doit égaler le capital initial ; une reprise historique peut utiliser une
écriture d'à-nouveaux justifiée au lieu d'un faux déblocage.

La dépense comptable conserve toujours son montant intégral. Le pourcentage et le
traitement fiscal sont seulement des métadonnées cohérentes et explicitement « à
vérifier » lorsqu'ils ne sont pas qualifiés. Cette phase ne calcule aucun résultat
fiscal.

## Import et rapprochement bancaires

Format V1 : UTF-8, point-virgule et en-tête exact
`date;label;amount;reference`. La date est ISO `AAAA-MM-JJ`, le montant est signé
et précis au centime, la référence doit être stable et unique pour le compte bancaire.

Le serveur limite la requête à 1 Mo et le fichier à 5 000 lignes. Il normalise les
montants, calcule des empreintes SHA-256, détecte les réimports et refuse une même
référence portant un contenu différent. Une prévisualisation précède l'import.

Un mouvement importé ne crée aucune écriture. L'utilisateur peut :

1. créer une recette ou dépense liée, ce qui crée exactement une écriture ;
2. rapprocher une ligne 512 existante de même compte, montant signé, date et exercice ;
3. laisser le mouvement en attente.

Une ligne comptable et un mouvement ne peuvent chacun participer qu'à un seul
rapprochement. L'annulation du rapprochement exige un motif et un exercice ouvert.
Une extourne métier annule d'abord son rapprochement en conservant l'audit.

Les suggestions simples basées sur le libellé ne sont jamais validées
automatiquement. Elles ne constituent ni une règle comptable ni une règle fiscale.

## Intégrité et sécurité

La migration `0003_operations` ajoute `property` existant comme référentiel de
bien et crée `bank_account`, `bank_transaction`, `bank_match`, `loan` et
`business_operation`. Elle conserve le schéma P2.

Les montants restent des centimes `INTEGER` dans SQLite, des `Decimal` en Python
et des chaînes décimales dans JSON. Le navigateur utilise `BigInt` avant tout envoi.

Les opérations, mouvements importés, emprunts et comptes bancaires sont immuables.
Les corrections comptables se font par extourne. Des triggers SQLite vérifient le
lien entre opération et écriture validée, le montant, la source, l'exercice ouvert,
la ventilation des échéances et les rapprochements. `BEGIN IMMEDIATE` sérialise
les écritures et les contrôles d'idempotence.

Les fichiers CSV sont lus comme du texte en mémoire : aucun chemin fourni par
l'utilisateur n'est utilisé, aucun tableur ou programme n'est exécuté. Cette limite
de taille est distincte du futur stockage des justificatifs.

## Sources comptables

Source officielle consultée le 16 septembre 2026 :
[Plan comptable général ANC au 1er janvier 2026](https://www.anc.gouv.fr/files/anc/files/1_Normes_fran%C3%A7aises/recueil/2026/PCG--1er-janvier-2026.pdf).

- Article 1214-41, pages 163–164 : fonctionnement des fournisseurs 401 et clients
  411, avec apurement par un compte de trésorerie lors du règlement.
- Plan de comptes, page 133, et article 1211-17, page 155 : compte 164 et
  subdivisions d'emprunts.
- Plan de comptes, page 144, et article 1221-66, page 177 : compte 661 et
  subdivisions des charges d'intérêts.
- Articles 1031-1 à 1032-2 : partie double, validation et pièces justificatives.

Ces références justifient la structure comptable. Elles ne déterminent pas la
déductibilité fiscale LMNP, qui demeure hors de cette phase.

## Vérification

Les tests couvrent les scénarios F, G et une partie des opérations courantes :
ventilation des échéances, dépense partiellement déductible, produits et charges à
l'engagement, règlements partiels, reprise d'emprunt, imports et réimports CSV,
rapprochement sans écriture supplémentaire, extournes, exercice fermé, concurrence,
idempotence et contournements SQL.

## Limites explicites

- Une transaction bancaire importée reste conservée même si elle est erronée ; elle
  peut rester non rapprochée. Un workflow append-only de correction du relevé sera
  ajouté avec l'audit complet.
- La catégorie suggérée se limite à quelques libellés évidents ; aucune
  catégorisation opaque ou automatique n'est utilisée.
- Pas d'OFX/QIF, d'API bancaire ni de calendrier d'emprunt généré.
- La mensualité et l'assurance contractuelles sont conservées comme termes informatifs.
  Les intérêts et échéances ne sont pas générés automatiquement : chaque échéance réelle
  doit être ventilée d'après le relevé du prêteur.
- TVA, immobilisation d'une dépense, charges constatées d'avance, factures non
  parvenues, bilan, fiscalité, FEC et liasse suivent les phases prévues.
