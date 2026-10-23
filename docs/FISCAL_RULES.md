# Registre des règles fiscales

Dernière vérification documentaire : **2 octobre 2026** (sources formulaires 2025
archivées ; règles BOFiP encore celles du 16/09/2026). Les fichiers
`fiscal/2025/rules.yaml` et `fiscal/2026/rules.yaml` restent en recherche
(`research_only` pour le calcul stocké). Quatre règles sont exécutables en code avec tests. L’ordre MVP
de consommation des reports (FIFO, exercices clôturés ; déficits horizon 10 ans)
est implémenté et golden-testé. La liasse BIC 2025 peut être `ready` sans que le
fichier de règles change de statut. Consulter un
texte et confirmer sa référence ne valide pas une déclaration.

## Références consultées et portée de la vérification

Les liens ci-dessous ont été ouverts et leurs titres et versions contrôlés le
15/09/2026. Une date de publication BOFiP n'est pas, à elle seule, la date
d'effet d'une règle légale. L'applicabilité doit être établie séparément pour
chaque exercice et chaque millésime de formulaires.

| Rule ID | Principe identifié et référence précise | Source officielle consultée | Application / tests | État restant |
|---|---|---|---|---|
| RULE-LMNP-BIC-001 | Périmètre produit : activité déclarée LMNP. Le LMP et les seuils du foyer (CGI art. 155 IV) sont hors outil. | Décision de périmètre, pas un calcul fiscal. | Aucun seuil ni comparaison de revenus. | Le LMP n'est pas implémenté. Cette règle ne bloque plus les calculs LMNP. |
| RULE-LMNP-DEPRECIATION-LIMIT-001 | Limitation de la déduction fiscale pour les personnes physiques, distincte de la dotation comptabilisée ; CGI art. 39 C II-2 et II-3 ; BOI-BIC-AMT-20-40-10-20, I-B § 20 et II § 40-100. | [CGI art. 39 C, version en vigueur depuis le 01/01/2015](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000029355753/2015-01-01) ; [BOFiP, publication du 01/03/2017](https://bofip.impots.gouv.fr/bofip/4527-PGP.html/identifiant=BOI-BIC-AMT-20-40-10-20-20170301) | Plafond + stock N ; reprise FIFO des reports d’exercices **clôturés** sur capacité résiduelle (`test_fiscal_carryforward`). | Cession/cessation et ventilation multi-biens hors MVP. |
| RULE-LMNP-LOSS-001 | Déficits LMNP non imputables sur le revenu global ; report sur revenus LMNP des dix années suivantes sous les conditions de qualification décrites ; BOI-BIC-CHAMP-40-20, III-A § 240-250, renvoyant au CGI art. 156 I 1° ter. | [BOI-BIC-CHAMP-40-20, publication du 14/02/2024](https://bofip.impots.gouv.fr/bofip/3610-PGP.html/identifiant=BOI-BIC-CHAMP-40-20-20240214) | Déficit N séparé ; imputation FIFO sur résultat positif N+1, horizon 10 ans, hors revenu global (`test_fiscal_carryforward`). | Changements de statut LMP/LMNP et report en arrière hors MVP. |
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
