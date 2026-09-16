# Fichier des écritures comptables (FEC)

## Références de recherche

Base légale : [LPF article L47 A](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000042659296) et format prescrit par [article A47 A-1 du LPF](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000028219503). Doctrine : [BOI-CF-IOR-60-40](https://bofip.impots.gouv.fr/bofip/9028-PGP.html). Ces liens et textes consolidés doivent être revérifiés avant Phase 8.

## Contrat prévu

Le FEC provient exclusivement des écritures/lignes validées du ledger et d'un exercice clôturé. Il est déterministe : ordre chronologique stable, encodage et séparateur fixés, arrondi explicite, nom et empreinte reproductibles. L'exporteur produira les 18 champs réglementaires dans l'ordre (`JournalCode`, `JournalLib`, `EcritureNum`, `EcritureDate`, `CompteNum`, `CompteLib`, `CompAuxNum`, `CompAuxLib`, `PieceRef`, `PieceDate`, `EcritureLib`, `Debit`, `Credit`, `EcritureLet`, `DateLet`, `ValidDate`, `Montantdevise`, `Idevise`), sous réserve de confirmation du texte applicable.

## Validation

ERROR : champ obligatoire absent, format/date/montant invalide, numéro dupliqué incohérent, écriture déséquilibrée, compte/journal absent, date hors exercice, ordre non déterministe. WARNING : pièce faible, rupture chronologique, à-nouveaux/inventaire attendus absents. INFO : statistiques et empreinte. Un ERROR interdit le libellé « FEC valide ». Les conditions d'obligation et dispenses propres au contribuable ne seront pas déduites sans source.
