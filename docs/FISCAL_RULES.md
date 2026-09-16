# Registre des règles fiscales

Dernière vérification documentaire : **15 septembre 2026**. Le registre et les
fichiers `fiscal/2025/rules.yaml` et `fiscal/2026/rules.yaml` restent en recherche
(`research_only`). Consulter un texte et confirmer sa référence ne valide pas
une implémentation ni une déclaration. Aucun moteur fiscal n'est implémenté.

## Références consultées et portée de la vérification

Les liens ci-dessous ont été ouverts et leurs titres et versions contrôlés le
15/09/2026. Une date de publication BOFiP n'est pas, à elle seule, la date
d'effet d'une règle légale. L'applicabilité doit être établie séparément pour
chaque exercice et chaque millésime de formulaires.

| Rule ID | Principe identifié et référence précise | Source officielle consultée | Application / tests | État restant |
|---|---|---|---|---|
| RULE-LMNP-BIC-001 | Champ BIC et qualification au niveau du foyer ; CGI art. 155 IV, BOI-BIC-CHAMP-40-10, notamment II § 40-50. | [BOI-BIC-CHAMP-40-10, publication du 15/04/2026](https://bofip.impots.gouv.fr/bofip/3615-PGP.html/identifiant=BOI-BIC-CHAMP-40-10-20260415) | Aucun calcul ; scénario de qualification à compléter. | Version légale consolidée de l'art. 155 et applicabilité historique 2025 à vérifier. Ne pas appliquer automatiquement la publication 2026 à 2025. |
| RULE-LMNP-DEPRECIATION-LIMIT-001 | Limitation de la déduction fiscale pour les personnes physiques, distincte de la dotation comptabilisée ; CGI art. 39 C II-2 et II-3 ; BOI-BIC-AMT-20-40-10-20, I-B § 20 et II § 40-100. | [CGI art. 39 C, version en vigueur depuis le 01/01/2015](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000029355753/2015-01-01) ; [BOFiP, publication du 01/03/2017](https://bofip.impots.gouv.fr/bofip/4527-PGP.html/identifiant=BOI-BIC-AMT-20-40-10-20-20170301) | Aucun calcul ; scénario C à chiffrer et valider. | Assiette des loyers/charges, ventilation entre biens, ordre d'utilisation des reports et cas de cession/cessation à spécifier avant P6. |
| RULE-LMNP-LOSS-001 | Déficits LMNP non imputables sur le revenu global ; report sur revenus LMNP des dix années suivantes sous les conditions de qualification décrites ; BOI-BIC-CHAMP-40-20, III-A § 240-250, renvoyant au CGI art. 156 I 1° ter. | [BOI-BIC-CHAMP-40-20, publication du 14/02/2024](https://bofip.impots.gouv.fr/bofip/3610-PGP.html/identifiant=BOI-BIC-CHAMP-40-20-20240214) | Aucun calcul ni expiration automatique ; scénario D à chiffrer et valider. | Version consolidée de l'art. 156 applicable à chaque exercice, ordre d'imputation et changements de statut à vérifier. |
| RULE-LAND-NON-DEPRECIABLE-001 | Le prix du sol est exclu de la base amortissable des constructions ; BOI-BIC-AMT-10-20, I-A § 10 et I-S § 230. | [Publication du 21/12/2022, terminée le 05/08/2026](https://bofip.impots.gouv.fr/bofip/4590-PGP.html/identifiant=BOI-BIC-AMT-10-20-20221221) ; [publication du 05/08/2026](https://bofip.impots.gouv.fr/bofip/4590-PGP.html/identifiant=BOI-BIC-AMT-10-20-20260805) | Invariant prévu ; aucun calcul d'amortissement. | Méthode documentée de ventilation terrain/construction et rattachement des versions à chaque exercice à définir. |
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

Qualification LMNP/LMP du foyer et historique ; articulation et ordre des reports ;
cession/cessation ; TVA/parahôtellerie ; plus-values ; frais d'acquisition ;
ventilation terrain/bâtiment ; durées et composants ; CFE ; annexes applicables.
Ces points bloquent les futurs calculs correspondants. La disponibilité générale
de la saisie EFI au réel simplifié est confirmée dans `FILING.md` ; les cases et
contrôles propres à chaque millésime restent à vérifier.
