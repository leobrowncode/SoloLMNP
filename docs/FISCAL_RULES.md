# Registre des règles fiscales

Dernière vérification documentaire des règles de calcul : **30 octobre 2026**.
Les fichiers `fiscal/2025/rules.yaml` et `fiscal/2026/rules.yaml` sont en
`research-2` et restent `research_only`. `declarable` y est `false`. Aucun
millésime n’est déclarable : `fiscal/2025/validation.json` et
`fiscal/2026/validation.json` restent `research_only`. Consulter un texte et
confirmer sa référence ne valide pas une déclaration.

Le résultat comptable, les réintégrations et l’amortissement fiscalement
utilisable sont trois montants distincts. Le stock créé reste dans
`depreciation_carry_forward` ou `tax_loss_carry_forward`. Chaque création,
utilisation ou expiration est une ligne `carry_forward_event` du calcul qui
la constate. Un recalcul ou une réouverture invalide ce calcul : les lignes
cessent de compter, et le calcul suivant les réécrit. L’amortissement non
déduit (art. 39 C, II) n’expire pas. Le déficit LMNP (art. 156, I, 1° ter)
expire au-delà des dix années suivantes.

Deux lectures demandées à tort ne sont pas appliquées, et le moteur le dit :

- L’article 156, I, 1° bis (déficits BIC sans participation personnelle,
  report de six ans) exclut expressément les déficits de location meublée de
  locaux d’habitation. La règle exécutée est le 1° ter.
- Les amortissements réputés différés de l’ancien article 39, 1-2° et de
  l’ancien second alinéa de l’article 39 B sont supprimés pour les exercices
  ouverts à compter du 1er janvier 2004. L’article 39 B en vigueur impose un
  amortissement minimal linéaire. Le stock LMNP suivi ici est celui de
  l’article 39 C, II, pas un ARD.

## Statuts affichés : Recherche, Provisoire, Déclarable

Une seule fonction, `app.domain.fiscal.output_status.classify`, décide le statut
du calcul, de la liasse, du PDF, du tableur, du dossier de contrôle et du
pré-contrôle. L’écran ne fait que l’afficher. Le mot « Prête à recopier » n’est
écrit que si ce statut est Déclarable.

| Statut | Condition exacte |
|---|---|
| Recherche | `fiscal/<millésime>/validation.json` n’est pas une attestation effective. C’est le cas si le fichier manque, est illisible, ou si l’un de ces points manque : `status` = `validated`, `declarable` = `true`, `version` non vide, `rules_version` non vide, `official_source.reference` non vide, `official_source.url` en `https://`, `validated_on` au format `AAAA-MM-JJ`, `scope.activity`, `scope.regime`, et `scope.excluded` (liste non vide). Une feuille dont les contrôles de cases sont satisfaits reste Recherche. |
| Provisoire | L’attestation est complète, mais elle ne couvre pas la sortie : `rules_version` diffère de `version` dans `fiscal/<millésime>/rules.yaml`, ou la liasse a une erreur, une case hors registre, ou un avertissement bloquant (`IMMOBILISATIONS_ECART`, `EFFECTIFS`, `RESULTAT_MIXTE`, `CLASSEMENT_INCOMPLET`, `SIREN_MANQUANT`). |
| Déclarable | L’attestation est complète, `rules_version` est celui du fichier de règles, et la liasse n’a ni erreur ni avertissement bloquant. Seule cette sortie peut afficher « Prête à recopier ». |

Le calcul stocké garde la colonne `status = research_only` (contrainte de base).
Le statut affiché est `output_status`. Pour le calcul, les portes de cases ne
s’appliquent pas : un millésime effectivement validé y est Déclarable, un
millésime validé mais dont `rules_version` a bougé y est Provisoire. La liasse
peut donc être Provisoire alors que le calcul est Déclarable. C’est le statut
de la liasse qui autorise la recopie.

Pour valider un millésime, remplacer `fiscal/<millésime>/validation.json` dans
une revue (pas d’écran) : les champs du tableau, plus `rules_version` égal à la
`version` courante de `rules.yaml`. Tout changement de règles renvoie la sortie
en Provisoire tant que ce fichier n’est pas réaligné. Les millésimes 2025 et
2026 ne sont pas validés.

### Posture d’export

`exports.liasse`, `exports.pdf`, `exports.fec` et `exports.archive` portent
chacun `posture` (`provisoire`, `bloquee` ou `finale`), `label` (Provisoire,
Bloquée, Finale) et `download`. `GET /api/filing/years/{id}/exports` expose
aussi les prérequis. Un téléchargement dont `download` est faux répond `409`
avec le contrat d’erreur (`code`, `message`, `action`, et `issues` s’il y en
a plusieurs). L’écran n’utilise pas de lien direct vers le fichier : le refus
reste dans la page, avec le lien d’action.

- Liasse et PDF : Bloquée si les portes de cases échouent ou si le calcul
  fiscal n’existe pas ; Finale seulement si le statut est Déclarable et
  l’exercice est clôturé ; sinon Provisoire. Une sortie Provisoire se
  télécharge, marquée Provisoire. Une sortie Bloquée ne se télécharge pas.
- FEC et dossier de contrôle : Bloquée tant que l’exercice n’est pas clôturé,
  sans SIREN, ou si le FEC a une erreur ; Finale quand l’exercice est clôturé
  et le FEC n’a pas d’erreur. Le FEC est un fichier comptable : sa posture
  Finale n’exige pas un millésime Déclarable.

### Statut dossier

Le bandeau affiche un statut métier, distinct du schéma SQLite. `app.domain.dossier.classify_dossier` le déduit de l’état de clôture (`OPEN`, `READY_TO_CLOSE`, `CLOSED`), du `output_status` fiscal et des postures d’export déjà calculées. `GET /api/status` le renvoie dans `dossier` pour l’exercice ouvert le plus récent, ou le dernier exercice si tous sont clôturés. Sans exercice, ou sans calcul fiscal, le statut est **Incomplet**. Une liasse ou un PDF **Bloquée** donne **Bloqué** ; un FEC bloqué avant la clôture ne compte pas, il est attendu. Après clôture, une sortie encore **Bloquée** laisse le dossier **Bloqué**, sinon **Clôturé**. Une feuille produite et non bloquée, exercice encore ouvert ou prêt à clôturer, est **Prêt à vérifier**.

`dossier.vintage_status` reste `research_only`. Un `output_status` Déclarable ne crée pas de cinquième libellé : le dossier s’arrête à Prêt à vérifier ou Clôturé. **Stockage opérationnel** n’est affiché que dans le diagnostic technique de la vue d’ensemble, et seulement tant que la dernière lecture de `/api/status` a réussi. « Aucun envoi » reste à côté des sorties fiscales.

## Références consultées et portée de la vérification

Les liens ci-dessous ont été ouverts et leurs titres et versions contrôlés le
15/09/2026. Une date de publication BOFiP n'est pas, à elle seule, la date
d'effet d'une règle légale. L'applicabilité doit être établie séparément pour
chaque exercice et chaque millésime de formulaires.

| Rule ID | Principe identifié et référence précise | Source officielle consultée | Application / tests | État restant |
|---|---|---|---|---|
| RULE-LMNP-BIC-001 | Périmètre produit : activité déclarée LMNP. Le LMP et les seuils du foyer (CGI art. 155 IV) sont hors outil. | Décision de périmètre, pas un calcul fiscal. | Aucun seuil ni comparaison de revenus. | Le LMP n'est pas implémenté. Cette règle ne bloque plus les calculs LMNP. |
| RULE-LMNP-DEPRECIATION-LIMIT-001 | Pour une personne physique, l’amortissement déductible est la différence positive entre les loyers acquis et les autres charges (CGI art. 39 C, II-2). La fraction écartée se déduit les années suivantes dans la même limite (II-3). Elle ne crée ni n’augmente un déficit. Pas de délai de dix ans dans l’article ni dans l’état de suivi BOI-FORM-000038. | [CGI art. 39 C depuis le 01/01/2015](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000029355753/2015-01-01) ; [BOI-BIC-AMT-20-40-10-20 du 01/03/2017](https://bofip.impots.gouv.fr/bofip/4527-PGP.html/identifiant=BOI-BIC-AMT-20-40-10-20-20170301) ; [BOI-FORM-000038](https://bofip.impots.gouv.fr/bofip/4547-PGP.html/identifiant=BOI-FORM-000038-20130826). Textes relus le 30/10/2026 (la page Legifrance brute a renvoyé un contrôle anti-robot ; le libellé utilisé est celui renvoyé avec l’URL officielle, recoupé avec le BOFiP récupéré en entier). | Exemple BOFiP 2 500 / 1 000 / 3 050 → 1 500 déductibles et 1 550 reportés (`test_fiscal_engine`). FIFO des exercices clôturés. | Cession, cessation et ventilation par bien non calculées. Ce stock n’est pas un ARD. |
| RULE-LMNP-LOSS-001 | Déficits LMNP non imputables sur le revenu global. Report sur les revenus de la même activité pendant les dix années suivantes. CGI art. 156, I, 1° ter, version en vigueur depuis le 01/07/2026. BOI-BIC-DEF-20-20, § 110-120. | [CGI art. 156, LEGIARTI000053544806](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000053544806) ; [BOI-BIC-DEF-20-20](https://bofip.impots.gouv.fr/bofip/2011-PGP.html/identifiant=BOI-BIC-DEF-20-20-20120912) ; [notice DGFiP](https://www.impots.gouv.fr/particulier/location-meublee) | Déficit séparé ; FIFO ; expiration après dix années (`test_fiscal_engine`, `test_fiscal_carryforward`). Consulté le 30/10/2026. | Passage LMP / LMNP et report en arrière non calculés. |
| RULE-BLOCKED-156-BIS-001 | Le 1° bis du I de l’art. 156 (six ans, BIC sans participation personnelle) ne s’applique pas à la location meublée d’habitation. Le texte l’exclut. | Même URL que l’art. 156, consultée le 30/10/2026. | Règle bloquée, jamais imputée. Motif renvoyé par `GET /api/fiscal/vintages`. | Ne pas coder un report de six ans pour un LMNP. |
| RULE-BLOCKED-ARD-39B-001 | ARD abolis pour les exercices ouverts à compter du 01/01/2004 (LF 2004, art. 89). L’art. 39 B actuel est l’amortissement minimal linéaire. | [BOI-BIC-AMT-10-50 du 04/01/2017](https://bofip.impots.gouv.fr/bofip/4667-PGP.html/identifiant=BOI-BIC-AMT-10-50-20170104), consulté le 30/10/2026. | Règle bloquée. Le stock exécuté est l’art. 39 C, II. | Ne pas reconstituer d’ARD. |
| RULE-BLOCKED-CESSION-001 | Cession et cessation non calculées. L’art. 39 C, II prévoit un sort propre du stock à la cessation. | [CGI art. 39 C](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000029355753/2015-01-01), consulté le 30/10/2026. | Mouvement 675 ou 775, ou immobilisation sortie : `FISCAL_RULE_BLOCKED`. | Le calcul de cessation reste à écrire. |
| RULE-BLOCKED-TVA-001 | La TVA n’est pas un loyer ni une charge de ce moteur. | [Notice DGFiP location meublée](https://www.impots.gouv.fr/particulier/location-meublee), consultée le 30/10/2026. | Mouvement 445 : `FISCAL_RULE_BLOCKED`. | Pas de régime de TVA. |
| RULE-BLOCKED-PLUS-VALUE-001 | Plus-values et moins-values non calculées. | Même art. 39 C, consulté le 30/10/2026. | Même déclencheur que la cession (675, 775, sortie). | Pas de formulaire de plus-value. |
| RULE-BLOCKED-LAND-AUTO-001 | Pas d’estimation du prix du sol. | [BOI-BIC-AMT-10-20 du 05/08/2026](https://bofip.impots.gouv.fr/bofip/4590-PGP.html/identifiant=BOI-BIC-AMT-10-20-20260805), URL déjà contrôlée le 02/10/2026. | Règle bloquée, listée par l’API. La saisie manuelle reste la règle exécutable du terrain. | Ventilation automatique non écrite. |
| RULE-LAND-NON-DEPRECIABLE-001 | Le prix du sol est exclu de la base amortissable des constructions ; BOI-BIC-AMT-10-20, I-A § 10 et I-S § 230 ; application LMNP confirmée au BOI-BIC-CHAMP-40-20 § 58. | [Publication BOFiP du 05/08/2026](https://bofip.impots.gouv.fr/bofip/4590-PGP.html/identifiant=BOI-BIC-AMT-10-20-20260805) ; [BOI LMNP du 14/02/2024](https://bofip.impots.gouv.fr/bofip/3610-PGP.html/identifiant=BOI-BIC-CHAMP-40-20-20240214) | Invariant registre + échec fiscal si base amortissable terrain. | Ventilation manuelle utilisateur ; aucune estimation automatique. |
| RULE-FISCAL-VINTAGE-IMMUTABLE-001 | Les versions de calcul utilisées historiquement doivent rester reproductibles avec leurs empreintes. | Politique interne de reproductibilité ; aucune portée normative fiscale. | Le test actuel distingue les fichiers de recherche 2025/2026. | Ajouter des résultats chiffrés figés et tests d'empreintes avec les moteurs futurs. |

Les associations erronées ou non vérifiées entre numéros d'article, identifiants
BOFiP et URL présentes dans l'inventaire initial ont été retirées. Les articles
155 et 156 ne partagent pas une même URL de référence. Le lien vers l'article
156 contenu dans le BOFiP consulté mène à une version historique 2023-2024 :
il ne constitue pas une vérification du texte consolidé pour 2025 ou 2026.

## Vérifications nécessaires avant activation d'une règle

- Conserver Rule ID, version, période d'effet, millésime des formulaires,
  source primaire et référence de paragraphe, date de consultation et empreinte.
- Décrire l'interprétation retenue, les cas inclus/exclus, puis associer le code
  et des tests chiffrés relus. Les scénarios A à J actuels sont un catalogue de
  futurs tests ; ils ne prouvent aucun montant fiscal.
- Vérifier les versions Legifrance applicables avant de transformer les
  principes documentés en règles exécutables. Les règles historiques ne sont
  pas modifiées silencieusement.

## Incertitudes bloquantes ciblées

Ordre des reports MVP : livré (FIFO). Restent hors MVP / bloquants hors chemin typique :
cession/cessation ; TVA/parahôtellerie ; plus-values ; frais d'acquisition ;
ventilation automatique terrain/bâtiment ; durées et composants ; CFE.
Les notices/formulaires 2031/2033 millésime 2025 sont archivés dans
`fiscal/2025/sources/` et les cases MVP listées dans `forms/cases.yaml`.
Le millésime 2026 et la 2042-C-PRO restent hors archive déclarable.
