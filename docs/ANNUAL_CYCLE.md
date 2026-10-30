# Cycle annuel

Parcours d’un exercice LMNP au réel dans SoloLMNP. Les montants affichés pour les millésimes 2025 et 2026 restent en recherche : ils ne se recopient pas comme une déclaration fiable, et rien n’est envoyé.

1. **Activité et exercice.** Créer l’activité, le SIREN, puis l’exercice. La date de fin est postérieure ou égale à la date de début, et l’année de clôture est celle de cette date de fin. Le millésime fiscal est l’année des formulaires : il peut différer du mot « exercice », et il n’est pas déduit des dates.
2. **Bien, banque, écritures.** Saisir le logement (terrain et bâtiment). Importer ou saisir les recettes et les charges. Une ligne payée passe par le compte bancaire. Le capital d’un emprunt n’est pas une charge : intérêts et assurance sont des lignes distinctes.
3. **Immobilisations.** Prévisualiser le plan du logement, le créer, calculer les périodes, puis comptabiliser les dotations. Le terrain n’est pas amorti. La comptabilité des dotations ne change pas le plafond fiscal.
4. **Centralisation.** Les comptes de charges et de produits se centralisent avant le calcul fiscal. L’affectation du 120 ou du 129 est une étape séparée.
5. **Calcul fiscal.** Lancer le calcul. Le statut affiché reste Recherche pour les millésimes chargés. Une quote-part non déductible se voit à part : le ledger garde le montant entier. L’amortissement non déduit et le déficit LMNP sont deux stocks distincts. Ce calcul n’est pas une base de déclaration.
6. **Pré-contrôle et clôture.** Le pré-contrôle bloque sur une erreur. Chaque avertissement affiché doit être accusé. La confirmation fige les écritures. Une réouverture exige un motif et invalide les exports déjà figés.
7. **Feuille et FEC.** La liasse à recopier porte `research_only` et le rappel qu’elle reste en recherche. Pas de télétransmission. Le FEC se télécharge depuis l’exercice clôturé, avec le SIREN, et ne contient que le ledger validé.
8. **Exercice suivant.** Créer le nouvel exercice, prévisualiser les à-nouveaux, les valider, puis contrôler que les soldes repris correspondent aux soldes source.
9. **Conservation.** Créer une sauvegarde. Une restauration demande le mot `RESTAURER` et remplace la base après contrôle.

Le détail d’installation est dans le [README](../README.md) et [DEPLOYMENT.md](DEPLOYMENT.md). Les limites sont dans [LIMITS.md](LIMITS.md).
