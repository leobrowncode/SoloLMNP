# Dépôt et saisie EFI

## Faisabilité confirmée le 15 septembre 2026

La DGFiP indique que les entreprises BIC relevant du régime simplifié peuvent
déclarer leurs résultats en ligne dans leur espace professionnel, en mode EFI.
La déclaration 2031 figure explicitement dans l'offre. La saisie manuelle EFI
constitue donc un workflow disponible pour le périmètre cible du projet.
Source : [DGFiP — Téléprocédures : EFI ou EDI](https://www.impots.gouv.fr/professionnel/teleprocedures-efi-ou-edi),
rubriques « Les services en ligne (mode EFI) » et « L'EDI : mode obligatoire au réel normal ».

La page DGFiP comparant les régimes identifie, pour les BIC au réel simplifié,
la 2031/2031-bis et les tableaux 2033-A à 2033-G ; son tableau récapitulatif
confirme l'accès EFI. Cette liste décrit la famille de formulaires : elle ne
signifie pas que chaque tableau doive être renseigné dans toute situation.
Source : [DGFiP — Régime réel simplifié et régime réel normal](https://www.impots.gouv.fr/professionnel/questions/quelles-differences-y-t-il-entre-le-regime-simplifie-dimposition-et-le-reel),
rubrique « En matière de bénéfices », sous-rubrique « Régime réel simplifié ».

Ces deux sources ont été ouvertes et contrôlées le 15/09/2026. Aucun accès au
compte fiscal d'un contribuable et aucune soumission de déclaration n'ont été
effectués pendant cette vérification documentaire.

## Workflow cible

1. Centraliser les charges et produits sur les états comptables.
2. Calculer le résultat fiscal sur le ledger final. L’écran recharge le dernier calcul, avec sa date et l’empreinte du ledger. Une empreinte de ledger différente, ou une correction des hypothèses de calcul (bien, immobilisation, composant, emprunt), marque ce résultat obsolète. Un recalcul refusé ne le laisse pas affiché comme calcul en cours.
3. Lancer le pré-contrôle, accuser les avertissements, puis clôturer. La clôture fige le package.
4. Contrôler les écritures, calculs et formulaires figés.
5. Exporter le rapport et la feuille de saisie EFI. Chaque sortie affiche Provisoire, Bloquée ou Finale ; une sortie Bloquée ne se télécharge pas et indique le prérequis manquant.
6. L'utilisateur ouvre lui-même son espace professionnel impots.gouv.fr.
7. Il recopie les valeurs, contrôle puis valide lui-même la déclaration.
8. Il archive l'accusé fourni par le portail.

L'interface SoloLMNP affichera formulaire, case, libellé, montant et origine du
calcul. Les exports PDF/JSON/CSV servent à la préparation et à l'archivage.
Ils ne constituent pas une transmission fiscale officielle. SoloLMNP ne
télétransmet rien, ne pilote pas le portail et n'effectue aucun scraping.

## Millésime 2025 — avancement sources

Formulaires et notice 2031 / 2033 du millésime 2025 sont archivés avec URL, date de
consultation et empreinte dans `fiscal/2025/sources/`. Le registre des cases est
dans `fiscal/2025/forms/cases.yaml`. Les contrôles de cases peuvent être
satisfaits sans que la feuille soit déclarable. Le statut affiché (Recherche,
Provisoire ou Déclarable) vient de `fiscal/<millésime>/validation.json` et des
mêmes portes pour la clôture et les exports. Les conditions exactes sont dans
[FISCAL_RULES.md](FISCAL_RULES.md). Les millésimes 2025 et 2026 restent en
Recherche : une sortie Recherche n’affiche jamais « Prête à recopier ».

## Règles LMNP à l’impôt sur le revenu (notice 2033-NOT-SD 2025)

Relu sur le PDF archivé le 23 octobre 2026 :

- Ligne 360 du 2033-B (déficits antérieurs) : réservée à l’IS. Les cases 370/372 reprennent donc 352/354.
- 2033-D cadre II (déficits reportables, cases 860, 870, 982) : servi par les seules entreprises à l’IS. Il n’est plus émis.
- Les déficits LMNP antérieurs s’imputent sur la déclaration de revenus du foyer, pas sur la liasse. Sur le CERFA 11222*28 (2042-C-PRO, millésime 2026, revenus 2025), 5GA = 2015 et 5GJ = 2024. L’origine 2025 n’a pas de case sur ce formulaire. Ce n’est pas une fenêtre glissante « année − 10 ».
- Amortissement non déduit de l’exercice (art. 39 C) : réintégré ligne 318. Reprise d’années antérieures : déduite ligne 350 « divers », détaillée sur l’état de suivi joint à la feuille.
- 2033-B : case 018 « déposé au titre de l’IR » à cocher.
- 2031 cadre C : ligne 1 (370/372), ligne 4, ligne 7 « dont BIC non professionnels ». 2031-bis cadre I : « Autres locations meublées non professionnelles ».
- 2042-C-PRO, revenus 2025 : bénéfice ou 0 en 5NA, déficit en 5NY (cas général, déclarant 1). 5OA / 5PA / 5OY / 5PY existent et ne sont pas remplies : le déclarant du foyer n’est pas connu. 5NK est le micro-BIC (meublés de tourisme non classés), 5NZ n’est pas sur le formulaire : les deux sont bloquées. Source : CERFA 11222*28 archivé le 30/10/2026 (`fiscal/2025/sources/official/2042-c-pro_2026.pdf`, empreinte `293de292…993b`). Le montant servi est le résultat fiscal avant imputation des déficits antérieurs. Le registre (`carry_forward_event`) montre l’ouverture, l’imputé et le reste.
- Exercice 2026 : le formulaire 2042-C-PRO millésime 2027 n’est pas publié. Aucune case 5NA, 5NY, 5NK, 5NZ ou 5GA n’est reconduite. Les montants restent affichés, la case est bloquée.
- Exports d’archive : `GET /api/filing/years/{id}/efi.json` et `efi.csv`, même porte que le PDF (Provisoire, Bloquée, Finale). En-tête `X-Content-SHA256`. Le JSON et le CSV portent le marqueur « document de travail, à vérifier », le millésime, les empreintes de règles et de formulaires, et `declarable: false`. Ils entrent dans le zip du dossier de contrôle. Saisie manuelle uniquement : pas de scraping, pas d’EDI, pas de télétransmission.

Le calcul fiscal interne garde une imputation FIFO des déficits antérieurs : c’est une estimation au niveau du foyer, pas une ligne de la liasse.

## Premier exercice et achat antérieur

Un bien acheté avant le début de l’exercice entre en comptabilité par une écriture unique datée du premier jour de l’exercice (Immobilisations → « Faire entrer le bien en comptabilité ») : immobilisations du registre au débit, capital restant dû des emprunts au crédit, solde bancaire et frais payés avant le début (intérêts, assurance, frais de dossier) au débit, écart au compte de l’exploitant 108. Au 2033-C, ces biens figurent en augmentations du premier exercice.

## Hors de la feuille recopiable

- 2033-F et 2033-G : non applicables aux entreprises individuelles.
- 2033-D cadre II : réservé à l’IS.
- Millésime 2026 : formulaires de 2027 non publiés. Les numéros 2033 et 2042 ne sont pas présentés comme officiels (`case_publication: blocked`, `case_not_verified`).
- Cession, TVA, plus-values : la présence de ces opérations empêche la feuille d’être complète. Un millésime non validé reste Recherche même si la feuille est complète.
- La cotisation CVAE n’est pas calculée. La case 117 reste une base, nulle jusqu’à 152 500 € de chiffre d’affaires.
- L’accès à l’espace professionnel du contribuable n’est pas testé ici.

Confirmer l’accès EFI ne remplace pas le contrôle des montants par l’utilisateur avant validation sur impots.gouv.fr.
