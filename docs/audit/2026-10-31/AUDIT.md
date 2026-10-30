# Audit SoloLMNP — 31 octobre 2026

Audit de parcours, sans correction du produit. Objectif rappelé par le propriétaire : une interface **claire et simple**.

## Méthode

Application lancée en local : API FastAPI sur `127.0.0.1:8000`, interface Vite sur `127.0.0.1:5173`. Base SQLite vide, puis un dossier LMNP au réel calqué sur le premier exercice des tests d’intégration.

- Activité « LMNP Mérignac », SIREN `123456789`, SIRET `12345678900019`, millésime 2025.
- Exercice du 06/04/2025 au 31/12/2025 (une écriture postérieure à la date du jour est refusée).
- Bien Mérignac 1, 11 rue des Acacias, 33700. Prix 145 000 €, frais 18 262 €, terrain 29 000 €, bâtiment 116 000 €. Base amortissable retenue par le plan : 134 262 €, ventilée en composants dont la somme est exacte.
- Deux emprunts : 15 000 € (compte 164000) et 195 000 € (164001), taux 3,25 %, départ 09/01/2025.
- Locataire Camille Dupont, loyer 850 €. Recettes, assurance PNO 180 €, copropriété 1 200 €, taxe foncière 900 €, entretien 240 € non payé.
- Entrée du bien tentée après la clôture : capital restant dû 14 884 € et 195 000 €, banque 46 000 €, intérêts antérieurs 1 200 €, frais de dossier 500 €. Apport attendu et obtenu : 1 078,00 €.

Parcours joués dans Chromium headless (Playwright), en 1 280 px et 390 px : démarrage, biens, plan d’amortissement, banque et CSV, journal, plan comptable, grand livre, balance, centralisation, fiscalité, pré-contrôle, clôture, réouverture, liasse à recopier, 2042-C-PRO, documents, sauvegarde, contrôle, restauration. Les captures sont dans `docs/audit/2026-10-31/screenshots/`.

Les montants cités pour la liasse bloquée sont ceux de l’exercice **clôturé avant l’entrée du bien**. L’entrée a ensuite été rejouée après réouverture, pour finir le parcours : l’écriture est équilibrée et l’apport est bien 1 078,00 € (`screenshots/1280-property-entry-preview.png`).

Les issues ouvertes [#7](https://github.com/leobrowncode/SoloLMNP/issues/7) (moteur fiscal encore en recherche) et [#11](https://github.com/leobrowncode/SoloLMNP/issues/11) (existence de la feuille EFI et du 2042-C-PRO) ne sont pas recréées. Le statut « Recherche » et la feuille elle-même existent déjà. Ce document ne porte que sur des écarts constatés dans l’usage.

## Synthèse

Deux blocages, sept gênes, et un lot de finitions. Le calcul fiscal de ce dossier, tant que le bien n’est pas au bilan, est cohérent **avec le journal incomplet** : loyers 6 800 €, charges externes 1 620 €, impôts 900 €, dotations 4 201,51 €, résultat 78,49 €. Ce résultat se retrouve sur le 2033-B, le 2031 et la case 5NA. Le problème n’est pas une erreur d’arrondi. C’est qu’on peut clôturer, et même télécharger un FEC marqué final, alors que le bâtiment n’a jamais été inscrit au bilan. Et qu’une sauvegarde ordinaire, avec le dossier de documents livré par le dépôt, ne se restaure pas.

Les dix points à traiter en premier :

1. **Restaurer une sauvegarde échoue** dès qu’elle contient `documents/.gitkeep`. Message : « Chemin de document refusé ».
2. **On clôture sans inscrire le bien.** Le 2033-A affiche des immobilisations nettes de −4 201,51 €. Le parcours marque pourtant « Terminé ».
3. **Après centralisation, les états affichent un résultat de 0,00 €**, alors que le compte 120 et la liasse portent 78,49 €. La rubrique « Capitaux propres hors résultat » contient le 120.
4. **Un emprunt non comptabilisé affiche un solde de 0,00 €**, et le message de succès propose une échéance dont le bouton est désactivé.
5. **L’import CSV comptabilise la seule ligne valide** et noie les lignes rejetées dans un tableau trop large.
6. **La surface du terrain est obligatoire** alors que le champ n’est pas envoyé au serveur. Le prix au m² est prérempli à 0,00.
7. **L’en-tête et la vue d’ensemble répètent** le même statut, la même progression et le même « Continuer ». En 390 px, cet en-tête occupe le premier écran. Les aides sont des « ? » sans mot.
8. **Le FEC est marqué « Finale »** et téléchargeable, alors que le texte promet le même statut pour le calcul, la liasse et les exports, et que la liasse est « Bloquée ».
9. **La page Immobilisations répète six fois** le même appel à justifier une durée, plus un long pavé de succès.
10. **L’aperçu du plan montre la construction pour 134 262 € et, en dessous, les composants qui totalisent déjà 134 262 €.** Le moteur n’amortit pas deux fois. La lecture, si.

## P0 — bloquant

### P0-1. Une sauvegarde normale ne se restaure pas

Le dépôt contient `data/documents/.gitkeep`. La création d’archive copie **tous** les fichiers du dossier documents, y compris celui-ci. À la restauration, un nom qui commence par un point est refusé et toute l’opération s’arrête avec « Chemin de document refusé ».

Le contrôle d’intégrité, lui, répond « Contrôle d’intégrité réussi ». Le bouton « Restaurer la sauvegarde » est donc actif. L’échec n’arrive qu’au clic. La copie de sécurité créée juste avant la restauration contient le même `.gitkeep` : elle est, elle aussi, irrestaurable.

**Reproduction**

1. Démarrer avec le dossier documents livré (le fichier `.gitkeep` est présent).
2. Déposer un justificatif, ou n’en déposer aucun : le fichier caché suffit.
3. Conservation → Créer une sauvegarde → Contrôler la sauvegarde.
4. Saisir `RESTAURER`, puis Restaurer la sauvegarde.

**Capture.** `screenshots/1280-restored.png` (bandeau d’erreur). Le contrôle réussi est dans `screenshots/1280-restore-preview.png`.

**Correction simple.** N’archiver que les fichiers réellement enregistrés (nom stocké en base), et ignorer les noms qui commencent par un point. Ne pas faire échouer une restauration à cause d’un fichier que l’application a elle-même mis dans le zip. Le `except Exception` nu autour du retour arrière (`backend/app/services/backup.py`) doit au minimum journaliser l’échec : aujourd’hui un rollback raté disparaît.

### P0-2. On clôture un exercice dont le bien n’est pas au bilan

Ordre réellement possible dans l’interface :

1. Créer le plan d’amortissement (registre seulement).
2. Calculer les périodes et comptabiliser toutes les dotations.
3. Centraliser, calculer le résultat fiscal, accuser les avertissements, clôturer.

Le bouton « Faire entrer le bien en comptabilité » reste disponible, mais rien ne l’exige. Le tableau de bord passe « Immobilisations et amortissements » à **Terminé** dès que les dotations sont passées. Le pré-contrôle ne bloque pas : l’écart d’immobilisations est un avertissement à cocher, pas une erreur.

Conséquences, exercice clôturé, bien absent du journal :

| Écran | Montant |
| --- | --- |
| Compte 281 (amortissements) | 4 201,51 € |
| Comptes 211 / 213 (brut) | 0 € |
| 2033-A, case 030, immobilisations corporelles nettes | **−4 201,51 €** |
| 2033-A, total actif net et total passif | 328,49 € |
| 2033-B, case 370, et 2042-C-PRO case 5NA | 78,49 € |
| Avertissement bloquant de la liasse | `IMMOBILISATIONS_ECART` |

Le bilan « équilibre » : banque 4 530 €, amortissements −4 201,51 €, fournisseur 240 €, exploitant 10 €, résultat 78,49 €. Il équilibre un dossier faux. La liasse affiche ensuite « À corriger avant de déclarer », mais la clôture est déjà faite et le FEC reste téléchargeable (voir P1-6).

Après réouverture, l’entrée du 06/04/2025 se comptabilise correctement (apport 1 078,00 €, pièces `ACTE-2025-01-09`). Les charges d’avant exercice (661 pour 1 200 € et 627 pour 500 €) tombent alors **à côté** du résultat déjà centralisé. Il faut recentraliser. L’outil ne le dit pas au moment où il a laissé clôturer.

**Reproduction**

1. Créer le bien, les emprunts et le plan, sans faire l’entrée en comptabilité.
2. Immobilisations → Calculer les périodes → Comptabiliser toutes les dotations.
3. États comptables → centraliser. Fiscalité → calculer, pré-contrôle, accuser, clôturer.
4. Ouvrir « Liasse à recopier », case 030 du 2033-A.

**Captures.** `screenshots/1280-depreciation-posted.png`, `screenshots/1280-statements-after.png`, `screenshots/1280-fiscal-efi.png`, `screenshots/390-filled-overview.png` (étape Immobilisations « Terminé » et liasse bloquée). L’entrée correcte, après coup : `screenshots/1280-property-entry-preview.png`.

**Correction simple.** Interdire la dotation et la clôture tant que le brut du registre n’est pas au journal. Traiter `IMMOBILISATIONS_ECART` comme une erreur de pré-contrôle, pas comme une case à cocher. Ne marquer l’étape Immobilisations terminée qu’après l’entrée du bien.

## P1 — gênant

### P1-1. Le résultat des états vaut 0,00 € après la centralisation

La centralisation solde les classes 6 et 7 vers le 120. Les états affichent alors, en gras, « Résultat comptable : 0,00 € », puis « Résultat de l’exercice : 0,00 € ». Le compte 120, créditeur de 78,49 €, est listé dans la section intitulée **« Capitaux propres hors résultat »**.

La fiscalité, le 2033-B et la case 5NA affichent 78,49 €. Un même dossier, deux résultats, sans une phrase du type « le résultat centralisé est sur le compte 120 ».

Le statut renvoyé par l’API des états reste `PROVISIONAL` même exercice clôturé. L’écran ne l’affiche pas. L’information est fausse des deux côtés : ni provisoire au sens où plus rien ne bouge, ni un résultat de 0 €.

**Reproduction.** Centraliser, puis ouvrir États comptables. Comparer avec Fiscalité LMNP.

**Capture.** `screenshots/1280-statements-after.png`. Fiscalité : `screenshots/1280-fiscal-computed.png` et `screenshots/1280-fiscal-efi.png`.

**Correction simple.** Après centralisation, afficher le résultat du compte 120/129 comme résultat de l’exercice, et réserver « Capitaux propres hors résultat » aux comptes autres que 120 et 129. Aligner le statut des états sur l’exercice (ouvert ou clôturé).

### P1-2. Un emprunt non passé en comptabilité a un solde de 0,00 €

À la création, « Crédit Habitat 195k » affiche « Capital initial : 195 000,00 € · Solde comptable : 0,00 € ». On lit un prêt soldé. Le message de succès propose « Saisir une échéance », alors que déblocage et échéance sont désactivés tant qu’il n’y a pas de banque (« Déblocage et échéance indisponibles »).

Deux chemins coexistent sans ordre : « Enregistrer le déblocage » et, plus tard, l’entrée du bien, dont le texte dit que le déblocage est inutile. Un déblocage après l’entrée est refusé. L’import d’échéances avant l’un ou l’autre est refusé aussi (`LOAN_NOT_FUNDED`), à juste titre, mais l’outil le propose quand même.

Quand une banque existe et que le capital n’est toujours pas au journal, le formulaire d’échéance affiche « Aucun capital comptable à rembourser » **et** laisse « Confirmer l’enregistrement ». La confirmation répond 409.

**Reproduction.** Créer un emprunt avant la banque et avant l’entrée du bien. Lire la carte, le message vert, puis ouvrir une échéance.

**Captures.** `screenshots/1280-emprunts.png`, `screenshots/1280-loan-payment.png`, `screenshots/1280-csv-loan-preview.png`.

**Correction simple.** Tant que rien n’est comptabilisé, afficher « Pas encore au bilan », pas un solde de 0,00 €. Un seul prochain pas : la banque, puis l’entrée du bien (ou le déblocage, pas les deux). Désactiver « Confirmer » quand le bandeau dit déjà que l’échéance est impossible. Masquer l’import d’échéances jusqu’à ce que le capital soit au compte 164.

### P1-3. La surface du terrain bloque un formulaire qui ne l’enregistre pas

« Surface du terrain ou quote-part (m²) » est obligatoire. Le champ est local : il ne part pas dans la requête. L’aide dit qu’il sert seulement à proposer le terrain. Le tutoriel et le texte du formulaire demandent le prix, le terrain et le bâtiment. « Prix constaté au m² » est prérempli à `0,00`, donc il passe le contrôle « obligatoire » sans être une saisie.

Sur le même formulaire, le champ date vide affiche le masque `mm/dd/yyyy` et, dessous, « Format JJ/MM/AAAA ».

**Reproduction.** Opérations → Biens → Ajouter un bien → Vérifier avant enregistrement, sans remplir la surface.

**Capture.** `screenshots/1280-property-form-required.png`.

**Correction simple.** Rendre la surface et le prix au m² facultatifs. N’exiger que le prix, les frais, le terrain et le bâtiment, avec terrain + bâtiment = prix. Afficher le calendrier en JJ/MM/AAAA.

### P1-4. L’import CSV enregistre une ligne et cache les onze autres

Sans compte bancaire, un collage de douze lignes (loyers et charges « déjà payées », plus un entretien non payé) donne « 11 erreur(s), 1 valide ». Le bouton « Comptabiliser les justificatifs » reste actif. Il passe la seule ligne non payée (240 €, compte 401). Le message de succès parle de cette ligne. Les loyers ne sont pas en comptabilité. Le détail des erreurs est un tableau très large : en 1 280 px la raison (« Choisissez le compte bancaire des lignes déjà payées ») se lit mal, en 390 px elle sort de l’écran.

Avec une banque choisie, le même type de fichier passe (11 lignes valides). Le piège est le premier essai, le plus probable.

**Reproduction.** Transactions → Importer depuis Google Sheets, sans banque, avec des lignes « Déjà payée = oui ». Comptabiliser.

**Captures.** `screenshots/1280-csv-operations-preview.png`, `screenshots/1280-transactions.png`. Le second import, réussi : `screenshots/1280-csv-operations-with-bank.png`.

**Correction simple.** S’il reste une erreur, ne pas proposer de comptabiliser « quand même ». Lister les rejets en phrases courtes au-dessus du bouton, pas dans un tableau plus large que la page. S’il n’y a pas de banque, le dire avant l’aperçu.

### P1-5. L’en-tête et la vue d’ensemble redisent la même chose

Dossier vide, chaque carte répète « L’activité n’est pas créée », « Aucun événement utile pour l’instant » et un lien « Créer l’activité ». « Continuer » est dans l’en-tête **et** dans le tableau de bord. L’en-tête ajoute encore le statut et « Progression 0/6 ». Trois boutons « ? » n’ont pas de libellé visible : le mot n’apparaît que dans l’infobulle (`Aide : …`).

En 390 px, statut + progression + Continuer passent sur plusieurs lignes avant le titre de la page. Le même schéma reste après clôture : le bandeau « Bloqué » et le détail des exports sont répétés dans l’en-tête de chaque écran.

**Reproduction.** Ouvrir la vue d’ensemble avant toute saisie, en 1 280 px puis en 390 px.

**Captures.** `screenshots/1280-empty-overview.png`, `screenshots/390-empty-overview.png`, `screenshots/1280-glossary-open.png`.

**Correction simple.** Une seule zone « prochaine action ». Sur les cartes, une ligne d’état, pas le même manque recopié trois fois. Sur mobile, garder le titre de la page ; replier statut et progression. Remplacer le « ? » nu par le mot (« LMNP », « Liasse », « FEC »).

### P1-7. La page Immobilisations répète six fois la même justification

Après le plan, chaque composant a le même paragraphe « Préciser la justification… » et son bouton. Le message de succès des dotations relit toute la liste. Quatre « ? » en haut de page. La saisie utile (entrée du bien, calcul, comptabilisation) est noyée.

**Reproduction.** Créer le plan d’amortissement, puis comptabiliser les dotations. Scroller la page Immobilisations.

**Captures.** `screenshots/1280-assets-preview.png`, `screenshots/1280-depreciation-posted.png`.

**Correction simple.** Une ligne par composant dans le tableau, avec la justification dans la ligne. Un seul message de succès, avec le total des dotations et le lien vers le journal.

### P1-6. Le FEC est « Finale » pendant que la liasse est « Bloquée »

Le pré-contrôle et la page fiscalité affichent : « Même statut pour le calcul, la liasse et les exports. » Sur le dossier clôturé sans le bien :

- calcul : Recherche ;
- liasse et PDF : Bloquée, téléchargement refusé ;
- FEC et dossier de contrôle : **Finale**, téléchargement proposé.

Le FEC d’un journal sans le bâtiment est donc présenté comme la pièce finale. Ce n’est pas une demande de valider le millésime (issue #7) ni de créer la feuille (issue #11). C’est le libellé qui contredit la phrase juste au-dessus, et un téléchargement qui a l’air officiel.

**Reproduction.** Clôturer le dossier du P0-2, puis regarder le bloc « Sorties figées » et la liasse.

**Capture.** `screenshots/1280-fiscal-efi.png`. Avant clôture, le même décalage est déjà visible : `screenshots/1280-glossary-open.png`.

**Correction simple.** Un seul statut affiché. Tant que la liasse est bloquée ou en recherche, le FEC ne doit pas être marqué « Finale ».

## P2 — finition

Un seul lot. Aucun n’empêche de finir un dossier correct. Chacun éloigne l’outil de « clair et simple », ou laisse un défaut latent.

| Point | Constat | Capture | Correction simple |
| --- | --- | --- | --- |
| Aperçu du plan | La ligne Construction 134 262 € est affichée **en plus** des composants qui totalisent 134 262 €. La légende dit la bonne base. L’œil additionne le double. Le moteur, lui, n’amortit que les composants. L’écriture d’entrée réelle ne débite le 213000 que pour le gros œuvre (53 704,80 €). | `screenshots/1280-assets-preview.png` | Présenter la construction comme un total « dont », pas comme une ligne de plus. |
| 5NA et 5NY | Les deux cases sont toujours là. Une seule porte le montant (ici 5NA 78,49 €, 5NY 0,00 €). La note l’explique, en un paragraphe. | `screenshots/1280-fiscal-efi.png` | N’afficher que la case qui porte le montant, et une ligne « l’autre case reste à 0 ». |
| « n’envoie rien » | La phrase est dans le menu, l’introduction, la fiscalité et le bas de la liasse. | `screenshots/1280-empty-overview.png` | La garder une fois, sur la liasse. |
| Dates | Champ vide en `mm/dd/yyyy`, aide en JJ/MM/AAAA. Une date saisie en 2025-06-09 s’affiche ensuite 09/06/2025. | `screenshots/1280-property-form-required.png` | Masque et aide identiques. |
| Taux d’emprunt | « Taux annuel (%) » est un champ monétaire, donc deux décimales. 3,25 % passe. Un taux à trois décimales, non. | formulaire emprunt, code `OperationsPage.tsx` | Champ nombre, pas un montant en euros. |
| Clés React | Aucun avertissement « same key » dans la console sur la liasse de ce dossier. Les cases 5NA/5NY et les années de report sont des clés distinctes. En revanche le pré-contrôle fait `key={item.code}` : `CLASSEMENT_INCOMPLET` peut être émis deux fois (2033-A et 2033-E), avec deux textes. Les deux cases cocheraient ensemble. | non reproduit à l’écran ; `CloseYear.tsx`, `liasse.py` | Clé `code + message`. Un accusé par avertissement. |
| Restauration, retour arrière | Si le remplacement de la base échoue, le `except Exception` qui repose la copie de sécurité avale aussi l’échec de ce retour arrière. | `backend/app/services/backup.py` | Laisser remonter, ou écrire l’erreur. |
| Aperçu CSV | L’inspection des colonnes ignore toute erreur (`.catch(() => undefined)`). | `CsvImportAssistant.tsx` | Afficher l’échec. L’utilisateur croit que le collage est muet. |
| Import d’échéances | Le tableau d’erreurs est plus large que la page. Les deux rejets du jeu d’essai (capital pas au bilan, total banque faux) sont justes, mais durs à lire. | `screenshots/1280-csv-loan-preview.png` | Une alerte par ligne, au-dessus du tableau. |
| Console | `GET /api/fiscal/years/1` et parfois la liasse répondent 404 tant que le calcul n’existe pas. L’écran gère le vide, la console reste rouge. | métadonnées du parcours | Répondre 200 avec un état vide, ou ne pas appeler avant le premier calcul. |
| Tables en 390 px | Fiscalité, états et imports deviennent une longue colonne. Les tableaux dépassent. | `screenshots/390-filled-fiscal.png`, `screenshots/390-filled-statements.png` | Cartes « case / montant » sous 800 px, pas un tableau horizontal. |

## Ce qui tient

- Création de l’activité, de l’exercice, du bien, du locataire, des emprunts et du compte 512.
- Plan par composants : somme exacte de la base 134 262 €, pas de double amortissement dans le moteur.
- Relevé CSV : la ligne `99/99/2025` est rejetée, les deux mouvements valides passent.
- Import d’opérations une fois la banque choisie.
- Brouillon OD puis validation.
- Centralisation `CENT-2025` équilibrée.
- Cohérence, **sur le journal incomplet**, entre fiscalité, 2033-B, 2031 et 5NA (78,49 €). Capacité d’amortissement 4 280 €, dotation déduite 4 201,51 €, report 0 €.
- Entrée du bien après réouverture : écriture du 06/04/2025 équilibrée, apport 1 078,00 €.
- Dépôt d’un justificatif PNG, création de sauvegarde, contrôle d’intégrité affiché comme réussi.
- Réouverture avec motif et saisie `ROUVRIR`.
- Aucune clé React dupliquée constatée sur la liasse de ce dossier.

## Écarts laissés aux issues déjà ouvertes

- Le millésime reste « Recherche », non déclarable. C’est le cadre de l’issue #7, pas un nouveau défaut d’écran.
- La feuille EFI, le 2042-C-PRO et le téléchargement manuel existent. L’issue #11 demande cette construction. Les défauts ci-dessus portent sur des montants faux, un statut contredit et une page trop chargée, pas sur l’absence de la feuille.
