# Parcours SoloLMNP, novembre 2026

Audit de parcours, sans changement du produit. Il part de `main` au 5 novembre 2026 (dernière fusion : #130). L’authentification Neon Auth et l’hébergement Vercel sont déjà en production. Ce document ne propose pas de revenir à un mot de passe Argon2 local ni à une base SQLite par utilisateur.

## Méthode

Deux lancements, le 5 novembre 2026.

1. **Comme le README.** Ubuntu, Python 3.12, puis `python3 scripts/start_local.py`. Le lanceur crée `.env` depuis `.env.example`, migre SQLite et ouvre http://127.0.0.1:5173. Aucun secret Neon n’a été ajouté.
2. **Parcours métier en mode d’essai.** Le serveur du dépôt `e2e/serve.py` (`AUTH_MODE=test`) est le seul chemin qui ouvre le dossier sur cette machine, sans compte Neon. Dossier joué : activité « LMNP Mérignac », SIRET `12345678900019`, exercice du 06/04/2025 au 31/12/2025, bien Mérignac 1 (prix 145 000 €, frais 18 262 €, terrain 29 000 €, bâtiment 116 000 €), compte 512, emprunt Crédit Habitat 195 000 € à 3,25 % sur 240 mois, plan d’amortissement calculé. L’entrée du bien, la centralisation et la clôture de ce dossier complet n’ont pas été menées au bout : le formulaire d’entrée présente des montants qui ont l’air saisis alors qu’ils sont vides (P1-2). Un premier essai, avant le bien, a en revanche clôturé un exercice vide, téléchargé le FEC et restauré la sauvegarde.

La production https://sololmnp.vercel.app a été ouverte sur `/connexion` seulement. Aucun compte autorisé n’a été utilisé. Une tentative d’inscription avec une adresse hors liste a reçu « Cette adresse n’est pas autorisée. »

Docker n’a pas été exécuté : la commande `docker` est absente de la machine. Le fichier `docker-compose.yml` a été lu.

Captures dans `docs/archive/audit/2026-11/screenshots/`, en 1280 px et en 390 px pour les étapes clés. Chromium via Playwright. Axe-core sur les vues principales, à 1280 px et à 390 px : aucune violation. Aucun dépassement horizontal mesuré sur ces vues (`scrollWidth` égal à `clientWidth`). Aucun avertissement « same key » en console.

Les issues [#7](https://github.com/leobrowncode/SoloLMNP/issues/7) et [#11](https://github.com/leobrowncode/SoloLMNP/issues/11) restent ouvertes. Elles ne sont pas recréées ici. Les millésimes restent en Recherche.

## Installation

Frictions constatées en partant du README, sur une Ubuntu neuve.

| Étape | Constat |
| --- | --- |
| Python | `python3 -m venv` échoue : le paquet `python3.12-venv` n’est pas installé avec Python. Le README demande Python 3.12+, pas ce paquet. `scripts/start_local.py` s’arrête donc avant toute migration. |
| Node | Le README et `frontend/package.json` exigent Node 24 (`>=24 <25`). Avec Node 22.23.4 et npm 10.9.9, `npm ci` s’arrête : moteur refusé, et le lockfile est jugé incomplet (`ajv@8.20.0` manquant). Avec npm 11 (celui de Node 24), `npm ci` passe, avec des alertes de pairs sur `@neondatabase/auth` (`better-call`). |
| Lanceur | Une fois le venv et Node 24 en place, le lanceur migre, démarre l’API sur 127.0.0.1:8000 et Vite sur 127.0.0.1:5173, et copie `.env.example`. Les URL Neon et `ALLOWED_EMAILS` y sont vides. `AUTH_MODE` n’est pas passé à `test` (réservé aux essais, refusé en production). |
| Premier écran | Le navigateur arrive sur `/connexion`. Se connecter répond « L’authentification n’est pas configurée. » Le bouton Google est affiché et inactif. Le dossier est inaccessible. |
| Docker | Binaire absent ici, donc pas de `docker compose up`. D’après `docker-compose.yml`, le défaut est `AUTH_MODE=neon` et `APP_ENV=production`, avec des URL Neon vides. L’image frontend fige `VITE_NEON_AUTH_URL` au build (`Dockerfile.frontend`). Sans ces variables, le conteneur reproduit le même mur que le lanceur, en mode production. |
| Doc contre prod | Le README décrit encore d’abord le mode local SQLite et Docker. L’hébergement Vercel et Neon est un second chapitre. Un lecteur pressé croit ouvrir un logiciel local sans compte. Depuis les PR #123 à #130, ce n’est plus le cas. |

Ce mur est le P0. Il date de l’authentification Neon (#125), pas de l’enchaînement SIRET de la #118.

## Connexion

Prod, 1280 et 390 : `screenshots/1280-prod-connexion.png`, `screenshots/390-prod-connexion.png`.

L’écran est clair : titre, « Le dossier reste privé. Seules les adresses autorisées entrent. », e-mail, mot de passe, « Se connecter », « Créer un compte », « Continuer avec Google ». En 390 px la carte tient dans l’écran. Google est actif en production.

Frictions qui restent :

- « Créer un compte » est proposé à tout le monde. Après une inscription (nom, e-mail, mot de passe), l’API répond « Cette adresse n’est pas autorisée. » (`screenshots/1280-prod-inscription-reponse.png`). Le compte est tenté chez Neon avant le contrôle de `ALLOWED_EMAILS` (`LoginPage.tsx`, `signUpWithPassword` puis `GET /api/status`). L’adresse d’essai `ada.audit@example.com` a reçu ce refus : la retirer de Neon Auth si elle y a été créée.
- Le mot de passe exige 8 caractères (`minLength={8}`), sans phrase en français. Avec un navigateur en anglais, le message natif est « Please lengthen this text to 8 characters or more ». Les dates, elles, ont `lang="fr"` et un message français. `screenshots/1280-essai-mot-de-passe-court.png`.
- En local non configuré, le même formulaire s’affiche alors qu’aucune saisie ne peut aboutir. `screenshots/1280-local-connexion-non-configuree.png`, `screenshots/390-local-creer-compte.png`.
- Le mode d’essai (parcours ci-dessous) remplace Google par « Google n’est pas disponible dans le mode d’essai. » Un mot de passe faux dit « Adresse ou mot de passe refusé. » `screenshots/1280-essai-mot-de-passe-refuse.png`.

## Parcours en mode d’essai

### Vue d’ensemble vide

`screenshots/1280-vide-apercu.png`, `screenshots/390-vide-apercu.png`, menu `screenshots/390-vide-menu.png`.

Un seul lien « Continuer », hors de la barre du haut. Prochaine action : « Créer l’activité. » Statut « Incomplet », progression 0/6. En 390 px, statut et progression sont dans un repliable fermé « Statut et progression », et le titre est visible. Les aides sont des mots (LMNP, Liasse, FEC), plus des « ? ». Le correctif du 31 octobre tient.

Le menu numérote encore 1 Comptabilité, 2 Opérations, 3 Immobilisations, 4 États, 5 Fiscalité, 6 Conservation, avec « Dans l’ordre du menu. Une étape à la fois. » Ce n’est pas l’ordre réel depuis la #118 (voir P1-4).

Cibles sous 44 px sur cet écran : le logo (38 px), « Se déconnecter » (41 px), une aide (37 px). Axe ne les signale pas. Finition (P2).

### SIRET, exercice, bien, banque

Rail dans Comptabilité : 1 SIRET, 2 Exercice, 3 Bien, 4 Banque. `screenshots/1280-init-siret.png`.

Le SIRET `12345678900019` remplit le SIREN `123456789`, en lecture seule. Nom et date de début, puis « Enregistrer et continuer ». L’exercice est proposé du 06/04/2025 au 31/12/2025, millésime 2025, avec la phrase « Dates proposées à partir du début d’activité ». `screenshots/1280-init-exercice.png`. Des dates inversées donnent « La date de fin doit être postérieure ou égale à la date de début. » Après création, l’outil ouvre `/operations/biens#ajouter-bien`.

Le bien refusé tant que terrain + bâtiment ne vaut pas le prix. Les frais sont en plus, et le texte le dit. `screenshots/1280-bien-frais-en-plus.png`, `screenshots/1280-bien-ecart.png`. Surface du terrain facultative, prix au m² vide (le gris « 1 234,56 » est un exemple, pas une valeur). Masque de date vide : JJ/MM/AAAA. `screenshots/1280-bien-champs-requis.png`.

Bien créé : « Ajouter un compte bancaire ». `screenshots/1280-bien-cree.png`. Le bandeau « Exercice 2025 enregistré. Indiquez le logement. » est encore là alors que le logement existe (P1-4). Compte « Compte courant LMNP » sur le 512 ensuite. `screenshots/1280-banque-cree.png`.

**Perte de saisie.** Remplir le formulaire d’identité en 1280 px, puis passer à 390 px, efface le SIRET, le nom et la date. Revenir à 1280 px ne les rend pas. `screenshots/1280-saisie-avant-redimensionnement.png`, `screenshots/1280-saisie-apres-redimensionnement.png`. Cause : `MobileSection` (`frontend/src/lib/PageSection.tsx`) change de `div` à `details` sous 768 px, ce qui recrée le formulaire. P1-1.

### Emprunt

Carte « Crédit Habitat » : « Pas encore au bilan », pas un solde de 0,00 €. Le message envoie vers l’entrée du bien, sans proposer une échéance comme prochaine action. L’échéance ouverte refuse « Confirmer » et dit « Aucun capital comptable à rembourser pour cet emprunt. » `screenshots/1280-emprunt-pas-au-bilan.png`, `screenshots/1280-emprunt-echeance-bloquee.png`. Le correctif du 31 octobre tient.

La mensualité de contrat s’affiche 0,00 € : le champ « Mensualité contractuelle (€) » part de `0.00` et n’a pas été saisi. Informatif, mais on lit un prêt sans mensualité (P2).

### Import CSV

Sans banque, le collage de loyers « déjà payés » affiche « Choisissez le compte bancaire des lignes déjà payées. » « Prévisualiser » est inactif. Il n’y a pas de bouton « Comptabiliser ». `screenshots/1280-csv-sans-banque.png`. Le correctif tient : on ne passe plus une ligne en silence.

Avec banque, des dates de mars 2025 sont refusées parce que l’exercice commence le 06/04/2025. Le retour est en phrases : « 2 lignes : 0 valides, 2 rejets », date hors exercice, date `99/99/2025` invalide, et « Aucune ligne valide. Corrigez le fichier avant de comptabiliser. » `screenshots/1280-fail-csv-partiel-puis-valide.png`. Le cas « une ligne valide, une rejetée » des justificatifs n’a pas été rejoué jusqu’au bouton (les deux lignes tombaient hors exercice).

Relevé bancaire : une ligne `abc` est rejetée, deux lignes restent valides, et le texte dit « Les lignes valides peuvent être importées. » `screenshots/1280-releve-apercu.png`. L’import de relevé autorise donc encore un envoi partiel, annoncé, là où les justificatifs le refusent (P2).

### Immobilisations

L’aperçu puis la création n’affichent qu’une fois la durée d’usage commune (compte mesuré : 1). Le correctif tient. « Comptabiliser toutes les dotations » reste inactif tant que le bien n’est pas au journal, avec le lien « Faire entrer le bien en comptabilité » et la phrase « le brut du registre n’est pas au journal ». `screenshots/1280-immobilisations-dotations-bloquees.png`. Le correctif du 31 octobre tient : on ne passe plus les dotations sans l’entrée.

Le formulaire d’entrée montre « 1 234,56 » dans le solde de banque, les intérêts, l’assurance et les frais. Ce sont des `placeholder`, les valeurs sont vides. On croit le formulaire déjà rempli. « Comptabiliser » n’a pas été activé sans vrais montants. `screenshots/1280-entree-apercu.png`. P1-2. Le parcours s’arrête ici pour le dossier complet.

### États, fiscalité, conservation

États vus avant centralisation d’un dossier complet : exercice, à-nouveaux, centralisation, beaucoup de vocabulaire (120, 129, FEC). `screenshots/1280-etats-avant.png`, `screenshots/390-mobile-etats.png`. Le résultat après centralisation (correctif du 31 octobre) n’a pas été rejoué sur un journal complet.

Fiscalité : bandeau Recherche, « Ce n’est pas une base de déclaration. » Quand les périodes sont calculées mais non comptabilisées, le pré-contrôle le dit et « Accuser et préparer la clôture » reste inactif (`CloseYear.tsx` traite cela comme une erreur, `role="alert"`, pas comme une case). `screenshots/1280-precontrole.png`. Le correctif tient sur ce point.

Un exercice sans bien et sans écriture, lui, se clôture après les cases de recherche. FEC téléchargé : `123456789FEC20251231.txt`. La liasse, le PDF et le FEC sont marqués Recherche, pas Finale. « Même statut pour le calcul, la liasse et les exports. » `screenshots/1280-cloture-sans-logement.png`, `screenshots/1280-liasse.png`. Le décalage FEC « Finale » / liasse « Bloquée » du 31 octobre n’est pas revenu. Clôturer un exercice vide reste possible (P1-5).

Conservation : sauvegarde, contrôle, saisie `RESTAURER`, restauration annoncée (« 0 écritures, 1 exercices » sur ce dossier vide). `screenshots/1280-conservation.png`, `screenshots/1280-sauvegarde.png`, `screenshots/1280-restauration.png`. Le blocage `documents/.gitkeep` du 31 octobre n’est pas revenu.

En 390 px, fiscalité et états passent en colonne, titre visible, menu repliable. Pas de tableau plus large que l’écran sur les vues mesurées. Les pastilles d’aide s’empilent (P2). `screenshots/390-mobile-fiscal.png`.

## Correctifs du 31 octobre

| Correctif (PR) | Rejeu | Tient |
| --- | --- | --- |
| Restauration malgré `documents/.gitkeep` (#108) | Sauvegarde puis `RESTAURER` | Oui |
| Clôture sans le bien au bilan (#109) | Dotations refusées sans entrée ; pré-contrôle bloque ensuite | Oui sur ce chemin. Non rejoué après une entrée réussie. |
| Résultat des états après centralisation (#110) | Centralisation d’un dossier complet non faite | Non revu |
| FEC aligné sur la liasse (#111) | Exercice vide clôturé : FEC en Recherche, comme la liasse | Oui |
| Import CSV partiel (#112) | Sans banque, pas de comptabilisation. Rejets écrits en phrases. | Oui pour ces cas. Le relevé, lui, propose encore d’importer les lignes valides. |
| Emprunt non comptabilisé (#113) | « Pas encore au bilan », confirmation d’échéance inactive | Oui |
| Surface de terrain (#114) | Champ facultatif, non bloquant | Oui |
| Statut regroupé, un seul Continuer (#115) | Une action, repliable en 390 px | Oui |
| Justification des composants une fois (#116) | Une seule phrase de durée | Oui |
| Finitions P2 (#117) | Masque JJ/MM/AAAA à vide, aides nommées | Oui pour ces points. Le placeholder monétaire « 1 234,56 » prête encore à confusion. |

Aucune régression constatée sur ces correctifs. Le trou nouveau est ailleurs : le premier lancement documenté ne passe plus la connexion (#125).

## Écrans

| Écran | Compréhension | Ordre | Charge | Erreurs | Mobile | Accessibilité |
| --- | --- | --- | --- | --- | --- | --- |
| Connexion | Claire en prod. En local, le refus n’explique pas quoi configurer. | « Créer un compte » a l’air d’être l’étape, puis la liste d’adresses refuse. | Peu de champs. Le minimum de 8 caractères n’est pas écrit. | Messages courts et justes, sauf le message natif anglais du mot de passe trop court. | Carte lisible en 390 px. | Champs étiquetés. Focus visible. Axe muet. |
| Vue d’ensemble | La prochaine action est la bonne (« Créer l’activité »). | Le menu 1 à 6 promet un autre ordre que le rail SIRET, exercice, bien, banque. | Une zone d’action, cartes d’étapes. Mieux qu’en octobre. | Vide utile. | Titre visible, statut replié. | Aides nommées. Quelques cibles sous 44 px. |
| Initialisation | SIRET, SIREN, exercice proposé : un non-comptable suit. | Le rail est le bon ordre. La phrase d’intro oublie la banque (« puis le logement »). | Nom, date, SIRET. Correct. | Dates inversées expliquées. | Passer sous 768 px efface la saisie. | `aria-current` sur le rail. |
| Biens | Prix, terrain, bâtiment, frais « en plus » : la règle est dite. | Après le bien, le bouton propose la banque. Le bandeau demande encore le logement. | Surface et prix au m² facultatifs. Le gris « 1 234,56 » ressemble à un montant. | L’écart de prix est une phrase, avant l’enregistrement. | À voir sans redimensionner en cours de saisie (sinon perte). | Libellés présents. |
| Banque | « Ajoutez un compte 512 avant d’importer un relevé. » | Après le bien, comme le rail. | Un nom et un compte. Léger. | Revue avant confirmation. | `screenshots/390-mobile-banque.png`, pas de débordement. | Correct. |
| Emprunts | « Pas encore au bilan » se comprend. L’entrée du bien est le prochain pas. | Cohérent avec un prêt antérieur à l’exercice. | Mensualité à 0,00 € par défaut, marquée informative. | Échéance impossible : bouton inactif et phrase. | `screenshots/390-mobile-emprunts.png`. | Correct. |
| Transactions | L’import explique les colonnes. Les rejets sont des phrases. | Loyers après bien et banque : le texte le dit. | Feuille CSV large, mais les erreurs ne sont plus un tableau illisible. | Dates hors exercice bien expliquées. | `screenshots/390-mobile-transactions.png`. | Correct. |
| Immobilisations | Entrée puis dotations : l’ordre est écrit. | Le bouton de dotation pointe vers l’entrée. | Le formulaire d’entrée a l’air prérempli. | Blocage explicite si le bien n’est pas au journal. | `screenshots/390-mobile-immobilisations.png`. | Une justification, pas six. |
| États | On voit où centraliser, et que le FEC est ailleurs. | À-nouveaux et centralisation sur le même écran, tôt dans le menu (étape 4) alors que le journal est encore vide. | Vocabulaire 120, 129, à-nouveaux. | Non revu sur un dossier centralisé. | Cartes d’ancres, pas de débordement. | Axe muet. |
| Fiscalité | Recherche et « pas une base de déclaration » sont répétés, à raison. | Calcul, pré-contrôle, clôture : l’ordre est écrit. | Pastilles d’aide nombreuses. Cases 2033 citées pour la recopie. | Erreur de dotations non contournable par une case. Un exercice vide, si. | Titre et menu corrects. Pastilles empilées. | Axe muet. Erreurs en `role="alert"`. |
| Conservation | Sauvegarde puis restauration confirmée par le mot `RESTAURER`. | En fin de menu, ce qui convient. | Peu de champs. | La restauration de l’essai a abouti. | `screenshots/390-mobile-conservation.png`. | Correct. |

## P0

### P0-1. Le démarrage du README et de Docker n’ouvre plus le dossier

Depuis Neon Auth (#125), toute l’API sauf `GET /api/health` exige un JWT. Le lanceur local copie un `.env` sans URL Neon et sans `ALLOWED_EMAILS`. La page de connexion affiche quand même le formulaire. L’envoi répond « L’authentification n’est pas configurée. » (`LoginPage.tsx`, branche `!neonAuthConfigured()`). Google est visible et désactivé. Docker vise le même mur : `AUTH_MODE` vaut `neon` par défaut, `APP_ENV` vaut `production`, et l’URL d’auth est figée dans l’image frontend.

Un nouvel utilisateur qui suit le README ou `docker compose up` ne crée pas de dossier. Ce n’est pas un retour en arrière souhaitable vers Argon2 ou une base par utilisateur : l’auth de production (Google, e-mail, `ALLOWED_EMAILS`, `/connexion`) est le bon modèle. Le trou est le premier écran et la doc, qui parlent encore d’un logiciel local sans compte.

**Régression.** Oui, de la #125 (auth et isolation). Pas de la #118.

**Captures.** `screenshots/1280-local-premier-ecran.png`, `screenshots/1280-local-connexion-non-configuree.png`, `screenshots/390-local-connexion-non-configuree.png`. Prod, pour comparer : `screenshots/1280-prod-connexion.png`.

**Correction proposée.** Si Neon n’est pas configuré, remplacer le formulaire par une explication : où mettre `NEON_AUTH_BASE_URL`, `VITE_NEON_AUTH_URL` et `ALLOWED_EMAILS`, avec un lien vers `docs/DEPLOYMENT.md`, et dire que l’instance hébergée est https://sololmnp.vercel.app. Aligner le README et la section Docker sur ce préalable. Ne pas réintroduire de compte local Argon2.

## P1

### P1-1. Changer la largeur efface la saisie en cours

Sous 768 px, `MobileSection` passe d’un `div` à un `details`. React détruit et recrée les enfants. Le formulaire d’identité (SIRET contrôlé, nom et date non contrôlés) revient vide. Cela arrive en tournant une tablette, ou en rétrécissant la fenêtre au milieu de la première étape.

**Captures.** `screenshots/1280-saisie-avant-redimensionnement.png`, `screenshots/1280-saisie-apres-redimensionnement.png`.

**Cause.** `frontend/src/lib/PageSection.tsx`, les deux `return` selon `useMediaQuery(MOBILE_QUERY)`.

**Correction.** Garder le même élément, et seulement replier. Ne pas changer le type de nœud au passage du seuil.

### P1-2. « 1 234,56 » ressemble à un montant déjà saisi

Sur l’entrée du bien, solde de banque, intérêts, assurance et frais montrent `placeholder="1 234,56"` alors que la valeur est vide. Le capital restant dû, lui, est un vrai montant. On ne distingue pas les deux. « Comptabiliser » ne s’active pas tant que les vides ne sont pas remplis, donc le dossier complet s’arrête là sans message du type « ces cases sont des exemples ».

Le prix au m² du bien a le même gris, mais le libellé dit « facultatif ».

**Capture.** `screenshots/1280-entree-apercu.png`.

**Cause.** `frontend/src/features/PropertyEntry.tsx`, attribut `placeholder` sur les champs `data-money`.

**Correction.** Placeholder « 0,00 » ou aucun, et une phrase « à remplir, rien n’est proposé ». Ne pas utiliser un montant qui pourrait être vrai.

### P1-3. « Créer un compte » puis refus de la liste

En production, le bouton est au même niveau que la connexion. L’inscription aboutit chez Neon, puis `/api/status` répond 403 et l’écran dit « Cette adresse n’est pas autorisée. » Rien ne prévient que seules quelques adresses entreront, ni que le compte peut déjà exister côté auth.

**Captures.** `screenshots/1280-prod-creer-compte.png`, `screenshots/1280-prod-inscription-reponse.png`, `screenshots/390-prod-connexion.png`.

**Cause.** `frontend/src/features/LoginPage.tsx` : `signUpWithPassword` avant `admit`.

**Correction.** Expliquer la liste avant l’inscription. Si l’adresse n’est pas autorisée, ne pas créer le compte. Ajouter en français « 8 caractères minimum » (ou la règle réelle de Neon) au lieu du seul message du navigateur.

### P1-4. Le menu 1 à 6 ne suit pas le rail, et un bandeau reste en retard

Le menu dit de faire la comptabilité d’abord. Le travail réel, depuis la #118, est SIRET, exercice, bien, banque, puis seulement les écritures. La phrase du rail s’arrête au logement et oublie la banque. Après la création du bien, le bandeau dit encore « Indiquez le logement. »

**Captures.** `screenshots/1280-vide-apercu.png`, `screenshots/1280-init-siret.png`, `screenshots/1280-bien-cree.png`.

**Cause.** `frontend/src/routing/paths.ts` (`navItems` étapes 1 à 6) et l’état de navigation `guideNote`, qui ne s’efface pas quand le bien existe. Texte du rail dans `SetupGuide.tsx`.

**Correction.** Une seule suite d’étapes, celle du rail, avec un état fait / à faire. Effacer le bandeau dès que le logement est enregistré. Compléter la phrase jusqu’à la banque.

### P1-5. Un exercice sans rien se clôture

Sans bien et sans écriture, les cases de recherche suffisent à clôturer. Le FEC part, marqué Recherche, ce qui est honnête. L’outil a tout de même l’air d’avoir fini un dossier. Dès que des dotations sont calculées sans entrée au journal, le pré-contrôle bloque : ce second cas est sain.

**Captures.** `screenshots/1280-cloture-sans-logement.png`, `screenshots/1280-liasse.png`. Blocage sain : `screenshots/1280-precontrole.png`.

**Cause.** Le pré-contrôle n’exige pas un logement ni une écriture. Il exige de ne pas avoir de dotations orphelines.

**Correction.** Refuser la clôture, ou la présenter comme « exercice vide », tant qu’il n’y a ni bien ni écriture. Ne pas changer le calcul fiscal.

## P2

| Point | Constat | Capture | Correction |
| --- | --- | --- | --- |
| Relevé partiel | Une ligne rejetée, et le texte propose d’importer les valides. Les justificatifs, eux, refusent. | `screenshots/1280-releve-apercu.png` | Même règle que les justificatifs : pas d’import tant qu’un rejet reste, ou un choix explicite déjà coché par l’utilisateur. |
| Mensualité à 0 | Le champ part de 0,00 € et la carte le montre comme la mensualité du contrat. | `screenshots/1280-emprunt-formulaire.png` | Laisser vide tant que ce n’est pas saisi. Le libellé dit déjà « informatif ». |
| Aides en pastilles | En 390 px, fiscalité empile une dizaine de pastilles avant le travail. | `screenshots/390-mobile-fiscal.png` | Les regrouper dans « Détail et aides », comme sur les immobilisations. |
| Cibles | Logo 38 px, déconnexion 41 px, aide 37 px. | `screenshots/1280-vide-apercu.png` | 44 px sur les contrôles fréquents, lors de la refonte. |
| Intro du rail | « puis le logement » alors que l’étape 4 est la banque. | `screenshots/1280-init-siret.png` | Une phrase qui nomme les quatre étapes. |
| Brouillon | Chaque ligne exige un libellé en plus du libellé d’écriture. Le formulaire est long pour une note. | non retenu comme défaut de données | À revoir avec la refonte comptabilité, pas en correctif isolé. |
| États | Beaucoup de notions avant que le journal existe. | `screenshots/1280-etats-avant.png` | À traiter dans la refonte de la zone, pas maintenant. |

## Ce qui tient

- Enchaînement #118 : SIRET, SIREN dérivé, exercice proposé, bien, puis banque.
- Correctifs du 31 octobre listés plus haut, sur les chemins rejoués.
- Rejets CSV en phrases, dates hors exercice comprises.
- Entrée du bien distinguée du déblocage quand le prêt est antérieur à l’exercice.
- Axe sans violation sur les vues principales, pas de défilement horizontal à 390 px sur ces vues.
- Statut Recherche conservé. Rien n’affiche « Prête à recopier ».
- Issues #7 et #11 non dupliquées.

## Parcours cible

De l’installation au dépôt, pour un loueur qui n’est pas comptable. L’auth reste Neon (Google ou e-mail, liste `ALLOWED_EMAILS`, page `/connexion`). Pas de second système de compte.

1. **Arrivée.** Soit l’instance hébergée, soit une installation dont l’écran dit clairement qu’il faut les variables Neon. Pas un formulaire mort.
2. **Connexion.** Google ou e-mail. Si l’adresse n’est pas sur la liste, le dire avant de créer quoi que ce soit.
3. **Ce que fait SoloLMNP.** Une phrase : LMNP au réel simplifié, pas de télétransmission, millésime en recherche tant qu’il n’est pas attesté. Puis une seule prochaine action.
4. **Identité.** SIRET, SIREN, nom, début d’activité. L’exercice se propose. On peut rétrécir la fenêtre sans perdre la saisie.
5. **Logement.** Prix, frais en plus, terrain et bâtiment égaux au prix. Surface facultative.
6. **Banque.** Un compte 512.
7. **Emprunt**, s’il y en a un, puis **entrée du bien** avec des cases vides visibles comme vides. Ensuite seulement les échéances et les dotations.
8. **Loyers et charges**, à la main ou en CSV, dates dans l’exercice, pas d’import partiel silencieux.
9. **États**, quand il y a des écritures. Résultat lisible après centralisation.
10. **Fiscalité.** Calcul en recherche, pré-contrôle, clôture seulement si le dossier n’est pas vide et si le bien est au journal.
11. **Recopie.** Liasse et 2042-C-PRO à la main, FEC et dossier de contrôle au même statut. Conservation.

Les étapes 1 à 6 du menu actuel ne sont pas cette suite. Le rail SIRET, exercice, bien, banque en est le début, déjà en place.

Hors de cette suite, et hors de ce chantier : [#7](https://github.com/leobrowncode/SoloLMNP/issues/7) (moteur encore en recherche, cession, TVA, plus-values) et [#11](https://github.com/leobrowncode/SoloLMNP/issues/11) (feuille EFI et 2042-C-PRO à tenir au fil des millésimes). On n’y touche pas pour « finir le parcours ».

## Liste ordonnée de PR

À relire avant d’en coder une autre. Une PR, un sujet. Pas de `codex-automerge` sans accord.

1. **Cet audit** (documentation seule).
2. **P0, premier écran.** Connexion explicite quand Neon n’est pas configuré. README et Docker alignés sur l’auth déjà en production. Pas de réécriture Argon2, pas de base par utilisateur.
3. **P1-1.** Ne plus perdre la saisie au changement de largeur.
4. **P1-2 et P1-4.** Montants exemples qui ne ressemblent plus à une saisie. Bandeau d’étape à jour. Menu aligné sur le rail réel (peut attendre la PR de coquille si le correctif de bandeau part seul).
5. **P1-3.** Inscription et liste d’adresses : prévenir, ne pas créer un compte qui sera refusé. Aide française sur le mot de passe.
6. **P1-5.** Clôture d’un exercice vide, sans toucher au calcul.
7. **Fondation visuelle**, sans changer l’aspect : Tailwind CSS v4 (plugin Vite) et shadcn/ui, en gardant `frontend/src/tokens.css` comme source. `contrast.test.ts` reste vert, clair et sombre. Documenter dans `docs/DESIGN.md`. Si la compatibilité React 19 / Vite 8 bloque, le dire dans ce document et choisir l’alternative là, pas dans une nouvelle palette.
8. **Coquille et navigation.** Une barre, les étapes du parcours cible avec leur état, en-tête léger. L’accueil s’appuie sur le rail déjà livré par la #118 et sur la connexion Neon déjà livrée, sans les refaire.
9. **Vue d’ensemble.** Une carte « prochaine action », indicateurs de l’exercice, alertes actionnables.
10. **Opérations.** Biens, banque, emprunts, transactions, imports.
11. **Comptabilité.** Brouillons, journal, grand livre, balance, plan, inventaire.
12. **Immobilisations, états, fiscalité, conservation.**
13. **P2 restants** au fil de ces zones (relevé partiel, mensualité vide, pastilles, cibles de 44 px).
14. **#7 et #11** seulement dans leurs issues, avec une source et un test, jamais dans une PR de parcours.

Chaque PR visuelle : captures 1280 et 390, avant et après. Les tests dorés fiscaux ne bougent pas.
