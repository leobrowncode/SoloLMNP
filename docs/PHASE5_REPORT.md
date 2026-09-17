# Phase 5 — premier lot : états provisoires par compte

## Périmètre

`GET /api/ledger/years/{year_id}/statements` et l’écran « États comptables »
produisent le résultat et un bilan par compte pour un exercice, uniquement à partir
des écritures VALIDATED. Les lectures partagent la transaction SQLite existante ;
aucune écriture, clôture, affectation de résultat ou donnée fiscale n’est créée.
Pas de nouveau modèle persistant ni de migration nécessaire.

Les montants sont additionnés en centimes entiers Python et rendus en chaînes
décimales ; le navigateur les affiche sans conversion en flottants. Le compte de
résultat présente produits et charges séparément. Le bilan distingue actif net,
dettes, capitaux propres et résultat de l’exercice. Les comptes d’amortissement
classés ASSET conservent leur solde négatif. Les comptes inactifs restent inclus.

Un déséquilibre du ledger ou du bilan bloque la réponse (409). Une incohérence
entre classe 6/7 et type EXPENSE/INCOME bloque également les états. Les autres
comptes suivent le type configuré dans le plan. L’interface efface les anciens
totaux lors d’une actualisation ou d’un changement d’exercice et ignore les
réponses tardives. Le nombre de brouillons exclus est visible.

## Source comptable

[PCG ANC consolidé au 1er janvier 2026](https://www.anc.gouv.fr/files/anc/files/1_Normes_fran%C3%A7aises/recueil/2026/PCG--1er-janvier-2026.pdf),
consulté le 17 septembre 2026 : articles 112-1 à 112-3, page 9.
Ces articles fondent l’établissement des comptes depuis les enregistrements et
l’inventaire, la distinction actif/passif/capitaux propres, la continuité du bilan
d’ouverture et la détermination du résultat par charges et produits indépendamment
des encaissements. Ce lot ne prétend pas satisfaire l’ensemble de ces exigences.

## Limites et suite de l’issue #6

Statut systématique PROVISIONAL, y compris pour un exercice verrouillé. Cet écran
est une projection technique par compte, pas un modèle réglementaire de comptes
annuels ni un mapping de liasse. Les soldes inhabituels sont signés, sans reclassement
automatique (ex. découvert bancaire). Le plan configurable doit être revu avant
une présentation réglementaire ; aucune compensation entre comptes n’est ajoutée.

Restent à livrer : écritures d’inventaire justifiées, génération idempotente des
à-nouveaux, contrôle de continuité et scénario complet de deuxième année,
présentation réglementaire et contrôles des reclassements. L’exercice suivant
est actuellement vide tant qu’aucune écriture n’y est enregistrée : l’isolement
testé ici ne vaut pas validation de continuité. L’issue #6 reste ouverte.

## Vérifications

Tests ajoutés : exercice vide/inconnu, produits à recevoir et charges non payées,
amortissement en diminution d’actif, résultat bénéficiaire/déficitaire, extourne,
brouillons exclus, isolation annuelle, compte personnalisé/inactif, centimes,
classement incohérent et blocage d’un ledger corrompu simulé en mémoire.
Tests UI : affichage d’une perte, erreur à l’actualisation sans anciens totaux,
réponse tardive d’un autre exercice et absence d’exercice.

Exécution locale du 17 septembre 2026 : 164 tests backend et 18 tests frontend
réussis, couverture backend 93 %. `pip check`, Ruff (lint et format), mypy,
ESLint, TypeScript et build Vite réussis. `npm ci` indique zéro vulnérabilité.
Les fixtures backend appliquent toutes les migrations sur des bases temporaires.
Docker et la CI distante ne sont pas validés par ces contrôles locaux.

## Correction de la CI et des réponses asynchrones (17 septembre 2026)

La CI du premier commit P5 a validé le backend Linux/Windows et Docker, mais
échoué sur le test de calcul des immobilisations. Le chargement initial des
périodes pouvait démarrer après un clic sur Calculer et invalider ce calcul.
L'abonnement aux périodes est désormais établi avant que les contrôles de
l'exercice rendu soient interactifs. Les lectures et calculs périmés ne peuvent
plus publier leur erreur ; changer d'exercice efface immédiatement les périodes,
les messages et le formulaire de comptabilisation de l'ancien exercice.

Six cas de test couvrent les réponses initiales tardives (succès/erreur), les
calculs de l'ancien exercice (succès/erreur), la fermeture du formulaire et
l'affichage d'une erreur courante. Quatre échouent sur l'ancien composant et les
six passent après correction. Suite frontend : 23 tests réussis ; ESLint,
TypeScript et build Vite réussis. Cette correction ne modifie ni les règles
comptables ni le schéma et ne termine pas P5.
