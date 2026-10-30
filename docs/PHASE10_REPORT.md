# Phase 10 — feuille EFI et 2042-C-PRO

La feuille de recopie est un document de travail. Chaque millésime reste `research_only`. L’écran **Déclaration** explique chaque montant (formule, identifiant de règle, lien vers la source officielle) et ouvre les écritures validées du ledger qui l’alimentent. La centralisation et l’affectation en sont exclues.

## EFI — 2031 et 2033

Pour le millésime projet 2025, les cases chiffrées du 2033-A à E viennent de la liasse archivée (`case_publication: verified_from_archive`). Les lignes 2031 et 2031-bis n’ont pas de numéro de case sur le formulaire : elles sont publiées **non numérotées**, pas inventées. Le millésime projet 2026 ne publie aucun numéro : les formulaires 2027 ne sont pas archivés (`case_publication: blocked`). Le numéro interne reste dans le package de liasse pour les contrôles, et la feuille affiche « bloquée ».

Le PDF, le CSV et le JSON portent le marqueur « document de travail, à vérifier », le millésime et les empreintes de règles et de formulaires. Ils suivent la posture Provisoire / Bloquée / Finale du PDF. Le zip de contrôle les contient. Saisie et envoi manuels uniquement : pas de scraping, pas d’EDI, pas de télétransmission.

## 2042-C-PRO

Produit séparé de la liasse. Revenus 2025, formulaire millésime 2026, CERFA 11222*28, lu le 30 octobre 2026 (1 020 894 octets, empreinte `293de292c87cf77251e659ac5611dac416104d6019e7a458078f7421707c993b`) :

- cas général, régime réel : bénéfice ou 0 en 5NA, déficit en 5NY ;
- 5NK est le micro-BIC (meublés de tourisme non classés) ; 5NZ n’est pas sur le formulaire ; les deux sont bloquées ;
- 5OA, 5PA, 5OY, 5PY, 5NM, 5WE et 5CD ne sont pas remplies ;
- déficits antérieurs sur ce formulaire seulement : 2015 = 5GA à 2024 = 5GJ.

Le montant de 5NA ou 5NY est le résultat fiscal avant imputation des déficits LMNP antérieurs. Le registre `carry_forward_event` montre l’ouverture, l’imputé et le reste. L’exercice 2026 ne publie aucune case : le formulaire 2027 n’existe pas.

L’issue #11 reste ouverte pour ce millésime 2027.
