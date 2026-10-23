# Fichier des écritures comptables (FEC)

## Références

Base légale : [LPF article L47 A](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000042659296) et format prescrit par l’article A47 A-1 du LPF. Le texte de l’arrêté du 29 juillet 2013 (JORFTEXT000027788276) a été relu le 2 octobre 2026 : les dix-huit premiers champs d’un fichier à plat sont, dans l’ordre, JournalCode, JournalLib, EcritureNum, EcritureDate, CompteNum, CompteLib, CompAuxNum, CompAuxLib, PieceRef, PieceDate, EcritureLib, Debit, Credit, EcritureLet, DateLet, ValidDate, Montantdevise, Idevise. Le fichier reprend les écritures après inventaire, y compris les à-nouveaux, et exclut les écritures de centralisation et de solde des comptes de charges et de produits. Doctrine : [BOI-CF-IOR-60-40-20](https://bofip.impots.gouv.fr/bofip/9028-PGP.html/identifiant=BOI-CF-IOR-60-40-20-20170607).

## Export livré

`GET /api/filing/years/{id}/fec` n’accepte qu’un exercice `CLOSED` dont l’activité a un SIREN. Le contenu est UTF-8 (admis par l’article A47 A-1 depuis l’arrêté de 2013), séparateur tabulation, fin de ligne CRLF, dates `YYYYMMDD`, montants avec virgule. Le nom suit la nomenclature `SirenFECAAAAMMJJ.txt` (IX de l’article A47 A-1).

`GET /api/filing/years/{id}/archive` produit le dossier de contrôle : FEC, sa description (XI de l’article A47 A-1 : zones, codes, jeu de caractères, séparateurs), feuille de liasse PDF et JSON figée à la clôture, `LISEZMOI.txt` et `SHA256SUMS.txt`. Le zip est reproductible (horodatages fixes). L’empreinte SHA-256 est renvoyée dans `X-Content-SHA256` et reste identique tant que les écritures validées ne changent pas. Les écritures `CENTRALIZATION` sont omises. Un ERROR du validateur interdit l’export. Cet export n’affirme pas que le contribuable est tenu de remettre un FEC.

## Contrat prévu

Le FEC provient exclusivement des écritures/lignes validées du ledger et d'un exercice clôturé. Il est déterministe : ordre chronologique stable, encodage et séparateur fixés, arrondi explicite, nom et empreinte reproductibles. L'exporteur produira les 18 champs réglementaires dans l'ordre (`JournalCode`, `JournalLib`, `EcritureNum`, `EcritureDate`, `CompteNum`, `CompteLib`, `CompAuxNum`, `CompAuxLib`, `PieceRef`, `PieceDate`, `EcritureLib`, `Debit`, `Credit`, `EcritureLet`, `DateLet`, `ValidDate`, `Montantdevise`, `Idevise`), sous réserve de confirmation du texte applicable.

## Validation

ERROR : champ obligatoire absent, format/date/montant invalide, numéro dupliqué incohérent, écriture déséquilibrée, compte/journal absent, date hors exercice, ordre non déterministe. WARNING : pièce faible, rupture chronologique, à-nouveaux/inventaire attendus absents. INFO : statistiques et empreinte. Un ERROR interdit le libellé « FEC valide ». Les conditions d'obligation et dispenses propres au contribuable ne seront pas déduites sans source.
