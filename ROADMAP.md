# Roadmap

## État au 16 septembre 2026

- P0 : architecture et catalogue de scénarios livrés dans la PR #1. La recherche fiscale reste à compléter avant toute règle exécutable.
- P1 : implémentation, contrôles natifs et [CI Linux/Windows/frontend/Docker réussis](https://github.com/leobrowncode/SoloLMNP/actions/runs/35065201132). Revue et intégration de la [PR #14](https://github.com/leobrowncode/SoloLMNP/pull/14) en attente.
- P2 : ledger, API et interface implémentés ; 120 tests backend et 10 frontend passent en local. Voir [le rapport](docs/PHASE2_REPORT.md).
- P3 : recettes/dépenses à l'engagement, règlements, banque CSV, rapprochement et emprunts implémentés. Voir [le rapport](docs/PHASE3_REPORT.md).
- P4 : registre immuable, composants, prorata en jours et dotations ledger implémentés. Voir [le rapport](docs/PHASE4_REPORT.md).
- P5 : en cours. Bilan/résultat provisoires, prévisualisation et génération idempotente des à-nouveaux, contrôle par compte et scénario de règlement en deuxième année livrés. La génération exige une source clôturée (parcours de clôture prévu en P7). Inventaire, présentation réglementaire et validation complète de continuité restent à terminer ; l’issue #6 reste ouverte. Voir [le rapport](docs/PHASE5_REPORT.md).
  - Intégration P3/P4/P5 : scénario sur deux exercices avec règlements métier, emprunt et dotations ; correction du double comptage du capital après reprise et filtres du journal étendus aux dotations/à-nouveaux. La clôture reste simulée uniquement dans les fixtures de test.
  - Inventaire P5 : API de saisie manuelle justifiée, atomique et idempotente, audit et filtre journal livrés dans la PR #18. Formulaire dédié, pièces archivées et traitements automatiques restent à développer.
  - Suite de l’issue #6 après fusion de #18 : formulaire d’inventaire manuel, revue avant validation, reçu et reprise de la même demande après réponse perdue. Les pièces archivées, traitements automatiques et autres limites P5 restent à livrer.
  - Contrôle défensif P5 : les états et les à-nouveaux refusent aussi deux écritures déséquilibrées dont les écarts se compensent dans les totaux annuels (PR #18).

| Phase | Périmètre | Issue |
|---|---|---|
| P1 | Fondations persistantes et migration initiale | [#2](https://github.com/leobrowncode/SoloLMNP/issues/2) |
| P2 | Ledger en partie double et projections comptables | [#3](https://github.com/leobrowncode/SoloLMNP/issues/3) |
| P3 | Recettes, dépenses, banque CSV et emprunts | [#4](https://github.com/leobrowncode/SoloLMNP/issues/4) |
| P4 | Registre des immobilisations et amortissements comptables | [#5](https://github.com/leobrowncode/SoloLMNP/issues/5) |
| P5 | Inventaire, bilan, résultat et continuité | [#6](https://github.com/leobrowncode/SoloLMNP/issues/6) |
| P6 | Moteur fiscal versionné et reports séparés | [#7](https://github.com/leobrowncode/SoloLMNP/issues/7) |
| P7 | Contrôles, audit, clôture et réouverture | [#8](https://github.com/leobrowncode/SoloLMNP/issues/8) |
| P8 | Export et validation FEC sourcés | [#9](https://github.com/leobrowncode/SoloLMNP/issues/9) |
| P9 | Mappings 2031/2033, package et snapshot | [#10](https://github.com/leobrowncode/SoloLMNP/issues/10) |
| P10 | Feuille de saisie EFI et 2042-C-PRO | [#11](https://github.com/leobrowncode/SoloLMNP/issues/11) |
| P11 | Justificatifs durcis, backup et restauration | [#12](https://github.com/leobrowncode/SoloLMNP/issues/12) |
| P12 | E2E, sécurité, accessibilité et performance | [#13](https://github.com/leobrowncode/SoloLMNP/issues/13) |

## Ordre et critères de passage

1. **Fondations** : installation reproductible, migrations, configuration et CI.
2. **Ledger** : comptes/journaux/écritures/lignes, validation atomique, chronologie et numérotation, journal/grand livre/balance, contrôles de concurrence.
3. **Opérations** : recettes, dépenses, imports CSV idempotents, rapprochement, capital/intérêts/assurance séparés.
4. **Immobilisations** : bases et composants documentés, terrain non amortissable, prorata et écritures de dotation.
5. **États** : inventaire, bilan équilibré, résultat dérivé des comptes, continuité et à-nouveaux.
6. **Fiscalité** : sources par période d'effet, retraitements, registres de reports distincts et golden tests chiffrés.
7. **Clôture** : validations, journal d'audit, verrouillage, réouverture motivée et invalidation des dépendances.
8. **FEC** : format sourcé, export exclusivement depuis le ledger, validations et reproductibilité.
9. **Liasse** : formulaires officiels, mapping complet, traçabilité, package et snapshot.
10. **EFI** : feuille de recopie et rapport ; déclaration personnelle séparée.
11. **Conservation** : justificatifs, sauvegarde SQLite cohérente, restauration contrôlée et portabilité.
12. **Durcissement** : parcours A–J bout en bout, sécurité, accessibilité et performances.

Chaque phase exige périmètre, prérequis, modèle/migration, implémentation, tests exécutés, corrections, documentation et commit. Une issue reste ouverte si une validation bloquante manque. Aucun état READY fiscal avant contrôle complet des règles et formulaires du millésime.

Les issues ont été effectivement créées le 16 septembre 2026. Leur état GitHub fait foi ; voir également [.github/ISSUES.md](.github/ISSUES.md).
