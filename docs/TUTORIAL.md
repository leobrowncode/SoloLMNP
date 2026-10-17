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

Alternative Docker : voir [DEPLOYMENT.md](DEPLOYMENT.md).

Vérifier que l’écran « État de l’installation » affiche **Base SQLite : Prête**.

---

## 1. Comptabilité — initialiser

Menu **Comptabilité** :

1. **Créer l’activité** (nom + date de début réelle).
2. **Ajouter un exercice 2026** (achat en 2026 : pas de liasse 2025). Millésime `2026`. Les numéros de cases viennent du dernier formulaire lu : vérifiez-les au moment de la déclaration 2027.
3. (Optionnel) Onglet **Plan comptable** pour ajouter des comptes.

Pour une activité déjà existante : saisir des **à-nouveaux** justifiés. L’application
ne reconstitue pas l’historique.

---

## 2. Opérations & banque — setup métier

Menu **Opérations & banque**, dans cet ordre :

| Onglet | Action |
| --- | --- |
| **Biens** | Ajouter le bien (prix, terrain, bâtiment) |
| **Banque** | Ajouter un compte bancaire (lié à un compte 512) |
| **Emprunts** | Si besoin : une ligne de crédit = un emprunt. Pour 15 000 € + 195 000 €, créez deux emprunts ; un compte 164 libre est attribué automatiquement. Puis déblocage et échéances (capital / intérêts / assurance / frais : total calculé auto). |
| **Transactions** | Recettes (loyers) et dépenses (charges) |

Pour chaque opération : date, bien, exercice, montant, compte 6xx/7xx.
Si le règlement a lieu le même jour → lier la banque ; sinon choisir « Non réglé »,
puis **Enregistrer un règlement** plus tard.

**Import CSV banque** (onglet Banque) :

- Format UTF-8, séparateur `;`, en-tête exact : `date;label;amount;reference`
- Prévisualiser → Confirmer → **rapprocher** chaque mouvement

**Import CSV de justificatifs** (onglet Transactions) :

- Factures et quittances déjà extraites en CSV
- En-tête exact : `kind;date;piece_date;type;counterparty;amount;description;piece_reference;source_file`
- Choisir le bien et l’exercice → Prévisualiser → Comptabiliser
- Chaque ligne devient une recette ou une dépense **non réglée**, traitement fiscal à vérifier
- Une référence déjà comptabilisée est ignorée ; un montant différent pour la même référence est refusé
- Les échéances d’emprunt restent à saisir à la main dans l’onglet Emprunts

---

## 3. Immobilisations

Menu **Immobilisations** :

1. **Inscrire un terrain** (non amortissable).
2. **Nouvelle immobilisation** (construction, mobilier…) avec justification de valeur et de durée.
3. Pour un bâtiment : **ajouter tous les composants** avant le premier calcul (total = base amortissable).
4. Choisir l’exercice 2026 → **Calculer les périodes** → **Comptabiliser** chaque dotation.

---

## 4. Vérifier la comptabilité

Retour **Comptabilité** :

- Valider tous les **brouillons** (validation = numéro définitif, plus de modification).
- Contrôler **Journal**, **Balance** et **Grand livre**.
- Onglet **Inventaire** pour les écritures d’inventaire manuelles justifiées.

---

## 5. États comptables — fin d’exercice

Menu **États comptables** :

1. Consulter bilan et résultat provisoires.
2. **Préparer la centralisation** → vérifier → confirmer.
3. Puis **affectation** du résultat (120/129 → capitaux) si proposé.
4. **Lancer le pré-contrôle** → cocher les avertissements → **Accuser et préparer** → **Confirmer la clôture**.

Après clôture, l’exercice est figé. Une réouverture exige un motif et invalide les exports.

---

## 6. Aperçu fiscal et feuille EFI

Menu **Fiscalité LMNP** :

1. Sélectionner l’exercice → **Calculer le résultat fiscal**.
2. **Liasse à recopier** : formulaire, numéro de case, libellé, montant. Télécharger le PDF.
3. Après clôture, **télécharger le FEC** (contrôle fiscal). Il n’est pas la déclaration.
4. Recopier **soi-même** dans l’espace professionnel impots.gouv.fr (mode EFI). SoloLMNP n’envoie rien.
5. Archiver l’accusé du portail.

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
Activité + exercice 2026
  → Bien + banque (+ emprunt)
  → Recettes / dépenses / rapprochements
  → Immobilisations + dotations
  → Valider les brouillons
  → Centraliser / affecter
  → Pré-contrôle → clôturer
  → Feuille EFI → recopie manuelle
  → Sauvegarde + justificatifs
```

## Limites à connaître

- Périmètre LMNP uniquement (pas de LMP).
- Cession, TVA, plus-values et ventilation automatique du terrain : désactivées. Leur présence bloque la recopie.
- Exercice 2026 seulement. Il n’y a pas de liasse 2025. Vérifiez les numéros de cases sur la déclaration déposée en 2027.
- 2042-C-PRO : case non archivée, à part de la liasse BIC.
- Aucune télétransmission.
