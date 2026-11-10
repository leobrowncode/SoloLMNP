# Amortissement plafonné et report 39 C

Dossier fictif, SIRET `12345678900025`. Exercice civil 2025 complet. Un seul composant, pour coller à l'exemple chiffré du BOFiP sans bruit de ventilation.

## Source

BOI-BIC-AMT-20-40-10-20 du 01/03/2017, II : loyers 2 500, autres charges 1 000, amortissements 3 050. Déductible : 1 500. Report : 1 550. Le résultat fiscal n'est pas un déficit. L'article 39 C, II du CGI ne limite pas la durée du report (ce n'est pas l'amortissement réputé différé supprimé). Le moteur `apply_lmnp` ne fait pas expirer ce stock.

## Construction de la base

Il faut une dotation 2025 d'exactement 305 000 centimes. Plan linéaire, mise en service le 01/01/2025, durée 120 mois, fin de plan le 31/12/2034. Jours du plan : 3 652. Jours 2025 : 365.

Base retenue : 3 051 670 centimes (30 516,67 EUR).
3 051 670 x 365 / 3 652 = 305 000,424, arrondi moitié vers le haut à 305 000.

Terrain : 0. Hypothèse isolée pour le plafond, pas un avis sur la valeur de terrain. Pas d'emprunt au bilan : les intérêts de l'exemple (40 000 centimes) sont une charge 661 saisie, le capital n'est pas au 164. Apport 108 = prix du bâtiment. Banque de fin = 250 000 - 60 000 - 40 000 = 150 000.

## Fiscal (centimes)

Produits 250 000. Autres charges 60 000 + 40 000 = 100 000. Plafond 150 000.
Dotation comptable 305 000. Déductible 150 000. Non déduit 155 000, stock de fin 155 000.
Résultat comptable = 250 000 - 100 000 - 305 000 = -155 000.
Résultat fiscal avant déficits = -155 000 + 155 000 (réintégration de la fraction non déductible) = 0.
Déficit fiscal créé = 0. Case 318 = 155 000. Cases 370 et 372 = 0. 5NA = 0 (résultat nul déclaré à 0, lecture du CERFA archivé). 5NY = 0.

## Bilan

Brut 3 051 670. Amortissements 305 000. Net 2 746 670. Banque 150 000. Actif net 2 896 670.
Capital 3 051 670 + résultat -155 000 = 2 896 670. Actif = passif.

## Écarts

Le BOFiP parle en euros ronds (3 050). La base du plan n'est pas 30 500,00 EUR, sinon la règle des jours (années bissextiles 2028 et 2032 dans les 3 652 jours) donnerait 304 833 centimes, pas 305 000. L'écart est documenté : on aligne la dotation sur l'exemple, pas la base sur 30 500,00.

Pas de second exercice ici : le report est le stock de fin. Son utilisation est dans le dossier `deficit-imputation` (stock 39 C de 2024 repris en 2025). Recoupement LMNP.ai : à faire par Léo.
