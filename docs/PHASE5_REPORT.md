# Phase 5 — états provisoires et préparation des à-nouveaux

État courant : la génération et le contrôle technique des à-nouveaux décrits dans
la dernière section sont livrés. Les sections précédentes documentent les lots
successifs et leurs limites à leur date de livraison.

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

## Prévisualisation des à-nouveaux (17 septembre 2026)

Depuis « États comptables », sélectionner l’exercice destinataire puis cliquer
sur « Prévisualiser les à-nouveaux ». La route en lecture seule
`GET /api/ledger/years/{year_id}/opening-preview` recherche l’exercice de la même
activité se terminant exactement la veille de son ouverture. Aucun prédécesseur
contigu : réponse 409 explicite ; exercice destinataire inconnu : 404.

Les soldes non nuls des comptes de bilan validés sont repris en débit/crédit,
sans compensation entre comptes. Les comptes de charges et produits ne sont
pas repris. Leur résultat est présenté distinctement, sur une ligne sans numéro
de compte, et inclus dans les totaux de contrôle. Cette ligne n’est pas une
écriture comptabilisable : le compte de reprise et l’affectation restent à
déterminer. Les montants sont calculés en centimes entiers et affichés en chaînes.
La réponse reste PROVISIONAL même si le prédécesseur est clôturé.

Source : PCG ANC au 1er janvier 2026 (lien ci-dessus), articles 112-2 et 112-3,
page 9, consultés le 17 septembre 2026. Le diagnostic prépare la comparaison
avec le bilan précédent avant répartition ; il ne certifie pas la continuité.
Il n’applique pas encore les opérations de centralisation et d’affectation du
résultat décrites pour le compte 12 (article 1211-12, page 154).

Les alertes indiquent : exercice précédent non clôturé, brouillons exclus,
exercice destinataire non ouvert, écritures déjà présentes (brouillons compris),
comptes inactifs et compte de reprise du résultat à déterminer. Aucune alerte
ne déclenche de mutation. L’historique et l’exercice destinataire restent intacts.
Le bilan source utilise les mêmes contrôles bloquants de classement et d’équilibre
que les états. Aucun modèle persistant ou migration supplémentaire.

Le changement d’exercice et l’actualisation des états effacent la prévisualisation.
Les réponses tardives, succès comme erreurs, de l’ancien exercice sont ignorées.
Une nouvelle demande efface les anciens montants avant chargement.

Onze tests backend couvrent les soldes de bilan, amortissements, bénéfice/perte,
centimes et grands montants, extourne et comptes soldés, exercice absent ou non
contigu, comptes inactifs, écritures destinataires, états verrouillés et source
corrompue/mal classée. Quatre tests frontend couvrent le chargement à la demande,
l’échec sans anciens totaux, les réponses tardives et l’actualisation globale.

Ce lot prépare la génération idempotente des à-nouveaux. Il ne la réalise pas,
ne valide pas encore un scénario complet de deuxième année et ne termine pas P5.
L’issue #6 reste ouverte ; inventaire, génération, contrôle de continuité après
comptabilisation et présentation réglementaire restent nécessaires.

Validation de ce lot : suite initiale de 173 tests backend réussie, puis 11 tests
à-nouveaux réussis après ajout de deux régressions sur les cumuls dépassant la
limite de stockage d’une ligne. Les cumuls restent des entiers sans limite SQLite.
Les 27 tests frontend, Ruff (lint/format), mypy, pip check, ESLint, TypeScript
et le build Vite passent. La CI distante de ce nouveau commit reste à vérifier.

## Génération idempotente et contrôle de reprise (17 septembre 2026)

La CI du commit de prévisualisation `78280f9` est réussie sur Linux, Windows,
frontend et Docker : [exécution 35224917266](https://github.com/leobrowncode/SoloLMNP/actions/runs/35224917266).

`POST /api/ledger/years/{year_id}/opening` accepte `preview_token` (empreinte
renvoyée par la prévisualisation), `journal_code`, `piece_reference` et
`result_account` (null si résultat nul). Le service vérifie à nouveau les soldes
dans une transaction SQLite `BEGIN IMMEDIATE`, exige une source contiguë de la
même activité, CLOSED et sans brouillon, ainsi qu’une destination OPEN et vide.
Le journal doit être actif et de type OPENING, les comptes repris actifs.
La référence de pièce est obligatoire. Une prévisualisation périmée est refusée.

La reprise avant affectation utilise un compte de capitaux propres choisi
explicitement : subdivision 120 pour un bénéfice (hors 1209, acomptes sur
dividendes), 129 pour une perte. Aucun compte n’est créé automatiquement.
Source vérifiée le 17 septembre 2026 : PCG ANC 2026, article 112-2 page 9,
plan des comptes page 133 et article 1211-12 page 154 (lien ci-dessus).
Cette implémentation prépare le bilan d’ouverture avant affectation ; elle ne
réalise ni la centralisation des classes 6/7 dans l’exercice source, ni
l’affectation du résultat à l’exploitant. Ces opérations et leur articulation
avec la clôture devront être validées dans les lots suivants.

L’écriture est immédiatement validée à la date d’ouverture avec provenance
OPENING, identifiant de l’exercice source et événement OPENING_GENERATED qui
conserve les paramètres. Les comptes 6/7 ne sont pas repris. Une même demande
renvoie l’écriture existante, sans autre écriture ni événement, y compris après
des opérations courantes ou le verrouillage de la destination. Des paramètres
différents sont refusés. Une erreur annule toute la transaction. L’extourne
générique est interdite ; un futur parcours métier devra gérer les corrections.

Migration **0005_opening** : index unique partiel sur l’exercice destinataire
pour les écritures OPENING ; pas de nouvelle table. Appliquer `alembic upgrade
head` avant le démarrage. La rétrogradation conserve les données et refuse de
retirer cette protection si une reprise générée existe. Les bases de test
vérifient la migration, le retour 0004 → 0005 et la cohérence des métadonnées.
La limite actuelle est une seule écriture, au plus 100 comptes et un total
compatible avec le stockage entier SQLite ; un dépassement est refusé sans
troncature ni écriture partielle. Un solde entièrement nul ne génère rien.

`GET /api/ledger/years/{year_id}/opening-continuity` compare par compte la seule
écriture générée aux soldes source actuels, avec écarts signés, état de clôture
et empreinte de la source. Les opérations courantes de la destination n’entrent
pas dans cette comparaison. Ce diagnostic reste PROVISIONAL ; il ne certifie
pas les comptes et ne rapproche pas les reprises manuelles. Une source rouverte
ou modifiée est signalée et ne peut pas être régénérée silencieusement.

L’écran expose le formulaire de génération après prévisualisation et le contrôle
de continuité à la demande. Les blocages connus désactivent le formulaire ;
le serveur répète tous les contrôles. Les demandes simultanées sont protégées,
les réponses tardives d’un écran quitté ignorées, les anciens écarts effacés
avant chaque contrôle. Après comptabilisation, le reçu invite à actualiser les
états. Un échec réseau permet de réessayer la même demande sans double reprise.

Validation : 192 tests backend passent (couverture 94 %), puis les 19 tests
ciblés passent après ajout de deux tests de migration, soit 194 cas au total.
Les 37 tests frontend, Ruff lint/format, mypy, pip check, ESLint, TypeScript et
build Vite passent. Les tests de génération couvrent bénéfice/perte, amortissements,
centimes, concurrence, idempotence, blocages, rollback, source rouverte, unicité
SQL et migrations. Le règlement d’une créance reprise en deuxième année solde
le compte client sans nouveau produit, tout en préservant le diagnostic initial.

**Limite opérationnelle :** le parcours de clôture P7 n’existe pas encore ; le
formulaire reste donc bloqué pour les exercices OPEN actuels. Les tests utilisent
des sources clôturées fictives, sans ajouter de contournement dans l’API publique.
Ne pas modifier directement les données réelles pour simuler une clôture.
Inventaire justifié, présentation réglementaire, correction des reprises après
réouverture et parcours complet sur deux exercices restent à terminer.
L’issue #6 reste ouverte et aucun montant déclarable n’est produit.

## Intégration opérations, emprunts et dotations (17 septembre 2026)

La CI du commit `7229cfb` a réussi sur Linux, Windows, frontend et Docker :
[exécution 35232175984](https://github.com/leobrowncode/SoloLMNP/actions/runs/35232175984).

Un scénario intégré P3/P4/P5 a révélé un défaut : le calcul du capital restant
dû additionnait les mouvements de tous les exercices, y compris les à-nouveaux
générés. Un emprunt de 10 000 € apparaissait ainsi à 20 000 € après sa reprise,
et un remboursement de capital supérieur au montant réel était accepté.
Trois cas ont échoué sur le code précédent et passent après correction.

Le cumul historique des mouvements du capital exclut désormais uniquement les
écritures de provenance OPENING générées par l’application. Les soldes initiaux
manuels et les extournes restent inclus. Les états annuels continuent à inclure
les à-nouveaux de leur exercice. Cette correction de double comptage n’ajoute
aucune règle comptable ou fiscale, aucune migration ni modification de données.
Les reprises manuelles dupliquant un historique déjà importé restent hors de ce
contrôle : leur rapprochement nécessite un futur parcours d’import dédié.

Le test intégré utilise un exercice 2025 puis un exercice court du 1er au
31 janvier 2026, afin de vérifier les dotations sans valider une date future.
La source est clôturée par une fixture sur une base temporaire, car P7 reste à
livrer. Le scénario passe par les API métier pour le déblocage de l’emprunt,
les recettes/dépenses non réglées, leurs règlements en deuxième exercice,
l’échéance et les dotations du registre. Les valeurs attendues sont explicites :

| Contrôle | Valeur attendue |
|---|---:|
| Capital après à-nouveaux | 10 000,00 € |
| Résultat 2025 (900,25 − 100,15 − 120,92) | 679,18 € |
| Résultat 2026 après règlement des créances/dettes reprises | 0,00 € |
| Capital après échéance de 125 € dont 100 € de capital | 9 900,00 € |
| Dotation de janvier 2026 | 20,37 € |
| Résultat du second exercice (20 € intérêts + 5 € assurance + dotation) | −45,37 € |
| Total actif / passif du second exercice | 10 533,81 € |

Le test vérifie aussi les réessais idempotents, les opérations soldées, le bilan
équilibré, les états source inchangés et la continuité des soldes repris.
Deux régressions refusent des remboursements de capital de 10 000,01 € et
20 000 € sans écriture partielle. Un quatrième test préserve le capital saisi
manuellement et restaure son solde après extourne d’une échéance en année 2.

Le filtre `source` du journal accepte maintenant DEPRECIATION et OPENING.
L’interface remplace la saisie libre des codes par une liste française de toutes
les provenances disponibles. Un test UI vérifie les requêtes filtrées et le
retour à toutes les sources ; le scénario backend vérifie leur contenu et
l’isolement des exercices.

L’inventaire justifié, la présentation réglementaire, la centralisation et
l’affectation du résultat, la clôture/réouverture et le parcours utilisateur
complet restent à réaliser. Ce lot ne termine pas P5 et ne clôture pas #6.

Validation locale : 198 tests backend réussis, couverture 94 %, puis les quatre
tests ciblés réussis après nettoyage des imports. Les 38 tests frontend, Ruff
lint/format, mypy, ESLint, TypeScript et build Vite passent. La CI du nouveau
commit sera contrôlée après publication.
