# Phase 6 — moteur fiscal versionné

Migration `0006_fiscal`. Un calcul est immuable dans son empreinte de règles, de ledger et d’ajustements. Les reports d’amortissement non déduit et de déficit LMNP sont des registres séparés. Aucune écriture de ledger n’est créée pour obtenir un résultat fiscal.

Quatre règles sont exécutables parce qu’elles ont un identifiant, une source, une période d’effet, une interprétation et un test chiffré : terrain non amortissable, plafond de déduction distinct de la dotation comptable, déficit LMNP non imputé sur le revenu global, charge partiellement déductible laissée pour son montant plein au ledger. Le LMP est hors périmètre : l’activité est déclarée LMNP, sans calcul des seuils du foyer. La cession, la TVA, les plus-values et la ventilation automatique du terrain restent désactivées. Aucun montant n’est inventé pour elles.

L’API et l’écran affichent `research_only`. `/api/status` ne passe pas à un état fiscal prêt. Depuis le lot moteur MVP, la consommation FIFO des reports d’amortissement non déduit et de déficit LMNP (exercices clôturés, horizon 10 ans pour les déficits) est tracée dans `details.prior_carry_forward_use` sans muter les registres d’origine. L’issue #7 reste ouverte pour cession, TVA, plus-values et le passage déclarable. Le LMP est hors périmètre.
