/**
 * Single glossary for LMNP au réel (BIC). Screens and API errors point here.
 * Vintages stay research_only: this copy never says a sheet is declarable.
 */

export const GLOSSARY_PROMPTS = {
  what: "C’est quoi",
  why: "Pourquoi c’est demandé",
  example: "Exemple",
  mistake: "Erreur fréquente",
} as const;

export interface GlossaryEntry {
  label: string;
  what: string;
  why: string;
  example: string;
  mistake: string;
}

export const GLOSSARY = {
  "lmnp-reel": {
    label: "LMNP au réel",
    what: "Location meublée non professionnelle imposée aux bénéfices industriels et commerciaux, régime réel. SoloLMNP suit une location longue durée, pas le micro-BIC et pas le LMP.",
    why: "Le réel demande une comptabilité : loyers, charges, emprunt, amortissements, puis une liasse à recopier. Le micro-BIC ne suit pas ce parcours.",
    example: "Un logement meublé loué à l’année, avec un emprunt et un bâtiment amorti. Les recettes et les charges sont des écritures, pas un simple pourcentage des loyers.",
    mistake: "Traiter un LMP, une location nue ou le micro-BIC avec ces écrans, ou croire que le calcul affiché est déjà envoyé aux impôts.",
  },
  exercice: {
    label: "Exercice",
    what: "Période comptable, souvent l’année civile, avec une date de début et une date de fin. Le millésime fiscal est l’année des formulaires, pas forcément le même mot que l’exercice.",
    why: "Chaque écriture, dotation, état et calcul fiscal est rattaché à un exercice ouvert, prêt à clôturer ou clôturé. Les reports ne sont repris que depuis des exercices déjà clôturés.",
    example: "Achat en 2026 : exercice du 01/01/2026 au 31/12/2026, millésime 2026. Il n’y a pas de liasse 2025 à produire pour cet achat.",
    mistake: "Saisir une charge de 2026 sur l’exercice 2025, ou calculer le résultat fiscal avant d’avoir validé et centralisé l’exercice.",
  },
  millesime: {
    label: "Millésime",
    what: "Année des formulaires utilisée pour les numéros de cases. Les millésimes chargés restent en recherche : ce ne sont pas une attestation, et les cases se contrôlent sur le formulaire en ligne au moment de déclarer.",
    why: "Un exercice 2026 peut s’appuyer sur les formulaires 2025 archivés tant que le millésime suivant n’est pas publié. Le statut Recherche rappelle de vérifier.",
    example: "Exercice 2026, millésime 2026 dans l’écran Comptabilité. Les cases affichées viennent des formulaires connus ; vous les revoyez sur impots.gouv.fr en 2027.",
    mistake: "Recopier les cases d’un millésime en recherche sans ouvrir le formulaire de l’année, ou changer le millésime pour « débloquer » un envoi que l’application ne fait pas.",
  },
  siren: {
    label: "SIREN",
    what: "Identifiant à 9 chiffres de l’entreprise. Le SIRET (14 chiffres) le précise sur la 2031. Sans SIREN, la liasse reste incomplète et le FEC ne s’exporte pas.",
    why: "Le nom réglementaire du FEC commence par le SIREN. La liasse et le pré-contrôle s’en servent pour dire si la feuille est encore en recherche ou provisoire.",
    example: "SIREN 123456789 saisi dans Comptabilité → Identité. Le fichier FEC d’un exercice clos au 31/12/2026 se nomme alors 123456789FEC20261231.txt.",
    mistake: "Laisser le SIREN vide puis télécharger le FEC, ou confondre SIREN et SIRET en saisissant 14 chiffres dans le champ à 9 chiffres.",
  },
  liasse: {
    label: "Liasse",
    what: "Feuille de recopie des formulaires 2031, 2031-bis et 2033 (A, B, C, E). SoloLMNP prépare les montants. Il n’envoie rien. Un millésime en recherche n’est pas une base de déclaration.",
    why: "Au réel, le résultat de la location meublée se reporte sur ces formulaires, puis vous les recopiez vous-même en mode EFI. Avant la clôture, la liasse est un calcul en cours.",
    example: "Après le calcul fiscal et la clôture, ouvrir Liasse à recopier : statut affiché, points bloquants, puis les cases. Le PDF provisoire n’est pas une liasse finale.",
    mistake: "Recopier une liasse encore en recherche, ou un PDF provisoire, sans vérifier les numéros de cases sur le formulaire en ligne.",
  },
  efi: {
    label: "EFI",
    what: "Échange de formulaires informatisé : le mode « Déclarer résultat » sur impots.gouv.fr, où vous saisissez vous-même la liasse. SoloLMNP n’envoie rien et ne télétransmet pas.",
    why: "La feuille et le PDF servent de brouillon de recopie. Le dépôt, la validation et l’accusé restent dans votre espace professionnel.",
    example: "Exercice clôturé, PDF de recopie ouvert à côté de la téléprocédure EFI. Vous reportez les cases, vous contrôlez, puis vous conservez l’accusé avec le dossier de contrôle.",
    mistake: "Déposer le PDF comme s’il avait été transmis, ou croire qu’un statut Recherche autorise l’envoi.",
  },
  fec: {
    label: "FEC",
    what: "Fichier des écritures comptables (livre des procédures fiscales, art. A. 47 A-1). Il liste les écritures validées d’un exercice clôturé, à-nouveaux et inventaire compris. Il exclut la centralisation et le solde des classes 6 et 7. Ce n’est pas la liasse, et SoloLMNP ne l’envoie pas.",
    why: "À garder en cas de contrôle, avec sa description. Le nom du fichier commence par le SIREN. Il exige un exercice clôturé.",
    example: "Exercice clôturé, SIREN renseigné : télécharger le FEC dans les sorties. Le dossier de contrôle reprend ce fichier, la liasse et les empreintes.",
    mistake: "L’exporter avant la clôture, sans SIREN, ou y chercher les cases fiscales. Une liasse encore en recherche ne se dépose pas : le millésime reste en recherche.",
  },
  "dossier-controle": {
    label: "Dossier de contrôle",
    what: "Archive zip à conserver : FEC, description réglementaire, liasse PDF et JSON, empreintes SHA-256. Elle se télécharge après clôture. SoloLMNP n’envoie rien aux impôts.",
    why: "En cas de contrôle, ce paquet rassemble les pièces que l’application a figées. Une réouverture invalide le snapshot courant ; les anciennes preuves restent consultables.",
    example: "Après clôture, sortie Finale « Dossier de contrôle ». Vous le rangez avec les justificatifs et, plus tard, l’accusé de dépôt EFI.",
    mistake: "Le prendre pour un envoi déjà fait, ou le générer avant la clôture et le calcul fiscal.",
  },
  "declaration-foyer": {
    label: "2042-C-PRO",
    what: "Déclaration de revenus du foyer, à part de la liasse professionnelle. Le résultat BIC de la location se reporte en 5NA (bénéfice ou 0) ou 5NY (déficit). Les déficits LMNP antérieurs vont en 5GA à 5GJ.",
    why: "La liasse ne remplace pas la déclaration du foyer. Ces cases sont un rappel à contrôler : le PDF officiel n’est pas archivé ici.",
    example: "Résultat fiscal 0 € : case 5NA à 0. Déficit de l’activité : 5NY. Un déficit LMNP de 2024 encore ouvert se suit vers 5GA–5GJ, après vérification sur votre déclaration.",
    mistake: "Recopier ces montants sans ouvrir la 2042-C-PRO de l’année, ou les confondre avec les cases de la 2033.",
  },
  extourne: {
    label: "Extourne",
    what: "Écriture inverse qui annule une écriture déjà validée, sans l’effacer. Le journal garde l’originale et l’extourne. Une écriture née d’une opération (recette, échéance, dotation, entrée du bien) s’extourne depuis cette opération, pas par une chaîne d’extournes au journal.",
    why: "La validation est définitive. Corriger un montant, un compte ou une date passe par l’extourne, avec une date, une pièce et un motif.",
    example: "Loyer validé à 700 € au lieu de 800 € : extourne des 700 €, puis nouvelle écriture à 800 €. Les deux lignes restent visibles, la source indique Extournes.",
    mistake: "Supprimer une écriture validée, extourner deux fois la même pièce, ou extourner au journal une écriture qui doit l’être depuis l’opération d’origine.",
  },
  "a-nouveaux": {
    label: "À-nouveaux",
    what: "Reprise des soldes de bilan au premier jour de l’exercice, dans le journal AN. Pour une activité déjà existante, vous les justifiez : l’application ne reconstitue pas l’historique. La prévisualisation ne crée aucune écriture tant que vous ne comptabilisez pas.",
    why: "Sans reprise, la banque, l’emprunt et l’immeuble ne partent pas des soldes de la veille. Le FEC attend ces lignes d’à-nouveaux. L’exercice précédent doit être clôturé, sans brouillon.",
    example: "Au 01/01/2026 : banque 3 200 € au débit, capital restant dû 180 000 € au crédit du 164, construction au coût et amortissements cumulés au crédit du 281.",
    mistake: "Les générer avant la clôture de N−1, y passer un loyer de l’année, ou croire qu’ils remplacent les factures anciennes.",
  },
  centralisation: {
    label: "Centralisation",
    what: "Écritures qui soldent les charges (classe 6) et les produits (classe 7) pour faire apparaître le résultat. Le bénéfice va au 120, le déficit au 129. Préparer ou quitter ne modifie pas le plan comptable. Confirmer peut créer 120000 ou 129000 s’il manque. Cette étape ne clôture pas l’exercice.",
    why: "Le bilan doit porter le résultat de l’année. Le FEC exclut ces écritures de centralisation et le solde des classes 6 et 7 : elles ne sont pas le fichier de contrôle.",
    example: "Brouillons validés, puis Préparer la centralisation, vérifier le montant, confirmer. Le calcul fiscal se lance ensuite dans Fiscalité LMNP, sur ce ledger final.",
    mistake: "Croire que centraliser clôture l’exercice, ou lancer la centralisation alors que des brouillons sont encore ouverts.",
  },
  affectation: {
    label: "Affectation",
    what: "Après la centralisation, transfert du solde 120 ou 129 vers un compte de capitaux (souvent le compte de l’exploitant). Ce n’est pas la clôture fiscale.",
    why: "Le résultat centralisé ne reste pas indéfiniment sur 120 ou 129 si vous décidez de l’affecter. L’écran ne propose l’affectation qu’une fois la centralisation comptabilisée.",
    example: "Bénéfice au 120000, puis affectation vers le 108000 du montant confirmé, avec pièce et justification d’au moins 10 caractères.",
    mistake: "Affecter avant d’avoir centralisé, ou reprendre un compte 120 ou 129 comme compte de destination.",
  },
  "compte-120-129": {
    label: "Comptes 120 et 129",
    what: "120 : résultat de l’exercice (bénéfice). 129 : résultat de l’exercice (perte). Ils reçoivent le solde des classes 6 et 7 lors de la centralisation. Le compte manquant (120000 ou 129000) peut être créé au moment de la confirmation, pas avant.",
    why: "Le bilan a besoin d’un compte de résultat. L’affectation vide ensuite ce solde vers les capitaux si vous la confirmez.",
    example: "Charges supérieures aux produits : le résultat va au 129000. L’année suivante, un bénéfice irait au 120000, pas sur le même compte.",
    mistake: "Créer ces comptes à la main « pour voir », ou centraliser un bénéfice sur le 129.",
  },
  "compte-108": {
    label: "Compte 108",
    what: "Compte de l’exploitant (108000 dans le plan proposé). Il reçoit l’écart quand le bien entre en comptabilité : prix, terrain, emprunts et frais payés avant l’exercice ne tombent pas juste.",
    why: "L’écriture d’entrée doit être équilibrée. L’écart n’est ni une charge de l’année ni un oubli de banque : c’est le solde de l’exploitant à cette date.",
    example: "Immeuble et terrain au débit, capital restant dû et apport au crédit. Le reliquat s’équilibre au 108000. Les échéances de l’année se saisissent ensuite, sans nouveau déblocage.",
    mistake: "Mettre cet écart en charge 6, ou saisir un déblocage en plus de l’entrée du bien pour le même capital.",
  },
  "compte-164": {
    label: "Compte 164",
    what: "Emprunts auprès des établissements de crédit. Une ligne de crédit = un emprunt = un compte 164, attribué automatiquement (164000, puis 164001…) et figé ensuite. Le capital y est suivi. Les intérêts vont au 661000, l’assurance au 616000, pas au 164.",
    why: "Deux prêts ne partagent pas un solde. Le capital restant dû à l’entrée du bien, puis chaque échéance, doivent toucher le bon 164.",
    example: "15 000 € et 195 000 € sont deux emprunts, donc deux comptes 164. Une échéance de 800 € se ventile : capital au 164, intérêts au 661000, assurance au 616000.",
    mistake: "Un seul compte pour deux lignes de crédit, ou passer toute l’échéance au 164.",
  },
  emprunt: {
    label: "Emprunt",
    what: "Un contrat de crédit du bien. Le tableau d’amortissement de la banque (capital, intérêts, assurance) n’est pas l’amortissement comptable du bâtiment. Si le prêt existait avant l’exercice, on reprend le capital restant dû : il n’y a pas de déblocage à saisir.",
    why: "Chaque échéance payée pendant l’exercice devient une écriture datée. Le taux, la durée et le prêteur restent corrigeables ; le capital initial et la date de départ se figent dès qu’un mouvement existe.",
    example: "Échéance du 05/03/2026 : capital 450 €, intérêts 310 €, assurance banque 40 €. L’assurance externe prélevée à part est une dépense ASS, pas une ligne de cette échéance.",
    mistake: "Confondre le tableau bancaire avec la dotation du 681, ou importer des échéances futures qui ne sont pas encore arrivées à leur date.",
  },
  "compte-512": {
    label: "Compte 512",
    what: "Compte banque (512000 ou un compte dédié de la même racine). Chaque compte bancaire de l’écran Banque y est lié. Le numéro se fige dès qu’un mouvement ou une écriture l’utilise.",
    why: "Les loyers encaissés, les charges payées et les échéances passent par la banque. Le rapprochement compare le relevé et ces écritures.",
    example: "Compte courant du bien en 512000. Un loyer encaissé le jour même débite 512000 et crédite le 706000. Un loyer non réglé reste chez le client jusqu’au règlement.",
    mistake: "Utiliser le 164 ou le 108 comme compte bancaire, ou changer le numéro alors que des écritures l’ont déjà utilisé.",
  },
  rapprochement: {
    label: "Rapprochement",
    what: "Lien entre un mouvement du relevé bancaire et une écriture, même compte, même montant, même exercice. Annuler ce lien demande un motif.",
    why: "Sans rapprochement, la banque de l’écran et le journal peuvent diverger. L’import CSV ne rapproche pas tout seul : vous confirmez chaque mouvement.",
    example: "Relevé du 05/03 : −800,00 €, rapproché avec l’échéance d’emprunt du même jour. Le mouvement passe de « À rapprocher » à « Rapproché ».",
    mistake: "Rapprocher deux fois le même mouvement, ou forcer un montant différent de l’écriture.",
  },
  journal: {
    label: "Journal",
    what: "Liste chronologique des écritures validées. Les codes proposés : AN à-nouveaux, BQ banque, VE ventes, AC achats, OD opérations diverses. Les brouillons n’entrent pas dans le journal, la balance ni le grand livre.",
    why: "C’est la piste d’audit. Le FEC reprend ces écritures validées, dans l’ordre prévu, hors centralisation.",
    example: "Loyer validé au journal VE, échéance au journal BQ ou OD selon la saisie, dotation au journal d’inventaire choisi.",
    mistake: "Chercher un brouillon dans le journal, ou valider une écriture déséquilibrée.",
  },
  brouillon: {
    label: "Brouillon",
    what: "Écriture enregistrée mais pas encore validée. Elle se modifie et se supprime. Elle est exclue des états, de la balance et du FEC. La validation lui donne un numéro définitif : plus de modification, seulement une extourne.",
    why: "Vous pouvez préparer une pièce, vérifier l’équilibre, puis valider. Un brouillon oublié fausse la centralisation et les à-nouveaux de l’exercice suivant.",
    example: "Nouvelle écriture, deux lignes débit et crédit égales, Enregistrer le brouillon, puis Valider. Le numéro affiché n’est plus « Brouillon ».",
    mistake: "Croire qu’un brouillon est déjà dans le résultat, ou tenter de modifier une écriture après validation.",
  },
  balance: {
    label: "Balance",
    what: "Tableau des comptes mouvementés par les écritures validées : totaux débit, crédit, et soldes. Elle doit être équilibrée (même total débit et crédit).",
    why: "C’est le contrôle d’ensemble avant les états et la centralisation. Une balance déséquilibrée signale une écriture incohérente, pas un écart fiscal.",
    example: "Compte 706000 : crédit 12 000 €. Compte 615000 : débit 400 €. Le pied de balance affiche les mêmes totaux des deux côtés.",
    mistake: "Y inclure les brouillons, ou « corriger » un écart en ajoutant une ligne sans pièce.",
  },
  "grand-livre": {
    label: "Grand livre",
    what: "Détail d’un compte : chaque ligne validée, avec le solde qui court. Solde positif : débiteur. Solde négatif : créditeur.",
    why: "La balance donne le total. Le grand livre montre quelles pièces l’ont construit, pour un 164, un 512 ou un 681.",
    example: "Grand livre du 164000 : déblocage ou reprise du capital, puis chaque remboursement de capital. Les intérêts n’y figurent pas s’ils sont au 661000.",
    mistake: "Lire le solde du 681 comme le montant déductible fiscalement, ou oublier de choisir le bon compte.",
  },
  inventaire: {
    label: "Inventaire",
    what: "Écriture manuelle justifiée, hors des opérations guidées : régularisation que vous savez calculer. La confirmation valide définitivement. La référence ne remplace pas l’archivage de la pièce.",
    why: "Certaines opérations de fin d’année ne passent pas par une recette ou une dotation automatique. Le motif et le calcul restent dans l’écriture.",
    example: "Charge constatée d’avance, deux lignes équilibrées, justification d’au moins 10 caractères, puis vérification avant validation.",
    mistake: "S’en servir pour une dotation déjà prévue à l’écran Immobilisations, ou valider sans le calcul dans la justification.",
  },
  "nature-compte": {
    label: "Nature du compte",
    what: "Classement du compte dans le plan : Actif, Dette, Capitaux, Charge ou Produit. Il vient du type enregistré. Il ne dit pas si le compte est utilisé : Activé ou Inactif est un autre état.",
    why: "Un emprunt activé reste une dette. Une charge désactivée reste une charge. Mélanger les deux fait croire que le plan comptable est faux.",
    example: "164000 emprunt : nature Dette, utilisation Activé. 615000 entretien désactivé : nature Charge, utilisation Inactif. 512000 banque : nature Actif, utilisation Activé.",
    mistake: "Lire Actif comme « compte activé », ou désactiver un compte pour en changer la nature. La désactivation retire le compte des saisies, elle ne le reclasse pas.",
  },
  bilan: {
    label: "Bilan",
    what: "Photo des comptes de bilan à la date de fin : actif, dettes, capitaux, et le résultat en cours. Il est calculé sur les écritures validées, brouillons exclus.",
    why: "Il montre ce que l’activité détient et doit (immeuble, banque, emprunt) avant la liasse 2033-A. Il ne clôture pas l’exercice.",
    example: "Actif : terrain 211, construction 213 nette du 281, banque 512. Passif : emprunt 164 et compte 108. Le résultat comptable relie le bilan et le compte de résultat.",
    mistake: "Y lire un prix de vente, ou croire que le bilan provisoire est déjà la case fiscale.",
  },
  "resultat-comptable": {
    label: "Résultat comptable",
    what: "Produits moins charges au journal validé, y compris la dotation 681. Le calcul fiscal ne réécrit jamais ce montant : il reste au ledger.",
    why: "La liasse part de ce résultat, puis applique le plafond d’amortissement et les réintégrations. Les deux chiffres peuvent différer.",
    example: "Loyers 12 000 €, charges hors dotation 4 000 €, dotation 681 de 9 000 € : résultat comptable −1 000 €. Le résultat fiscal peut être 0 € si la dotation est plafonnée.",
    mistake: "Modifier une écriture pour forcer le résultat fiscal, ou confondre ce solde avec le bénéfice imposable.",
  },
  produits: {
    label: "Produits",
    what: "Comptes de classe 7 de l’exercice validé. Pour la location, les loyers sont en pratique au 706000 (prestations de services) dans le plan proposé.",
    why: "Ils forment le point de départ de la capacité d’amortissement : loyers et autres produits, avant charges.",
    example: "Loyer mensuel 1 000 € comptabilisé au crédit du 706000. Douze mois : 12 000 € de produits, hors dépôt de garantie qui n’est pas un loyer.",
    mistake: "Passer un dépôt de garantie ou un apport en produit, ou oublier un loyer encore « non réglé » qui est pourtant exigible.",
  },
  charges: {
    label: "Charges",
    what: "Comptes de classe 6 validés : copropriété 614, entretien 615, assurance 616, intérêts 661, dotation 681, etc. La dotation est une charge comptable, pas automatiquement déductible en totalité.",
    why: "Le résultat comptable et la capacité fiscale n’utilisent pas les charges de la même façon. La capacité retire les charges autres que la dotation, puis plafonne le 681.",
    example: "Taxe foncière, assurance PNO et intérêts d’emprunt en charges. La dotation du bâtiment est au 681100, à part dans le calcul fiscal.",
    mistake: "Oublier la dotation dans les charges comptables, ou la juger déductible sans regarder le plafond.",
  },
  "loyers-charges": {
    label: "Loyers et charges",
    what: "Montants issus du ledger validé, hors écritures de centralisation. Ce sont les chiffres comptables, avant le retraitement fiscal (plafond, réintégrations, reports).",
    why: "Le calcul fiscal a besoin de cette base. Si le ledger change ensuite, le résultat fiscal devient obsolète et n’est plus le calcul en cours.",
    example: "Compte de résultat : produits 12 000 €, charges 13 000 € dont 9 000 € de 681. L’écran fiscal reprend ces totaux, puis calcule la capacité sur les charges hors 681.",
    mistake: "Lire ces montants comme le bénéfice à déclarer, ou les calculer à partir de brouillons.",
  },
  immobilisation: {
    label: "Immobilisation",
    what: "Bien durable inscrit à l’actif : terrain (211), construction (213), composants, mobilier (218400). Le terrain ne s’amortit pas. Les frais de notaire et d’agence proposés s’ajoutent au bâtiment, pas au terrain.",
    why: "L’entrée du bien et les dotations partent de ce registre. Une fois une immobilisation créée, le prix, le terrain et le bâtiment du bien sont figés : la correction se fait sur la fiche.",
    example: "Logement : terrain 40 000 € au 211000, construction au 213000 / 281300, four au 218400 / 281840 avec une justification de valeur et de durée.",
    mistake: "Passer le prix d’achat en charge de l’année, ou choisir un compte 28 comme compte d’immobilisation.",
  },
  terrain: {
    label: "Terrain",
    what: "Quote-part du prix qui ne s’use pas, compte 211. Aucun plan d’amortissement, aucun compte 281. La ventilation est manuelle : l’application ne la calcule pas.",
    why: "Amortir le terrain gonflerait la dotation et la capacité fiscale à tort. SoloLMNP refuse une base amortissable sur un terrain.",
    example: "Prix 240 000 € dont terrain 40 000 € saisi à part. Seuls 200 000 €, plus les frais imputés au bâtiment, peuvent entrer dans les composants amortissables.",
    mistake: "Laisser le terrain à 0 pour tout amortir, ou mettre le terrain dans le compte 213.",
  },
  composant: {
    label: "Composant",
    what: "Part du bâtiment amortie sur sa propre durée : gros œuvre, toiture, façade, électricité, plomberie, agencements dans l’aperçu proposé. La somme des composants doit couvrir exactement la base amortissable du bâtiment.",
    why: "Une seule durée pour tout le bâti mélange des éléments qui ne s’usent pas au même rythme. Les durées proposées se confirment : ce n’est pas un barème légal.",
    example: "Toiture sur une durée plus courte que le gros œuvre, montants dont le total égale la base du 213, avant le premier calcul de périodes.",
    mistake: "Ajouter un composant après avoir déjà comptabilisé des dotations, ou laisser un écart entre la somme des composants et la base.",
  },
  amortissement: {
    label: "Amortissement",
    what: "Répartition linéaire, en mois, du coût du bâti, des composants et du mobilier. Le terrain est exclu. Les durées proposées se confirment : ce n’est pas un barème légal. La dotation comptable (681) peut dépasser la part déductible : l’excédent se reporte, il n’est pas perdu.",
    why: "Au réel, le coût du logement s’étale sur la durée d’utilisation. La déduction fiscale, elle, ne peut pas dépasser les loyers diminués des autres charges déductibles.",
    example: "Base amortissable 200 000 € ventilée en composants. Une cuisine sur 15 ans n’a pas la même annuité que le gros œuvre. Le mobilier se suit à part, 218400 et 281840.",
    mistake: "Amortir le terrain, prendre la dotation comptable comme montant déductible, ou confondre cet amortissement avec le tableau de l’emprunt.",
  },
  dotation: {
    label: "Dotation",
    what: "Charge d’amortissement d’une période, calculée en jours calendaires sur la base du composant ou du bien. La comptabiliser crée l’écriture (souvent au 31/12). Le calcul des périodes n’écrit rien tant que vous ne comptabilisez pas.",
    why: "Sans dotation validée, le 681 reste vide et le résultat comptable ignore l’usure. Après comptabilisation, la valeur, la durée et les comptes de la fiche sont figés.",
    example: "Exercice 2026, Calculer les périodes, puis Comptabiliser la dotation au 31/12/2026 avec une pièce d’inventaire. L’écriture débite le 681 et crédite le 281.",
    mistake: "Comptabiliser avant le 31/12 si la date de dotation n’est pas atteinte, modifier la durée après coup sans extourner, ou relancer un lot sans regarder quelles dotations sont déjà passées. Le bouton se verrouille le temps du traitement : un double clic ne crée pas une seconde écriture.",
  },
  "compte-681": {
    label: "Compte 681",
    what: "Dotations aux amortissements (681100 dans le plan proposé), contrepartie des comptes 281. C’est la charge comptable de l’année. Elle ne se réintègre pas dans le formulaire de quote-part : le plafond fiscal la traite à part.",
    why: "Le résultat comptable inclut toute la dotation. Le résultat fiscal n’en déduit que la part qui tient dans la capacité, puis reporte le reste.",
    example: "Dotation 4 000 € : débit 681100, crédit 281300. Si la capacité n’est que de 2 500 €, la comptabilité garde 4 000 € et le fiscal n’en déduit que 2 500 €.",
    mistake: "Croire que tout le 681 est déductible, le saisir en 615, ou le réintégrer comme une charge privée.",
  },
  vnc: {
    label: "VNC",
    what: "Valeur nette comptable de la base amortissable : base du plan − amortissements cumulés. Ce n’est ni le prix de revente ni la part déductible de l’année. Le terrain n’a pas de plan : il n’a pas cette VNC.",
    why: "La colonne « VNC de la base » montre ce qu’il reste à amortir sur le composant après les dotations déjà calculées. Elle aide à voir qu’on ne dépasse pas la base.",
    example: "Base 200 000 €, cumul des dotations 8 000 € : VNC de la base 192 000 €. Une dotation de plus diminue cette VNC, pas le prix du marché.",
    mistake: "La prendre pour une valeur vénale, ou pour le montant à reporter en case fiscale.",
  },
  plafond: {
    label: "Plafond",
    what: "Limite de l’amortissement déductible de l’année. L’amortissement déductible ne peut pas dépasser les loyers diminués des autres charges déductibles. L’excédent est reporté, pas perdu.",
    why: "Au réel LMNP, la dotation ne doit pas créer ni augmenter le déficit par elle-même. Le surplus attend une année où la capacité suffit. Les millésimes restent en recherche : le chiffre se contrôle avant toute recopie.",
    example: "Loyers 12 000 €, autres charges 4 000 € : plafond 8 000 €. Dotation comptable 9 000 € : 8 000 € au plus sont déductibles cette année, 1 000 € partent en report.",
    mistake: "Déduire toute la dotation 681, ou croire que le surplus est perdu.",
  },
  capacite: {
    label: "Capacité",
    what: "Loyers et produits, moins les charges déductibles hors dotation, plus les réintégrations. On déduit d’abord l’amortissement de l’année dans cette limite, puis les reports d’amortissement antérieurs (du plus ancien au plus récent) sur le reste.",
    why: "C’est le maximum d’amortissement fiscalement déductible cette année. Au-delà, le surplus est reporté. Ce n’est pas une case à envoyer telle quelle : le millésime est en recherche.",
    example: "Capacité 8 000 €, dotation de l’année 6 000 €, report ancien 3 000 € : on déduit 6 000 € puis 2 000 € de report. Il reste 1 000 € de report pour plus tard.",
    mistake: "Imputer les vieux reports avant la dotation de l’année, ou augmenter la capacité en passant une charge privée sans la réintégrer.",
  },
  "report-amortissement": {
    label: "Report d’amortissement",
    what: "Part de dotation non déduite faute de capacité, suivie par année d’origine. Elle se reprend plus tard, dans l’ordre d’ancienneté, s’il reste de la capacité après la dotation de l’année. Elle n’est pas perdue au bout de 10 ans : ce délai concerne le déficit, pas ce stock.",
    why: "L’état de suivi (art. 39 C dans la liasse de travail) conserve l’ouverture, le repris et le reste. Vous le gardez avec la liasse. Le montant n’est pas une base de déclaration tant que le millésime est en recherche.",
    example: "2026 : 1 000 € non déduits. 2027 : capacité restante 400 € après la dotation de 2027 : on reprend 400 €, il reste 600 €.",
    mistake: "Le confondre avec le déficit LMNP (10 ans, hors salaire), ou le déduire en plus de la capacité.",
  },
  deficit: {
    label: "Déficit",
    what: "Résultat fiscal négatif de l’activité LMNP. Il se reporte sur les bénéfices LMNP des 10 années suivantes. Il ne diminue pas les salaires ni les autres revenus du foyer.",
    why: "Le plafond d’amortissement vise en pratique un résultat fiscal proche de 0 €. Un déficit peut quand même venir des charges autres que la dotation. La case de rappel côté foyer est 5NY, à contrôler sur la déclaration.",
    example: "Loyers 10 000 €, charges hors dotation 12 000 €, dotation plafonnée à 0 : déficit 2 000 €, reportable sur les LMNP suivants, pas sur le salaire.",
    mistake: "L’imputer sur le revenu global, ou le mélanger avec le stock d’amortissement non déduit.",
  },
  reintegration: {
    label: "Réintégration",
    what: "Part d’une charge comptable qui n’est pas déductible (usage privé, par exemple). L’écriture du journal reste entière. Seul le calcul fiscal ajoute cette part. Les comptes 681 ne se gèrent pas ici.",
    why: "Une charge privée abaisserait à tort le résultat fiscal et augmenterait la capacité si on l’ignorait. La réintégration la neutralise. Chaque ligne demande un compte de charge déjà au ledger, un montant plafonné par ce solde, et une justification d’au moins 10 caractères.",
    example: "Assurance 600 € dont 100 € d’usage personnel : réintégration 100 € sur le compte 616. La comptabilité garde 600 €. La capacité remonte de 100 €.",
    mistake: "Réintégrer le 681, ou modifier l’écriture comptable au lieu de saisir la quote-part.",
  },
  "resultat-fiscal": {
    label: "Résultat fiscal",
    what: "Résultat de l’activité après plafond d’amortissement, réintégrations et reports. La cible usuelle au réel est 0 €, pas un bénéfice BIC supplémentaire via cette activité. Il peut différer du résultat comptable. Le calcul enregistré reste en recherche : ce n’est pas une base de déclaration et rien n’est envoyé.",
    why: "C’est le montant que la liasse de travail propose de recopier, après contrôle des cases. S’il ne correspond plus au ledger, il est obsolète et le pré-contrôle le traite comme absent.",
    example: "Résultat comptable −1 000 € à cause d’une dotation trop forte pour la capacité. Résultat fiscal 0 €, et 1 000 € d’amortissement reporté.",
    mistake: "Le déclarer sans relire le formulaire, ou garder un ancien calcul après avoir corrigé une écriture.",
  },
  "pre-controle": {
    label: "Pré-contrôle",
    what: "Contrôle avant clôture : erreurs bloquantes et avertissements. Chaque avertissement affiché se coche. Un nouveau pré-contrôle décoche tout. Sans calcul fiscal à jour, il renvoie au calcul.",
    why: "Il empêche de figer un exercice incomplet (SIREN, calcul absent ou obsolète, points bloquants). Accuser un avertissement ne le fait pas disparaître du dossier : vous confirmez l’avoir lu.",
    example: "Calcul fiscal à jour, Lancer le pré-contrôle, cocher l’avertissement affiché, puis Accuser et préparer la clôture.",
    mistake: "Préparer la clôture sans avoir coché les avertissements du dernier contrôle, ou ignorer un lien qui ramène au calcul.",
  },
  cloture: {
    label: "Clôture",
    what: "Gel de l’exercice après pré-contrôle et confirmation. Les écritures ne se modifient plus. Les sorties peuvent alors passer en finale si leurs autres conditions sont réunies. La centralisation, faite avant, ne suffit pas. Une liasse encore en recherche reste un travail de recherche, même après la clôture.",
    why: "Le FEC et le dossier de contrôle exigents partent d’un exercice clôturé. Clôturer ne télétransmet rien.",
    example: "Pré-contrôle sans erreur, avertissements cochés, Accuser et préparer, puis Confirmer la clôture. Le statut de l’exercice devient clôturé.",
    mistake: "Confondre centralisation et clôture, ou clôturer pour « envoyer » la liasse.",
  },
  reouverture: {
    label: "Réouverture",
    what: "Retour d’un exercice clôturé à l’état ouvert, avec un motif d’au moins 10 caractères et la confirmation ROUVRIR. Les calculs fiscaux et le snapshot liasse/FEC courants sont invalidés. Il faut recalculer, relancer le pré-contrôle et reclôturer. Les anciennes preuves restent consultables.",
    why: "Une erreur découverte après clôture ne se corrige pas en silence. L’audit garde le motif. Rien n’est envoyé ni retiré chez l’administration : l’application ne transmet pas.",
    example: "Dotation oubliée : Réouvrir l’exercice, motif explicite, ROUVRIR, corriger, recalculer, pré-contrôle, reclôturer, puis regénérer les sorties.",
    mistake: "Rouvrir sans motif réel, ou recopier encore l’ancienne liasse après l’invalidation.",
  },
  "import-csv": {
    label: "Import CSV",
    what: "Chargement d’un relevé, de recettes et dépenses, ou d’un échéancier depuis un fichier. Le modèle français nomme les colonnes en clair. Vous associez ensuite celles de votre fichier. Rien n’est enregistré avant la confirmation de l’aperçu.",
    why: "Un export de banque ou de tableur n’utilise pas les noms techniques du logiciel. L’aperçu sépare les lignes valides, les doublons, les avertissements et les erreurs. Un rejet n’efface pas une écriture déjà validée.",
    example: "Modèle téléchargé, dates 05/03/2026, montants 800,00. Une cellule « abc » dans Montant est une erreur : la correction attendue demande un montant au centime. Les autres lignes peuvent être importées. Le fichier des rejets se corrige puis se recharge.",
    mistake: "Laisser des noms techniques sans les associer, mélanger deux prêts dans le même fichier, ou confirmer un montant déjà comptabilisé avec une autre ventilation.",
  },
  justificatif: {
    label: "Justificatif",
    what: "Pièce déposée (PDF, JPEG ou PNG) qui appuie une écriture : facture, quittance ou avis. Le fichier est renommé, daté, mesuré et résumé par une empreinte SHA-256. Le relier n’écrit rien dans l’écriture.",
    why: "En cas de contrôle, la pièce doit se retrouver à côté de l’écriture. L’empreinte montre que le fichier n’a pas été remplacé en silence depuis le dépôt.",
    example: "Quittance PDF liée à l’écriture 2026-000012 du 05/03/2026, pièce LOY-2026-03. La liste affiche le nom, la date, le type, la taille et l’empreinte.",
    mistake: "Saisir un identifiant interne de base, ou déposer un fichier dont le contenu n’est pas un PDF, un JPEG ou un PNG.",
  },
  sauvegarde: {
    label: "Sauvegarde",
    what: "Archive locale de la base et des justificatifs, avec la date, la taille, la version de l’application, la révision du schéma et une empreinte SHA-256. Elle ne contient pas les secrets d’environnement.",
    why: "Une copie datée permet de revenir en arrière si la base est abîmée. Le contrôle d’intégrité dit si l’archive est encore lisible et conforme à son empreinte.",
    example: "Après la clôture, Créer une sauvegarde. La liste montre la date, la taille, les versions, l’empreinte et le résultat du dernier contrôle.",
    mistake: "Noter un nom de fichier à la main, ou croire qu’une sauvegarde jamais contrôlée est forcément intacte.",
  },
  restauration: {
    label: "Restauration",
    what: "Reprise d’une sauvegarde connue de la liste, à la place de la base en service. L’aperçu indique la date et les nombres d’écritures et d’exercices. Il faut saisir RESTAURER. Une copie de l’état actuel est prise avant.",
    why: "Revenir en arrière retire les saisies faites après la sauvegarde choisie. La confirmation et la copie préalable évitent un remplacement accidentel. Les écritures validées ne se corrigent pas une à une.",
    example: "Aperçu : 12 écritures et 1 exercice à la place de 14 et 1. Saisir RESTAURER. La copie d’avant restauration apparaît dans la liste.",
    mistake: "Confirmer sans lire les nombres, ou restaurer pour corriger une seule écriture validée au lieu de l’extourner.",
  },
  empreinte: {
    label: "Empreinte",
    what: "Condensé SHA-256 du fichier. La même suite de caractères désigne le même contenu. Elle est affichée pour chaque justificatif et chaque sauvegarde.",
    why: "Elle permet de vérifier qu’une pièce ou une archive n’a pas changé depuis son enregistrement ou son dernier contrôle d’intégrité.",
    example: "Une quittance déposée affiche 64 caractères hexadécimaux. Le même fichier déposé de nouveau produit la même empreinte.",
    mistake: "Comparer deux empreintes coupées trop court, ou les prendre pour un numéro d’écriture.",
  },
  ecriture: {
    label: "Écriture",
    what: "Ligne de journal datée, avec un numéro lorsqu’elle est validée, une date et une pièce. Un brouillon n’a pas encore de numéro. La validation fige l’écriture : on ne la réécrit pas.",
    why: "Le justificatif se rattache à cette écriture par son numéro, sa date et sa pièce. Ce n’est pas un identifiant interne de la base.",
    example: "2026-000012 · 05/03/2026 · LOY-2026-03. Le sélecteur retrouve cette écriture avec ces trois informations.",
    mistake: "Chercher l’écriture par un numéro technique de base, ou modifier une écriture validée au lieu de l’extourner.",
  },
  cession: {
    label: "Cession et plus-values",
    what: "Vente du bien, TVA et plus-values sont hors de cet outil : les écrans les signalent comme désactivés. Leur présence bloque la recopie. SoloLMNP ne calcule pas la plus-value et n’envoie rien.",
    why: "Le parcours couvre la location longue durée au réel, pas la cession. Un bien vendu dans l’exercice ne se traite pas comme une simple dotation.",
    example: "Message de blocage sur la liasse de travail si une immobilisation est sortie. Vous traitez la plus-value en dehors de SoloLMNP, avec le formulaire de l’année.",
    mistake: "Forcer une écriture de vente dans l’inventaire pour « finir » la liasse, ou amortir l’année entière après la sortie.",
  },
} as const satisfies Record<string, GlossaryEntry>;

export type GlossaryId = keyof typeof GLOSSARY;

export const GLOSSARY_IDS = Object.keys(GLOSSARY) as GlossaryId[];

export function isGlossaryId(value: string): value is GlossaryId {
  return Object.prototype.hasOwnProperty.call(GLOSSARY, value);
}

export function glossaryEntry(id: GlossaryId): GlossaryEntry & { id: GlossaryId } {
  return { id, ...GLOSSARY[id] };
}
