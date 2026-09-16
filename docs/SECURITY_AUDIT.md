# Audit de sécurité — fondations, 16 septembre 2026

## Protections implémentées

| Risque | Mesure actuelle | Vérification / limite |
|---|---|---|
| Exposition réseau sans authentification | Interface Compose liée à 127.0.0.1 ; API non publiée ; Vite loopback | Configuration relue ; smoke Docker CI réussi |
| Host/CORS | Hôtes explicites, aucun joker, CORS vide par défaut, proxy même origine | Tests Host malveillant et origines acceptées/refusées |
| Injection SQL | ORM/paramètres ; aucune entrée SQL fournie par l'utilisateur | Tests de persistance ; aucune API métier modifiable à cette phase |
| XSS | Échappement React, aucune insertion HTML brute ; CSP Nginx | Tests et revue ; headers Docker vérifiés par le smoke prévu |
| Privilèges conteneurs | Utilisateurs non root, racine readonly, cap_drop ALL, no-new-privileges | Smoke Docker distant réussi, UID contrôlés |
| Intégrité SQLite | FK, WAL, synchronous FULL, BEGIN explicite, migrations Alembic | Tests d'annulation de DML et DDL, FK, contraintes, downgrade/upgrade |
| Précision monétaire | Decimal fini au centime ; INTEGER avec contraintes de type et signe | Tests float/int/bool/NaN/infinis/sous-centimes et grande précision |
| Mutation d'écriture | Contrats frozen et lignes copiées en tuple ; validation retourne une valeur | Tests ; persistance et verrouillage métier réservés P2/P7 |
| Informations techniques | Disponibilité 503 sans SQL/chemin exposé ; docs API désactivées en production | Tests sur base corrompue et schéma incorrect |
| Fuite Git/image | Exclusion env, bases, pièces, exports, backups, dépendances et caches | Contrôle des fichiers suivis avant commit |
| Dépendances | Lockfiles, actions CI référencées par SHA, audits npm/pip-audit | Audits locaux : aucune vulnérabilité connue signalée |
| Fiabilité fiscale | Statut research_only, aucun moteur ni montant déclarable | Catalogue de scénarios uniquement ; règles à valider avant P6 |

## Risques résiduels et périmètre

- Une installation sans authentification doit rester privée. Le filtrage Host/CORS n'est pas une authentification ; l'écoute réseau constitue la barrière principale.
- L'application n'offre encore aucune API de mutation métier. Les contrôles d'origine des futures écritures, CSRF, limites de requêtes et audit seront ajoutés avec ces endpoints.
- Le propriétaire de la machine peut modifier directement SQLite. Les contraintes ne constituent ni chiffrement ni journal inviolable.
- Les statuts d'exercice sont définis mais leur workflow, les verrouillages d'exercice et l'audit append-only ne sont pas encore implémentés.
- Uploads, import bancaire, désérialisation, restauration et moteur de formules ne sont pas exposés. Leurs protections restent à implémenter avec les fonctionnalités.
- Les versions de paquets sont figées, mais les lockfiles Python ne contiennent pas encore les hashes de distributions. Les tags Docker restent mutables ; geler les digests lors d'une publication et organiser les mises à jour.
- Les contrôles backend Linux/Windows, frontend et Docker ont réussi dans la [CI #4](https://github.com/leobrowncode/SoloLMNP/actions/runs/35065201132). Cela ne remplace pas les futurs audits des fonctions métier.
- Deux avertissements de dépréciation upstream apparaissent dans les tests Starlette/httpx ; ils ne sont pas masqués.


## Contrôles P2

Les mutations exigent X-SoloLMNP-Request: 1 ; Origin doit correspondre à l’hôte demandé ou à une origine explicitement autorisée et Sec-Fetch-Site ne doit pas être cross-site. Les modèles refusent les champs inconnus et les montants JSON numériques. Les requêtes SQL sont paramétrées. BEGIN IMMEDIATE sérialise les écritures et les triggers interdisent les mutations des écritures validées. Ces contrôles ne remplacent pas la protection réseau et du fichier SQLite.

## Contrôles P3

Le CSV bancaire est limité à 1 Mo et 5 000 lignes, parsé sans exécution et sans utiliser de chemin fourni par l'utilisateur. L'en-tête, les dates, montants et références sont strictement contrôlés. Les empreintes détectent les réimports et conflits. Les identifiants idempotents empêchent la double comptabilisation après un retry. Les rapprochements et opérations sont aussi validés par des triggers SQLite. Les libellés importés restent des données non fiables rendues comme texte par React.

## Contrôles P4

Les actifs, composants et plans d'amortissement sont immuables. Des contraintes SQL
indépendantes de l'API interdisent une base terrain, le dépassement de base par les
composants et une période comptabilisée sans écriture OD conforme. La durée maximale de
200 ans borne les entrées pathologiques ; tous les montants restent des centimes entiers.
