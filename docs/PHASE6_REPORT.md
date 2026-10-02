# Phase 6 — moteur fiscal versionné

Migration `0006_fiscal`. Un calcul est immuable dans son empreinte de règles, de ledger et d’ajustements. Les reports d’amortissement non déduit et de déficit LMNP sont des registres séparés. Aucune écriture de ledger n’est créée pour obtenir un résultat fiscal.

Quatre règles sont exécutables parce qu’elles ont un identifiant, une source, une période d’effet, une interprétation et un test chiffré : terrain non amortissable, plafond de déduction distinct de la dotation comptable, déficit LMNP non imputé sur le revenu global, charge partiellement déductible laissée pour son montant plein au ledger. La qualification LMNP/LMP du foyer, la cession, la TVA, les plus-values et la ventilation automatique du terrain restent désactivées. Aucun montant n’est inventé pour elles.

L’API et l’écran affichent `research_only`. `/api/status` ne passe pas à un état fiscal prêt. L’issue #7 reste ouverte tant qu’une règle bloquante est désactivée.
