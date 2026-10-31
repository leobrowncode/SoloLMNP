# Limites connues

SoloLMNP tient une comptabilité LMNP au réel simplifié, pour une personne, sur une machine locale. Les montants sont des centimes entiers. Le journal validé est la seule source du grand livre, de la balance, des états et du FEC. Les couches fiscales ne modifient pas les écritures.

## Ce qui n’est pas une déclaration

Les millésimes 2025 et 2026 restent en **Recherche** (`research_only`). Le calcul, la liasse, le PDF et le FEC de ces millésimes ne sont pas déclarables. « Prête à recopier » n’apparaît que pour une sortie **Déclarable**, ce qui n’arrive pas pour ces millésimes. SoloLMNP n’envoie rien à l’administration : pas d’EDI, pas de télétransmission, pas de scraping.

Un résultat affiché, même équilibré, reste à contrôler sur le formulaire en ligne au moment de déclarer. Les cases de l’exercice 2026 ne sont pas publiées : elles restent bloquées.

## Hors périmètre

- LMP, micro-BIC, location nue.
- Cession, TVA, plus-values.
- Ventilation automatique du terrain.
- Imputation des déficits LMNP antérieurs sur la liasse. Le calcul interne peut montrer une estimation FIFO ; elle n’est pas une imputation officielle.
- Authentification. L’application doit rester liée à `127.0.0.1`. Voir [SECURITY.md](SECURITY.md).
- Plusieurs utilisateurs, ou une base autre que le fichier SQLite local.

## Données et restauration

Le propriétaire du fichier SQLite peut le modifier. L’audit n’est pas une piste inviolable. La restauration remplace toute la base après contrôle de l’archive et sauvegarde préalable. Elle ne réécrit pas une écriture validée en place.

Le FEC suit le format légal (tabulation, 18 zones, dates et montants inchangés). Ses zones de texte neutralisent une formule de tableur, comme les autres CSV produits par l’application.
