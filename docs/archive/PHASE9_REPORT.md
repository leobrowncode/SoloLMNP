# Phase 9 — liasse de travail

`fiscal/2025/forms/2033.json` et `fiscal/2026/forms/2033.json` décrivent une structure de travail, pas des cases CERFA certifiées. Le compilateur n’évalue qu’une liste blanche (`sum_accounts`, `balance`, `tax_result`, additions et soustractions). Chaque case conserve l’expression, les comptes, les écritures et les Rule IDs. Le contrôle `RESULT_IS_TAX` relie le résultat fiscal au champ correspondant. Le snapshot est `CURRENT` ou `SUPERSEDED` et n’est pas supprimé.

Aucun envoi à l’administration. L’issue #10 reste ouverte tant que les notices officielles du millésime ne sont pas archivées et qu’une règle bloquante reste désactivée.
