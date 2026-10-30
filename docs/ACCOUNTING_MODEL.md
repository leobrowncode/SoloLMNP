# Modèle comptable

## Source de vérité

Une opération métier produit une commande idempotente, puis une `AccountingEntry` persistée. La validation est transactionnelle et refuse déséquilibre, compte inactif, date hors exercice ou exercice verrouillé. Après validation, correction par extourne et nouvelle écriture ; aucune modification silencieuse. Un lot de dotations (`POST /api/assets/years/{id}/post`, en-tête `Idempotency-Key`) s’arrête à la première période refusée et décrit chaque élément. Les écritures déjà validées dans ce lot restent. La même clé ne les poste pas une seconde fois.

## Plan initial configurable

| Compte | Usage proposé |
|---|---|
| 101/108 | capital ou compte de l'exploitant |
| 164 | emprunts |
| 401 | fournisseurs |
| 411 | locataires si comptabilité d'engagement |
| 445 | TVA uniquement si activité assujettie configurée |
| 512 | banque |
| 211 | terrain, jamais amorti |
| 213 | constructions et composants |
| 215/2183/2184 | équipements, informatique, mobilier |
| 2813/2815/2818 | amortissements cumulés correspondants |
| 606/615/616/622/627 | fournitures, entretien, assurance, honoraires, banque |
| 635 | impôts et taxes (sous-comptes CFE/taxe foncière) |
| 661 | intérêts ; assurance d'emprunt dans un sous-compte documenté |
| 6811 | dotations aux amortissements |
| 706 | loyers et prestations ; sous-comptes pour charges refacturées |

Cette liste est une proposition à valider lors de la phase Ledger selon le PCG en vigueur. Les comptes sont configurables et historisés. Le type enregistré (`account_type`) est `ASSET`, `LIABILITY`, `EQUITY`, `EXPENSE` ou `INCOME`. L’écran Plan comptable traduit ces valeurs en nature Actif, Dette, Capitaux, Charge ou Produit, à part de l’état Activé ou Inactif.

## Projections

Journal : lignes ordonnées par date/journal/numéro. Grand livre : lignes groupées par compte avec solde courant. Balance : sommes débit/crédit par compte. Bilan et résultat reposent sur mappings de comptes versionnés, jamais sur les opérations ou formulaires fiscaux.


## Implémentation P2

Le ledger persistant est opérationnel. Les règles de validation, la numérotation, les protections SQLite, les projections et leurs références ANC sont détaillées dans [PHASE2_REPORT.md](PHASE2_REPORT.md). Le journal, le grand livre et la balance utilisent exclusivement les écritures VALIDATED.

## Implémentation P3

Les opérations suivent une comptabilité d'engagement : 411/401 lors de la constatation, puis apurement par 512 lors du règlement. Les dépenses restent comptabilisées pour leur montant intégral ; leur pourcentage fiscal ne modifie jamais l'écriture. Le capital d'emprunt, les intérêts, l'assurance et les frais sont ventilés. Détails et références ANC : [PHASE3_REPORT.md](PHASE3_REPORT.md).

## Implémentation P4

La base amortissable correspond à la valeur brute diminuée de la valeur résiduelle
significative et mesurable renseignée. La mise en service démarre le plan comptable.
Le terrain utilise 211 et ne possède ni durée, ni plan, ni compte 28. Les constructions,
installations, équipements et meubles utilisent leurs comptes 21/218 et 281 associés.
Chaque période confirmée débite 681100 et crédite le compte 28 du plan.

La durée est une estimation documentée de l'utilisation par l'activité. Le logiciel ne
fournit pas de barème automatique. Si une construction est décomposée, les composants
doivent couvrir exactement sa base afin d'éviter un double amortissement ou une omission.
Détails et sources : [PHASE4_REPORT.md](PHASE4_REPORT.md).

Le formulaire manuel ne propose que les comptes actifs de la catégorie. Le serveur
refuse tout autre couple, y compris sur un appel direct à l’API. Le compte
d’amortissement est le miroir de même longueur : on insère 8 après le chiffre de
classe et on retire le dernier chiffre (`213000` → `281300`, `213500` → `281350`,
`218400` → `281840`).

| Catégorie | Comptes d’immobilisation | Exemple |
|---|---|---|
| Terrain | 211, sans compte 28 | 211000 |
| Construction | 212, 213 hors 2135, 214 | 213000 / 281300 |
| Travaux immobilisés | 2135, 2181 | 213500 / 281350 |
| Équipement | 215, 2182, 2183 | 218300 / 281830 |
| Mobilier | 2184 | 218400 / 281840 |
| Autre | 218 hors 2181 à 2184 | sous-compte à ouvrir, avec son miroir 28 |

Un composant de construction n’utilise que les comptes construction ou agencement
(212, 213, 214, 2135, 2181) et leur miroir. Les comptes 28 et 29 ne sont jamais des
comptes d’immobilisation.

Un couple déjà enregistré qui ne respecte pas cette règle est signalé sur la fiche.
Il n’est pas réécrit automatiquement. Une correction de justification peut
préciser le motif sans changer les comptes ; un changement de compte ne passe
que s’il respecte le couple de la catégorie.

La correction d’une fiche structurante est un `PATCH` motivé. L’historique
`audit_event` conserve l’ancienne valeur, la nouvelle et le motif. Tant qu’aucune
dotation n’est comptabilisée, la valeur, la durée, les dates et les comptes d’une
immobilisation ou d’un composant peuvent être corrigés : les périodes calculées
non comptabilisées de cette fiche sont effacées, le plan est réaligné, les calculs
fiscaux des exercices ouverts sont invalidés, leurs instantanés `CURRENT` passent
`SUPERSEDED` et un exercice `READY_TO_CLOSE` redevient `OPEN`. Les écritures
validées ne sont pas réécrites : le FEC, qui n’en est que la lecture, ne change
donc pas tant que le journal ne change pas. Une dotation déjà comptabilisée fige
la valeur, la durée, les dates et les comptes (l’extourne d’une dotation n’est
pas proposée ici). Un calcul fiscal clôturé qui a conservé la base ou la durée
refuse leur modification jusqu’à réouverture ; il n’est pas invalidé en silence.
Une écriture d’acquisition encore en vie fige la valeur et les comptes. Le terrain
reste non amortissable. Les composants ne peuvent pas dépasser la base, et ils
doivent la couvrir exactement dès qu’un plan existe. Le bien, le locataire, la
banque et l’emprunt suivent la même règle : modifier ce qui est encore libre, ou
expliquer le verrou. Aucune de ces fiches n’est supprimée.
