# Déficit 2024, imputation en 2025

Dossier fictif, SIRET `12345678900033`. Deux exercices civils. Le millésime de cases servi est 2025 seulement : le formulaire 2042-C-PRO archivé (CERFA 11222*28, revenus 2025) a une case pour le déficit 2024 (5GJ). Il n'a pas de case pour un déficit né en 2025. L'année 2024 est donc prouvée par le ledger et le moteur, pas par des numéros de liasse 2025.

## Bien et dotations

Base 1 596 712 centimes, linéaire, 240 mois, mise en service le 01/01/2024, fin de plan le 31/12/2043, 7 305 jours.

2024 est bissextile (366 jours). 1 596 712 x 366 / 7 305 = 80 000,000 (pile). Dotation 80 000.
2025 : cumul au 31/12/2025 = arrondi(1 596 712 x 731 / 7 305) = 159 780. Dotation de l'année = 159 780 - 80 000 = 79 780.

## 2024, le déficit vient des charges

Produits 100 000. Autres charges (copropriété) 250 000. Dotation 80 000.
Plafond = max(0, 100 000 - 250 000) = 0. Dotation déductible 0. Non déduit 80 000.
Résultat comptable = 100 000 - 250 000 - 80 000 = -230 000.
Résultat fiscal = 100 000 - 250 000 = -150 000. Déficit LMNP créé : 150 000, reportable 10 ans sur la même activité (CGI art. 156, I, 1° ter). L'amortissement n'augmente pas ce déficit.

Apport 1 746 712 = prix 1 596 712 + 150 000 de trésorerie pour que la banque finisse à 0 (loyers 100 000, charge 250 000).
Actif net = 1 596 712 - 80 000 = 1 516 712.
Passif = compte 108 1 746 712 + résultat -230 000 = 1 516 712.

À l'ouverture 2025, le résultat est affecté au compte 108 (entreprise individuelle, pas de compte 120 laissé ouvert, sinon la case 136 mélangerait le déficit antérieur et le résultat de l'année). 108 d'ouverture = 1 746 712 - 230 000 = 1 516 712.
À-nouveaux : 213 au débit 1 596 712, 281300 au crédit 80 000, 108 au crédit 1 516 712. L'écriture est équilibrée. Ces soldes égalent la clôture 2024 après affectation.

## 2025, imputation

Produits 500 000. Autres charges 80 000. Dotation 79 780.
Plafond = 420 000. La dotation de l'année tient dedans (79 780). Il reste 340 220 de plafond.
Le stock 39 C de 2024 (80 000) est repris en entier (FIFO, un seul stock). Reste de plafond 260 220.
Résultat fiscal avant déficits = 500 000 - 80 000 - 79 780 - 80 000 = 260 220.
Le déficit 2024 (150 000) s'impute. Résultat fiscal après imputation = 110 220. Stock de déficit : 0. Stock 39 C : 0.
Résultat comptable = 500 000 - 80 000 - 79 780 = 340 220 (la reprise 39 C n'est pas une charge comptable).

Banque fin = 0 + 500 000 - 80 000 = 420 000.
Actif net = (1 596 712 - 159 780) + 420 000 = 1 856 932.
Passif = 108 1 516 712 + résultat 340 220 = 1 856 932.

## Cases 2025

2033-B case 254 = 79 780 (dotation comptable). Case 350 = 80 000 (amortissements non déduits des exercices antérieurs, art. 39 C). Case 370 = 260 220. La ligne 360 des déficits antérieurs de la liasse reste vide : en LMNP à l'IR ils vont sur la 2042-C-PRO (notice 2033-NOT-SD, et le registre `cases.yaml`).

2033-C : le bien est entré en 2024, donc colonne début (430 = 1 596 712, 520 = 80 000), dotation 522 = 79 780, fin 526 = 159 780.

2042-C-PRO, hypothèse à trancher par Léo : 5NA = 260 220, c'est le bénéfice avant imputation du déficit antérieur (même montant que la case 370). 5GJ = 150 000, stock d'ouverture du déficit 2024, avant imputation. Le résultat après imputation (110 220) n'est pas pré-soldé dans 5NA. C'est la lecture déjà codée dans `declaration.py` (« avant l'imputation estimée »). Si la notice veut le net dans 5NA et seulement la fraction imputée dans 5GJ, les cases changent et ce dossier doit être réaligné. Ce point n'a pas été recoupé avec LMNP.ai.

## 2024 sans numéros de cases

Aucun formulaire 2024 vérifié n'est archivé dans `fiscal/`. Le golden de 2024 ne contient donc pas de cases 2033. Servir les numéros 2025 sur les revenus 2024 serait une invention.
