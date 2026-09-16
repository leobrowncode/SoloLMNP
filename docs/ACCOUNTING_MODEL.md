# Modèle comptable

## Source de vérité

Une opération métier produit une commande idempotente, puis une `AccountingEntry` persistée. La validation est transactionnelle et refuse déséquilibre, compte inactif, date hors exercice ou exercice verrouillé. Après validation, correction par extourne et nouvelle écriture ; aucune modification silencieuse.

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

Cette liste est une proposition à valider lors de la phase Ledger selon le PCG en vigueur. Les comptes sont configurables, historisés et typés ACTIF/PASSIF/CHARGE/PRODUIT/CAPITAUX.

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
