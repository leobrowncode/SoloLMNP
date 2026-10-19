# Décisions produit

Une recommandation de l'agent n'est pas une décision approuvée. Tant que la colonne Décision est vide, le statut reste `EN_ATTENTE_UTILISATEUR` et le comportement correspondant ne doit pas être implémenté.

## Q-001 — Prochaine capacité

- Question : quel parcours débloquer ensuite ?
- Constat : la génération des à-nouveaux refuse toute source qui n'est pas `CLOSED`. Aucun écran ne clôture un exercice. Un utilisateur ne peut donc pas reprendre ses soldes sur l'exercice suivant. Les états restent une projection provisoire par compte.
- Options :
  - A. Livrer une clôture minimale auditée (`OPEN` vers `CLOSED`, réouverture motivée) qui débloque les à-nouveaux, sans centraliser les classes 6/7 ni affecter le résultat.
  - B. Finir d'abord une présentation réglementaire du bilan et du résultat, en laissant les à-nouveaux bloqués.
  - C. Ouvrir le moteur fiscal versionné, toujours en `research_only`.
- Recommandation : A. C'est le seul blocage qui empêche un dossier réel d'enchaîner deux exercices. La présentation réglementaire et la fiscalité restent des lots séparés.
- Décision approuvée : —
- Date et référence : —
- Statut : `EN_ATTENTE_UTILISATEUR`
- Implémentation : non commencée

## Q-002 — Reprise du résultat

- Question : lors d'une future clôture, où va le résultat ?
- Constat : les à-nouveaux demandent un compte 120 (hors 1209) pour un bénéfice ou 129 pour une perte. Aucun de ces comptes n'est créé automatiquement. Il n'y a ni centralisation des classes 6/7 ni affectation au compte de l'exploitant.
- Options :
  - A. Reprendre le résultat uniquement sur le compte 120 ou 129 choisi explicitement, avant affectation.
  - B. Ajouter dans le même parcours une affectation vers le compte de l'exploitant.
  - C. Laisser le résultat dans les comptes de charges et de produits, sans écriture de reprise du résultat.
- Recommandation : A. Elle est déjà celle du service d'à-nouveaux et elle n'invente pas d'affectation.
- Décision approuvée : —
- Date et référence : —
- Statut : `EN_ATTENTE_UTILISATEUR`
- Implémentation : non commencée

## Q-003 — Écritures d'inventaire guidées

- Question : les CCA, PCA, charges à payer et produits à recevoir doivent-ils rester une saisie libre ?
- Constat : l'inventaire est une écriture équilibrée, justifiée et validée, dont le schéma est choisi par l'utilisateur. Aucun modèle ne calcule ces montants.
- Options :
  - A. Conserver la saisie manuelle justifiée, sans schéma proposé.
  - B. Proposer des schémas guidés, toujours relus et validés explicitement, sans modifier la déductibilité fiscale.
- Recommandation : A tant que la clôture n'existe pas. Un schéma guidé peut venir ensuite, sans devenir un calcul fiscal.
- Décision approuvée : —
- Date et référence : —
- Statut : `EN_ATTENTE_UTILISATEUR`
- Implémentation : non commencée
