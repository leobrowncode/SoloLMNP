# Premier exercice partiel, emprunt, six composants

Dossier fictif. SIRET `12345678900017` n'est pas un numéro attribué. Exercice du 01/07/2025 au 31/12/2025 (184 jours). Millésime de cases : 2025, registre `fiscal/2025/forms/`.

## Hypothèses

- Prix : terrain 40 000,00 EUR non amortissable (compte 211), bâtiment 160 000,00 EUR, mobilier 2 400,00 EUR (compte 218400, 84 mois). Frais de notaire : 0, pour ne pas mélanger une clé de répartition des frais avec la ventilation.
- Ventilation du bâtiment : grille déjà dans `backend/app/services/assets.py` (`DWELLING_PARTS`), en dix-millièmes, reliquat sur le dernier poste. Ici les parts tombent juste : gros œuvre 40 % (64 000, 480 mois, 213/281300), toiture 10 % (16 000, 300 mois, 2135/281350), façade, électricité et plomberie 10 % chacun (16 000, 240 mois, 2135/281350), agencements 20 % (32 000, 180 mois, 2135/281350). Ce n'est pas un barème légal. La grille est modifiable dans un vrai dossier.
- Emprunt débloqué le 01/07/2025 (donc en cours d'exercice, pas en capital restant dû d'ouverture) : 150 000,00 EUR. Six échéances, capital 200,00, intérêts 500,00, assurance 50,00. Le tableau est saisi, pas recalculé par un taux.
- Apport de l'exploitant : 55 000,00 EUR au compte 108. Il solde l'acquisition (202 400,00) après le déblocage.
- Prorata : jours réels, arrondi moitié vers le haut sur le cumul, comme `calculate_year` (base x jours / durée totale du plan). La durée totale va de la mise en service à `add_months(début, durée) - 1 jour`.
- Les intérêts et l'assurance d'emprunt sont des autres charges. Ils réduisent le plafond 39 C. Ils ne sont pas une dotation.
- 5NA reçoit le résultat fiscal de l'exercice. Il n'y a pas de déficit antérieur.

## Dotations (centimes)

Jours d'usage : 184. Jours du plan entre parenthèses.

| Composant | Base | Jours du plan | Dotation |
| --- | --- | --- | --- |
| Gros œuvre | 6 400 000 | 14 610 | 80 602 |
| Toiture | 1 600 000 | 9 131 | 32 242 |
| Façade | 1 600 000 | 7 305 | 40 301 |
| Électricité | 1 600 000 | 7 305 | 40 301 |
| Plomberie | 1 600 000 | 7 305 | 40 301 |
| Agencements | 3 200 000 | 5 479 | 107 465 |
| Mobilier | 240 000 | 2 557 | 17 270 |
| Total | | | 358 482 |

Contrôle gros œuvre : 6 400 000 x 184 / 14 610 = 80 602,327, arrondi à 80 602.

## Fiscal

Produits (706) : 6 x 200 000 = 1 200 000.

Autres charges : copropriété 60 000, taxe foncière 50 000, assurance PNO 20 000, gestion 18 000, CFE 10 000, assurance emprunteur 6 x 5 000 = 30 000, intérêts 6 x 50 000 = 300 000. Total 488 000.

Plafond (BOI-BIC-AMT-20-40-10-20, II, 01/03/2017) : max(0, 1 200 000 - 488 000) = 712 000. La dotation 358 482 est en dessous : elle est déductible en entier. Rien à reporter.

Résultat comptable = 1 200 000 - 488 000 - 358 482 = 353 518.
Résultat fiscal = 353 518. Déficit créé = 0. L'amortissement ne crée pas le déficit.

## Banque et bilan

Banque : +15 000 000 (emprunt) + 5 500 000 (apport) - 20 240 000 (acquisition) + 1 200 000 (loyers) - 608 000 (charges, intérêts, assurance, capital) = 852 000.

Emprunt fin : 15 000 000 - 6 x 20 000 = 14 880 000.

Actif net : brut 20 240 000 - amortissements 358 482 + banque 852 000 = 20 733 518.
Passif : 108 pour 5 500 000 + résultat 353 518 + emprunt 14 880 000 = 20 733 518.

2033-C : terrain en 42x, gros œuvre en constructions (43x / 52x), les cinq autres composants en agencements (45x / 54x) car comptes 2135 et 28135, mobilier en autres (47x / 56x). Totaux 492 et 572 = brut acquis et dotation.

2033-B : 242 = 614 + 616 + 622 = 128 000. 244 = 635 = 60 000. 254 = 358 482. 294 = 300 000. 370 = 353 518. 2042-C-PRO case 5NA = 353 518 (CERFA 11222*28, revenus 2025, bénéfice réel cas général). 5NY = 0.

## Écarts

Pas d'oracle externe. Les cases reprennent le registre 2025 déjà lu sur les PDF archivés, pas une nouvelle lecture. Le regroupement 2135 en « agencements » est celui de `liasse.py`, à confirmer sur le formulaire si Léo veut une autre ligne.
