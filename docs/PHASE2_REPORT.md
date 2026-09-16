# Phase 2 — Ledger persistant

## Périmètre livré

Comptes et journaux configurables, activité minimale et exercices, brouillons persistants,
validation atomique, numérotation par exercice, extourne, historique append-only,
journal filtrable et paginé, grand livre par compte et balance générale.
L'interface appelle ces API ; les montants restent des chaînes décimales en JSON et
des centimes entiers dans SQLite. Python manipule des Decimal ; les sommes des
projections utilisent des entiers exacts. Le navigateur utilise BigInt pour les totaux.

Migration `0002_ledger` après `0001_foundation`. Le plan initial est copié dans la
migration, pour ne pas dépendre des évolutions futures du code. Les données de phase 1
sont conservées. Une rétrogradation contenant des écritures ou événements est refusée.

## Invariants et décisions

- Deux lignes minimum, un seul côté strictement positif par ligne.
- Un brouillon peut être déséquilibré ; sa validation est alors refusée.
- Les brouillons n'alimentent aucun état comptable.
- Une validation attribue `YYYY-000001`, puis une séquence commune aux journaux de
  l'exercice. Cette séquence suit l'ordre de validation ; la consultation trie par
  date comptable, séquence, position. Les dates futures ne sont pas validables.
- `BEGIN IMMEDIATE` acquiert le verrou SQLite avant de lire les versions et la
  séquence. Les modifications de brouillons exigent leur version attendue.
- Répéter une validation retourne la même écriture sans la comptabiliser deux fois.
  La création de brouillon n'a pas encore de clé d'idempotence : après une panne
  réseau, consulter les brouillons avant de recréer une saisie.
- Écritures validées et leurs lignes immuables : service et triggers SQLite.
  Les libellés de compte et journal sont figés à la validation.
- Un exercice hors OPEN refuse la saisie et la validation. Le workflow métier
  de clôture/réouverture ne sera exposé qu'en phase 7.
- L'extourne crée et valide une nouvelle écriture inversée dans le même exercice
  ouvert, avec motif et lien vers l'original. Une seule extourne par original.
  Les comptes/journaux doivent être actifs ; les réactiver si nécessaire.
  Les corrections inter-exercices restent à traiter avec la continuité en phase 5.
- Le journal d'événements conserve créations, modifications, suppressions de
  brouillons et validations. Les identifiants supprimés ne sont pas réutilisés.

## Fondement comptable

Sources officielles ANC consultées le 16 septembre 2026 :

- [PCG au 1er janvier 2026](https://www.anc.gouv.fr/files/anc/files/1_Normes_fran%C3%A7aises/recueil/2026/PCG--1er-janvier-2026.pdf).
- [Plan de comptes 2026](https://www.anc.gouv.fr/files/anc/files/1_Normes_fran%C3%A7aises/Plans%20comptables/2026/Plan-de-comptes-2026.pdf).

| Référence | Exigence | Réalisation |
|---|---|---|
| Art. 1021-2 | Journal et grand livre | Projections des lignes persistées |
| Art. 1031-1 | Partie double | Égalité débit/crédit à la validation |
| Art. 1031-3 | Caractère définitif après validation | Immutabilité et extourne |
| Art. 1031-4 | Clôture et chronologie | Verrouillage défensif ; workflow futur |
| Art. 1032-1 et 1032-2 | Origine et pièce justificative | Référence et date obligatoires ; fichiers en phase 11 |

La numérotation, le choix du stockage et la stratégie de verrouillage sont des
décisions techniques, pas des règles fiscales. Le plan est un sous-ensemble
configurable : 706 « Prestations de services » n'est pas présenté comme un mapping
fiscal LMNP universel. Les subdivisions et affectations métier seront vérifiées
avant leur automatisation en phase 3.

## Vérification

Les tests couvrent le cycle brouillon/validation/extourne, les projections exactes,
les montants JSON invalides, les conflits de version, les validations concurrentes,
l'idempotence de validation, le verrouillage des exercices, les contournements SQL,
la conservation de l'audit, les filtres et le contrôle d'origine HTTP.
Les tests frontend couvrent la saisie de chaînes décimales, les totaux exacts au-delà
de la précision des Number, la séparation saisie/validation et la balance.

## Limites explicites

L'onboarding reste minimal : aucun solde historique n'est inventé. Le journal AN
permet une saisie manuelle justifiée ; la reprise automatique et la continuité
inter-exercices restent en phase 5. Pas encore de recettes/dépenses métier, imports
bancaires, emprunts, immobilisations, bilan, résultat fiscal, FEC ou liasse.

Les triggers protègent les accès ordinaires et les erreurs de programmation ;
un administrateur capable de modifier le fichier SQLite ou son schéma reste capable
de contourner ces protections. Il faut protéger les fichiers et sauvegardes.

Les écritures HTTP exigent un en-tête spécifique et une origine autorisée.
Ce contrôle réduit le risque de requêtes provenant d'autres sites ; ce n'est pas
une authentification. Le service reste local ou privé, sans exposition publique.

