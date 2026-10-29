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

Si l’alerte « Stockage non sûr » apparaît, la base est dans OneDrive. Elle reste visible sur toutes les vues, même quand la base est prête. Copiez le projet hors de ce dossier synchronisé avant de saisir : la synchronisation peut corrompre SQLite.

Alternative Docker : voir [DEPLOYMENT.md](DEPLOYMENT.md).

Vérifier que l’écran « État de l’installation » affiche **Base SQLite : Prête**.

---

## 1. Comptabilité — initialiser

Menu **Comptabilité** :

1. **Créer l’activité** (nom + date de début réelle).
2. **Identité** : saisir le **SIREN** (et le SIRET). Sans SIREN, la liasse reste incomplète (statut Recherche ou Provisoire, jamais « Prête à recopier ») et le FEC ne s’exporte pas (son nom réglementaire commence par le SIREN).
3. **Ajouter un exercice 2026** (achat en 2026 : pas de liasse 2025). Millésime `2026`. Les numéros de cases viennent des formulaires 2025 archivés : vérifiez-les sur le formulaire en ligne au moment de déclarer en 2027.
4. (Optionnel) Onglet **Plan comptable** pour ajouter des comptes.

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

**Import CSV banque** (onglet Banque) :

- Format UTF-8, séparateur `;`, en-tête exact : `date;label;amount;reference`
- Prévisualiser → Confirmer → **rapprocher** chaque mouvement

**Import depuis Google Sheets ou CSV** (onglet Transactions, « Importer depuis Google Sheets ou un CSV ») :

- Copier les lignes du Google Sheet de saisie (en-tête compris) et les coller, ou charger un CSV à point-virgule
- Colonnes : `kind;date;piece_date;type;counterparty;amount;description;piece_reference;source_file`, plus `paid` facultative
- `kind` : Recette / Dépense (ou REVENUE / EXPENSE) ; dates JJ/MM/AAAA ou AAAA-MM-JJ ; montants « 1 200,00 € » acceptés
- Mise en forme du Sheet (listes déroulantes Recette/Dépense, types filtrés selon la nature, dates, montants en €, `paid` oui/non, référence de pièce proposée, doublons en rouge) : coller `scripts/gsheet/format_saisie.gs` dans Extensions > Apps Script du Sheet, puis exécuter `setup` une fois
- Choisir le bien, l’exercice et le compte des lignes payées → Prévisualiser → Comptabiliser
- `paid` = oui : opération réglée directement sur ce compte ; sinon elle reste **à régler**. Traitement fiscal à vérifier
- Une référence déjà comptabilisée est ignorée ; un montant différent pour la même référence est refusé
- **Import des échéances** (onglet Emprunts) : choisissez un emprunt, l’exercice et
  la banque, puis collez les lignes d’un seul prêt depuis Google Sheets. Les colonnes
  `Prêt`, `Rang`, `Date`, `Capital`, `Intérêts`, `Assurance banque`,
  `Assurance externe à compléter` et `Total banque` du modèle sont reconnues.
- Vérifiez puis confirmez explicitement la correspondance entre la référence `Prêt`
  du tableau et l’emprunt SoloLMNP sélectionné. Ajoutez si nécessaire une colonne
  `Date débit` pour reprendre la date comptable exacte du relevé bancaire.
- La prévisualisation conserve seulement les échéances de l’exercice déjà arrivées à
  leur date. Elle ignore les doublons identiques et refuse une ventilation différente
  pour une date déjà comptabilisée. Le capital restant dû ou le déblocage doit exister.
- Une assurance externe prélevée séparément ne fait pas partie de l’échéance bancaire :
  importez-la dans Transactions comme dépense `ASS`.

---

## 3. Immobilisations

Menu **Immobilisations** :

1. **Prévisualiser l’amortissement du logement**, puis **Créer les immobilisations affichées**. L’aperçu liste le terrain, la construction et six composants (montants, comptes, durées, mise en service) sans rien enregistrer : ni immobilisation, ni compte. Annuler laisse la base inchangée. Répéter la confirmation ne crée pas de doublon. Les frais de notaire et d’agence sont ajoutés au bâtiment ; les durées proposées sont à confirmer, ce n’est pas un barème légal. Ou saisie manuelle : terrain (compte 211, sans amortissement), puis construction (213000 / 281300) et tous ses composants. Le formulaire ne propose que les comptes de la catégorie, jamais un compte 28 comme compte d’immobilisation.
2. **Faire entrer le bien en comptabilité** (une seule fois, premier exercice) : indiquez le capital restant dû de chaque prêt au début de l’exercice, le solde bancaire à cette date et les frais payés avant (intérêts, assurance emprunteur, frais de dossier). **Prévisualiser**, puis **Comptabiliser**. L’écart va au compte de l’exploitant (108). Les prêts repris ainsi n’ont pas de « déblocage » à saisir : enregistrez seulement les échéances payées pendant l’exercice. Une erreur se corrige en extournant l’écriture depuis le journal.
3. Mobilier : **Nouvelle immobilisation**, comptes 218400 et 281840, avec justification de valeur et de durée. Un couple déjà enregistré qui ne correspond pas à sa catégorie est signalé sur la fiche et n’est pas réécrit tout seul. **Modifier** (ou **Préciser la justification** si la fiche est figée) demande un motif. Avant toute dotation comptabilisée, la valeur, la durée et les comptes peuvent changer : les périodes seulement calculées sont alors effacées, il faut relancer **Calculer les périodes**. Après comptabilisation, ces champs restent affichés comme figés et l’écran dit pourquoi. La même action existe pour le bien, le locataire, la banque et l’emprunt.
4. Choisir l’exercice 2026 → **Calculer les périodes** → **Comptabiliser** chaque dotation (possible à partir du 31/12, date de la dotation).

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

1. Sélectionner l’exercice → **Calculer le résultat fiscal** (après la centralisation, sur le ledger final).
2. **Lancer le pré-contrôle**. S’il manque le calcul, ou s’il ne correspond plus au ledger, le lien **Calculer le résultat fiscal** ramène au calcul. Cocher chaque avertissement affiché : un nouveau pré-contrôle décoche tout, et **Accuser et préparer** reste inactif tant qu’il en manque un. Puis **Confirmer la clôture**. Le statut de l’exercice, le tableau de bord et les sorties (liasse, FEC) se rechargent.
3. Après clôture, l’exercice est figé. Pour le corriger : **Réouvrir l’exercice** (motif d’au moins 10 caractères, confirmation `ROUVRIR`). Les calculs fiscaux et le snapshot liasse/FEC courants sont invalidés ; l’exercice redevient ouvert. Recalculez, relancez le pré-contrôle puis reclôturez pour regénérer les sorties figées.
4. **Liasse à recopier** : le statut **Recherche**, **Provisoire** ou **Déclarable** (le même que le calcul et que le pré-contrôle), points bloquants, consignes de saisie, puis les cases par formulaire (2031, 2031-bis, 2033-A, B, C, E), l’état de suivi des amortissements non déduits et les cases de la 2042-C-PRO. Télécharger le PDF : il porte le même statut. **Recherche** n’est pas une base de déclaration et n’affiche jamais « Prête à recopier ». Avant la clôture, la liasse reste un calcul en cours.
5. À tout moment : **Export tableur (.xlsx, Google Sheets)** — opérations, journal, balance, amortissements, liasse. À déposer dans Google Drive puis « Ouvrir avec Google Sheets ».
6. Après clôture : **FEC** et **Dossier de contrôle** (zip : FEC, sa description réglementaire, liasse PDF/JSON, empreintes SHA-256). À garder en cas de contrôle.
7. Recopier **soi-même** dans l’espace professionnel impots.gouv.fr (mode EFI, « Déclarer résultat »). SoloLMNP n’envoie rien.
8. Sur la déclaration de revenus du foyer (2042-C-PRO) : résultat en **5NA** (bénéfice ou 0) ou **5NY** (déficit), déficits LMNP antérieurs en **5GA à 5GJ**.
9. Archiver l’accusé de dépôt avec le dossier de contrôle.

Voir aussi [FILING.md](FILING.md).

---

## 7. Conservation

Menu **Conservation** :

- Déposer les justificatifs (PDF, JPEG ou PNG), éventuellement liés à une écriture.
- **Créer une sauvegarde** régulièrement.
- La restauration écrit une **copie de contrôle** ; elle ne remplace pas la base en service.

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
