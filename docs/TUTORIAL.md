# Tutoriel SoloLMNP — exercice 2026

Guide d’utilisation pour un LMNP au réel, location longue durée, y compris une colocation.
SoloLMNP prépare la liasse à recopier et le FEC. Il n’envoie rien
sur [impots.gouv.fr](https://www.impots.gouv.fr).

## Démarrer l’application

**Windows :** double-cliquer sur `SoloLMNP.bat` à la racine du dépôt.

**Linux / macOS :**

```sh
./scripts/start_local.sh
```

**Équivalent Python (tous systèmes) :**

```sh
python scripts/start_local.py
```

Prérequis : Python 3.12+ et Node.js 24 (avec `npm`). Au premier lancement, le
script crée l’environnement, installe les dépendances, migre la base et ouvre
[http://127.0.0.1:5173](http://127.0.0.1:5173). Les données restent dans `data/`.

Chaque étape du menu possède une adresse stable (`/comptabilite/brouillons`,
`/operations/biens`, `/fiscalite`, etc.) : vous pouvez recharger la page,
utiliser Précédent/Suivant du navigateur ou enregistrer un favori sans perdre
votre écran. Une saisie non enregistrée demande confirmation avant de quitter.

Sur un écran étroit (768 px et moins), le menu se replie. La page en cours
reste affichée : **Ouvrir le menu** montre toutes les étapes, **Replier le menu**
les range. La navigation n’est pas retirée. Les pages longues proposent des
ancres, et certaines sections se replient. Le journal, la balance, le plan
comptable, les dotations et les imports se lisent en cartes : les colonnes
principales restent visibles, les autres sous **Autres colonnes**. Entre 320 et
430 px, chaque liste déroulante répète en entier la valeur choisie sous le
champ. Au-dessus de 768 px, la disposition de bureau ne change pas.

Les pastilles **?** à côté d’un terme comptable ouvrent le glossaire : ce que c’est, pourquoi c’est demandé, un exemple et l’erreur fréquente. Clic, Entrée ou Espace ouvrent l’aide ; un second clic, Échap ou un clic à l’extérieur la ferment. Le texte reste dans l’écran, y compris sur un téléphone (320 px et plus). Une erreur peut proposer la même entrée. Le glossaire ne dit pas qu’une sortie est déclarable : les millésimes restent en recherche. SoloLMNP n’envoie rien aux impôts.

Une action métier désactivée (nouvelle recette, nouvelle dépense, immobilisation,
à-nouveaux, emprunt, règlement, dotation, clôture, etc.) nomme chaque prérequis
manquant et propose un lien vers l’écran qui le corrige. S’il y a plusieurs
causes, elles sont toutes listées. L’ordre du parcours ne change pas.

Si l’alerte « Stockage non sûr » apparaît, la base est dans OneDrive. Elle reste visible sur toutes les vues, même quand la base est prête. Copiez le projet hors de ce dossier synchronisé avant de saisir : la synchronisation peut corrompre SQLite.

Si un écran affiche une erreur de chargement, **Réessayer** relance la lecture. Ce n’est pas un dossier vide. Quand c’est sans risque, les informations déjà affichées restent, marquées comme pouvant être périmées. Les totaux des états comptables disparaissent plutôt que de montrer un chiffre incertain. Le **statut dossier** et **Stockage opérationnel** disparaissent aussi : une lecture ratée ne laisse pas l’indicateur précédent.

Le bandeau affiche le **statut dossier** : Incomplet, Bloqué, Prêt à vérifier ou Clôturé. Il est calculé sur l’exercice en cours (ou le dernier exercice s’ils sont tous clôturés) à partir de la clôture, du statut fiscal et de la posture des exports. Il ne dit jamais que le dossier est déclarable : les millésimes restent en recherche. **Stockage opérationnel** n’apparaît que dans **Diagnostic technique**, sur la vue d’ensemble. « Aucun envoi » est à côté des sorties fiscales (liasse, PDF, FEC), pas dans le bandeau.

La vue d’ensemble est le tableau de bord du dossier, pas une copie du menu. Le menu reste la navigation. Chaque étape (structure et SIREN, opérations, immobilisations et amortissements, à-nouveaux, clôture, fiscalité et exports) affiche **Terminé**, **À faire**, **En cours** ou **Bloqué**, avec une justification. Une clôture prête à confirmer affiche **Prête**. Les prérequis manquants reprennent les mêmes explications et liens que sur une action désactivée, et chaque blocage propose le lien qui le corrige. Le dernier événement utile est indiqué. **Continuer** ouvre la prochaine action, celle du premier prérequis réel : un à-nouveaux bloqué par l’exercice précédent passe avant le pré-contrôle.

Le bandeau reprend cette progression à côté du statut dossier, sur toutes les pages : le décompte des étapes terminées et **Continuer**. Le statut dossier reste affiché. Ces états viennent du serveur (`GET /api/dashboard`), pas d’une liste enregistrée dans le navigateur. Recharger la page ou ouvrir un autre navigateur donne le même résultat. Rien n’y est présenté comme déclarable : les millésimes restent en recherche. Les montants affichés sont des centimes convertis en euros, au format français (`1 234,56 €`). La saisie accepte `1 234,56` ou `1234,56`. Le calcul reste en centimes entiers. L’API reçoit toujours le décimal exact `1234.56`. Les dates affichées sont en JJ/MM/AAAA, et chaque champ date le rappelle. Les messages de validation sont en français. Le bouton de fichier dit « Choisir un fichier ».

Après un enregistrement, le message reste à côté du bouton ou de la ligne créée. Il nomme l’objet, l’action et l’heure, par exemple « Immobilisation “Appartement Lyon” créée à 15:42 ». La ligne est amenée à l’écran et surlignée, sans prendre le focus. S’il y a une suite utile, un lien ou un bouton la propose. Le message se ferme tout seul, ou avec **Fermer le message**. Il ne reste pas affiché en haut de la page.

Alternative Docker : voir [DEPLOYMENT.md](DEPLOYMENT.md).

Vérifier, sur la vue d’ensemble, que le statut dossier s’affiche, que la progression du bandeau indique le décompte et **Continuer**, et que le tableau de bord détaille chaque étape. Ouvrir une autre page du menu : le statut dossier et la progression restent, **Diagnostic technique** non. **Stockage opérationnel** n’est que dans ce diagnostic.

---

## 1. Comptabilité — initialiser

Menu **Comptabilité** :

1. **Créer l’activité** (nom + date de début réelle).
2. **Identité** : saisir le **SIREN** (et le SIRET). Sans SIREN, la liasse reste incomplète (statut Recherche ou Provisoire, jamais « Prête à recopier ») et le FEC ne s’exporte pas (son nom réglementaire commence par le SIREN).
3. **Ajouter un exercice 2026** (achat en 2026 : pas de liasse 2025). Millésime `2026`. Les numéros de cases viennent des formulaires 2025 archivés : vérifiez-les sur le formulaire en ligne au moment de déclarer en 2027.
4. (Optionnel) Onglet **Plan comptable** pour ajouter des comptes. Chaque ligne sépare la nature (Actif, Dette, Capitaux, Charge ou Produit) de l’utilisation (**Activé** ou **Inactif**). Actif est une nature de bilan : un emprunt activé reste une Dette. Le filtre et le formulaire proposent ces cinq natures. Désactiver un compte le retire des saisies sans changer sa nature. La pastille **?** « Nature du compte » rappelle la différence.

Pour une activité déjà existante : saisir des **à-nouveaux** justifiés. L’application
ne reconstitue pas l’historique.

---

## 2. Opérations & banque — setup métier

Menu **Opérations & banque**, dans cet ordre :

| Onglet | Action |
| --- | --- |
| **Biens** | Ajouter le bien (prix, terrain, bâtiment). **Modifier** corrige le nom, l’adresse et les notes. Le prix, le terrain et le bâtiment se figent dès qu’une immobilisation existe : la correction se fait alors sur le registre. |
| **Banque** | Ajouter un compte bancaire (lié à un compte 512). Le nom reste modifiable. Le numéro se fige dès qu’un mouvement ou une écriture l’utilise. |
| **Emprunts** | Si besoin : une ligne de crédit = un emprunt. Pour 15 000 € + 195 000 €, créez deux emprunts ; un compte 164 libre est attribué automatiquement et n’est plus modifié. Puis déblocage et échéances (saisie unitaire ou import du tableau d’amortissement). Le taux, la durée et le prêteur restent corrigeables ; le capital initial et la date de départ se figent dès qu’un mouvement existe. |
| **Transactions** | Recettes (loyers) et dépenses (charges) |

Pour chaque opération : date, bien, exercice, montant, compte 6xx/7xx.
Si le règlement a lieu le même jour → lier la banque ; sinon choisir « Non réglé »,
puis **Enregistrer un règlement** plus tard.

**Import CSV** (Banque, Emprunts, Transactions) :

- **Télécharger le modèle CSV** : en-têtes en français, deux lignes d’exemple, UTF-8 avec BOM, séparateur `;`, montants avec virgule (`800,00`), dates `JJ/MM/AAAA`.
- Banque : Date, Libellé, Montant, Référence. Transactions : Nature, Date, Date de la pièce, Type, Tiers, Montant, Libellé, Référence de pièce, Justificatif, Déjà payée. Emprunts : Prêt, Rang, Date, Date de débit, Capital, Intérêts, Assurance banque, Assurance externe, Autres frais, Total banque.
- Collez votre fichier ou chargez-le. Un export avec virgule, une tabulation (Google Sheets) ou des dates `AAAA-MM-JJ` sont lus aussi. Associez chaque colonne de votre fichier au champ attendu si les noms diffèrent.
- La prévisualisation distingue les lignes **valides**, les **doublons**, les **avertissements** et les **erreurs** avant toute écriture. Un rejet indique la ligne, la colonne, la valeur lue et la correction attendue. **Télécharger les lignes à corriger** produit un CSV à réparer puis à recharger.
- Seules les lignes valides, et les avertissements qui peuvent l’être, sont enregistrées. Une écriture déjà validée n’est pas réécrite : une référence identique avec un autre contenu est refusée.
- Banque : prévisualiser puis confirmer, puis **rapprocher** chaque mouvement. L’import seul ne comptabilise rien.
- Transactions : choisir le bien, l’exercice et le compte des lignes payées. Nature : Recette ou Dépense. Déjà payée = oui : opération réglée sur ce compte ; sinon elle reste **à régler**. Traitement fiscal à vérifier. Mise en forme du Sheet (listes déroulantes, dates, montants en €, doublons en rouge) : coller `scripts/gsheet/format_saisie.gs` dans Extensions > Apps Script, puis exécuter `setup` une fois. Les anciens en-têtes techniques (`kind`, `piece_date`, `counterparty`, `source_file`, …) restent reconnus.
- Emprunts : un seul prêt par fichier. Confirmez que la référence Prêt correspond à l’emprunt choisi. L’en-tête « Assurance externe à compléter » est reconnu. Une assurance externe non nulle n’entre pas dans le total banque : importez-la dans Transactions comme dépense `ASS`. Seules les échéances de l’exercice déjà arrivées à leur date sont comptabilisées. Le capital restant dû ou le déblocage doit exister.

---

## 3. Immobilisations

Menu **Immobilisations** :

1. **Prévisualiser l’amortissement du logement**, puis **Créer les immobilisations affichées**. L’aperçu liste le terrain, la construction et six composants (montants, comptes, durées, mise en service) sans rien enregistrer : ni immobilisation, ni compte. Annuler laisse la base inchangée. Répéter la confirmation ne crée pas de doublon. Les frais de notaire et d’agence sont ajoutés au bâtiment ; les durées proposées sont à confirmer, ce n’est pas un barème légal. Ou saisie manuelle : terrain (compte 211, sans amortissement), puis construction (213000 / 281300) et tous ses composants. Le formulaire ne propose que les comptes de la catégorie, jamais un compte 28 comme compte d’immobilisation.
2. **Faire entrer le bien en comptabilité** (une seule fois, premier exercice) : indiquez le capital restant dû de chaque prêt au début de l’exercice, le solde bancaire à cette date et les frais payés avant (intérêts, assurance emprunteur, frais de dossier). **Prévisualiser**, puis **Comptabiliser**. L’écart va au compte de l’exploitant (108). Les prêts repris ainsi n’ont pas de « déblocage » à saisir : enregistrez seulement les échéances payées pendant l’exercice. Une erreur se corrige en extournant l’écriture depuis le journal.
3. Mobilier : **Nouvelle immobilisation**, comptes 218400 et 281840, avec justification de valeur et de durée. Un couple déjà enregistré qui ne correspond pas à sa catégorie est signalé sur la fiche et n’est pas réécrit tout seul. **Modifier** (ou **Préciser la justification** si la fiche est figée) demande un motif. Avant toute dotation comptabilisée, la valeur, la durée et les comptes peuvent changer : les périodes seulement calculées sont alors effacées, il faut relancer **Calculer les périodes**. Après comptabilisation, ces champs restent affichés comme figés et l’écran dit pourquoi. La même action existe pour le bien, le locataire, la banque et l’emprunt.
4. Choisir l’exercice 2026 → **Calculer les périodes** → **Comptabiliser** une dotation, ou **Comptabiliser toutes les dotations**. Le bouton reste inactif jusqu’à la réponse et l’étape s’affiche. Le lot s’arrête à la première dotation refusée : les précédentes restent en comptabilité, l’écran recharge l’état réel. Un second clic ou une réponse perdue ne crée pas une seconde écriture (possible à partir du 31/12, date de la dotation).

---

## 4. Vérifier la comptabilité

Retour **Comptabilité** :

- Valider tous les **brouillons** (validation = numéro définitif, plus de modification).
- Contrôler **Journal**, **Balance** et **Grand livre**.
- Onglet **Inventaire** pour les écritures d’inventaire manuelles justifiées.

---

## 5. États comptables — centraliser

Menu **États comptables** :

1. Consulter bilan et résultat provisoires.
2. **Préparer la centralisation** → vérifier → confirmer. La préparation ne modifie pas le plan comptable. S’il n’existe aucun compte actif 120 (hors 1209) ou 129 selon le sens du résultat, la confirmation annonce et crée le compte manquant (120000 ou 129000) dans la même opération. Corriger ou quitter avant cette confirmation laisse le plan inchangé.
3. Puis **affectation** du résultat (120/129 → capitaux) si proposé.

Cette étape ne clôture pas l’exercice. La suite est dans **Fiscalité LMNP**.

---

## 6. Fiscalité, pré-contrôle, clôture et sorties figées

Menu **Fiscalité LMNP**, dans cet ordre :

Les pastilles **?** de cet écran reprennent le glossaire (plafond, déficit, amortissement, liasse, FEC, EFI). Le geste est le même que sur les autres écrans.

1. Sélectionner l’exercice. Le dernier calcul se recharge avec sa date et l’empreinte du ledger. Si cette empreinte n’est plus celle du ledger, ou si une correction de bien, d’immobilisation, de composant ou d’emprunt a changé un montant, une durée, une date ou un compte du calcul, le résultat est marqué **Obsolète** immédiatement. Il n’est plus le calcul en cours : le pré-contrôle le traite comme absent. Un libellé, un locataire ou une banque ne le rend pas obsolète. **Calculer le résultat fiscal** (après la centralisation, sur le ledger final) enregistre un nouveau calcul. Un recalcul refusé retire l’ancien résultat de l’écran : il n’est pas laissé comme calcul en cours.
2. **Lancer le pré-contrôle**. S’il manque le calcul, ou s’il ne correspond plus au ledger, le lien **Calculer le résultat fiscal** ramène au calcul. Cocher chaque avertissement affiché : un nouveau pré-contrôle décoche tout, et **Accuser et préparer** reste inactif tant qu’il en manque un. Puis **Confirmer la clôture**. Le statut de l’exercice, le tableau de bord et les sorties (liasse, FEC) se rechargent.
3. Après clôture, l’exercice est figé. Pour le corriger : **Réouvrir l’exercice** (motif d’au moins 10 caractères, confirmation `ROUVRIR`). Les calculs fiscaux et le snapshot liasse/FEC courants sont invalidés ; l’exercice redevient ouvert. Recalculez, relancez le pré-contrôle puis reclôturez pour regénérer les sorties figées.
4. **Liasse à recopier** : le statut **Recherche**, **Provisoire** ou **Déclarable** (le même que le calcul et que le pré-contrôle), points bloquants, avertissements avec leur niveau (information, avertissement ou erreur), consignes de saisie, puis les cases par formulaire (2031, 2031-bis, 2033-A, B, C, E), l’état de suivi des amortissements non déduits et les cases de la 2042-C-PRO. **Recherche** n’est pas une base de déclaration et n’affiche jamais « Prête à recopier ». Avant la clôture, la liasse reste un calcul en cours.
5. **Sorties** : chaque fichier indique **Provisoire**, **Bloquée** ou **Finale**. Une sortie Bloquée liste les prérequis (calcul fiscal, SIREN, clôture, contrôles de cases) et le bouton reste inactif. Si un téléchargement est tout de même refusé, le message et le lien pour corriger restent dans la page. Le PDF Provisoire se télécharge : il n’est pas une liasse finale. Le **tableur** (.xlsx, Google Sheets) reprend opérations, journal, balance, amortissements et la liasse avec sa posture.
6. Après clôture : **FEC** et **Dossier de contrôle** passent en Finale (zip : FEC, sa description réglementaire, liasse PDF/JSON, empreintes SHA-256). Ils exigent un exercice clôturé. À garder en cas de contrôle. Une liasse encore en Recherche reste Provisoire, même après la clôture.
7. Recopier **soi-même** dans l’espace professionnel impots.gouv.fr (mode EFI, « Déclarer résultat »). SoloLMNP n’envoie rien.
8. Sur la déclaration de revenus du foyer (2042-C-PRO) : résultat en **5NA** (bénéfice ou 0) ou **5NY** (déficit), déficits LMNP antérieurs en **5GA à 5GJ**.
9. Archiver l’accusé de dépôt avec le dossier de contrôle.

Voir aussi [FILING.md](FILING.md).

---

## 7. Conservation

Menu **Conservation** :

- Déposer les justificatifs (PDF, JPEG ou PNG). La liste montre le nom, la date, le type, la taille, l’empreinte SHA-256 et l’écriture liée.
- Lier une écriture par le sélecteur : numéro, date et pièce. Pas d’identifiant interne. Lier un justificatif ne modifie pas l’écriture, y compris si elle est validée.
- **Créer une sauvegarde** régulièrement. La liste montre la date, la taille, la version de l’application, la révision du schéma, l’empreinte et le dernier contrôle. **Contrôler** vérifie l’archive.
- **Restaurer** une sauvegarde de la liste. L’aperçu indique la date et les nombres d’écritures et d’exercices qui remplaceront l’état actuel. Il faut saisir `RESTAURER`. Une copie de l’état actuel est prise avant. Les écritures validées ne se corrigent pas une à une.

---

## Ordre rapide

```text
Activité + SIREN + exercice 2026
  → Bien + banque + emprunts (sans déblocage si achat avant l’exercice)
  → Immobilisations : prévisualiser l’amortissement, créer les immobilisations, faire entrer le bien en comptabilité
  → Recettes / dépenses / échéances / rapprochements
  → Dotations (au 31/12)
  → Valider les brouillons
  → Centraliser / affecter
  → Calculer le résultat fiscal
  → Pré-contrôle → clôturer
  → (si correction) Réouvrir → recalculer → pré-contrôle → reclôturer
  → Liasse à recopier (EFI) + 2042-C-PRO
  → Dossier de contrôle (FEC) + sauvegarde + justificatifs
```

## Limites à connaître

- Périmètre LMNP uniquement (pas de LMP).
- Cession, TVA, plus-values et ventilation automatique du terrain : désactivées. Leur présence bloque la recopie.
- Exercice 2026 : les formulaires du millésime 2027 ne sont pas encore publiés. Vérifiez les numéros de cases sur le formulaire en ligne.
- 2042-C-PRO : cases 5NA / 5NY / 5GA–5GJ relevées par recoupement (PDF officiel non archivé). À contrôler sur votre déclaration.
- Aucune télétransmission.
