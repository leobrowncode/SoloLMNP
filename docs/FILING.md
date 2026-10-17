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

1. Clôturer l'exercice et calculer un package immuable.
2. Contrôler les écritures, calculs et formulaires.
3. Exporter le rapport et la feuille de saisie EFI.
4. L'utilisateur ouvre lui-même son espace professionnel impots.gouv.fr.
5. Il recopie les valeurs, contrôle puis valide lui-même la déclaration.
6. Il archive l'accusé fourni par le portail.

L'interface SoloLMNP affichera formulaire, case, libellé, montant et origine du
calcul. Les exports PDF/JSON/CSV servent à la préparation et à l'archivage.
Ils ne constituent pas une transmission fiscale officielle. SoloLMNP ne
télétransmet rien, ne pilote pas le portail et n'effectue aucun scraping.

## Millésime 2025 — avancement sources

Formulaires et notice 2031 / 2033 du millésime 2025 sont archivés avec URL, date de
consultation et empreinte dans `fiscal/2025/sources/`. Le registre des cases est
dans `fiscal/2025/forms/cases.yaml`. La liasse BIC 2025 est `ready` lorsque chaque
case émise est dans ce registre et que le package n’a ni erreur ni écart bloquant
(immobilisations, classement, effectifs, cession, TVA). Le millésime 2026 et la
2042-C-PRO restent non déclarables.

## Hors de la feuille recopiable

- 2033-F et 2033-G : non applicables aux entreprises individuelles.
- 2042-C-PRO : produit séparé, case non archivée.
- Millésime 2026 : formulaires non archivés.
- Cession, TVA, plus-values : la présence de ces opérations refuse `ready`.
- La cotisation CVAE n’est pas calculée. La case 117 reste une base, nulle jusqu’à 152 500 € de chiffre d’affaires.
- L’accès à l’espace professionnel du contribuable n’est pas testé ici.

Confirmer l’accès EFI ne remplace pas le contrôle des montants par l’utilisateur avant validation sur impots.gouv.fr.
