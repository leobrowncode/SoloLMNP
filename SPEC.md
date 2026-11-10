# SoloLMNP v1

Contrat produit. Une demande hors de cette page est refusée. Léo est le seul arbitre.

## Promesse

Liasse LMNP à l'impôt sur le revenu, réel simplifié, exercice civil (premier exercice partiel possible) : feuille de recopie dans l'ordre des écrans EFI, PDF, montants 2042-C-PRO, état de suivi des amortissements non déduits (article 39 C), FEC et description. Pas de télétransmission. L'outil calcule, l'utilisateur signe. Aucun libellé « conforme » ou « certifié ».

En local : une commande, aucun secret. En ligne, à la demande de Léo : le même parcours sur Vercel, derrière Neon Auth, un dossier par compte.

## Dans la v1

LMNP, 1 à 3 logements meublés longue durée, plusieurs biens, composants, mobilier, prorata en jours, emprunt (capital, intérêts, assurance), plafonnement 39 C, déficits LMNP 10 ans par année d'origine, continuité N vers N+1. Formulaires : 2031, 2031-bis, 2033-A, 2033-B, 2033-C, 2033-D (cadre II mentionné néant), 2033-E, 2042-C-PRO, FEC. Dossier source YAML + CSV, justificatifs joints au dossier. Écritures dérivées, centimes entiers, partie double. Une OD justifiée peut venir d'un fichier. Trois états : Brouillon, Vérifié par l'utilisateur, Déclaré.

Hébergement, demandé par Léo : projet Vercel `sololmnp` (production https://sololmnp.vercel.app) et Neon Auth (Better Auth, e-mail et Google, liste `ALLOWED_EMAILS`). Chaque compte autorisé ne voit que son dossier. Hors ligne, le dossier reste des fichiers locaux. Sur Vercel, YAML, CSV, justificatifs et sorties sont dans le Blob privé. FEC, PDF et ZIP se téléchargent. `AUTH_MODE=local` ouvre le dossier sans secret. Il est refusé en production et sur Vercel.

## Hors v1

LMP, micro-BIC, location nue, SCI, TVA, cession, plus-value (alerte seulement), télétransmission EDI, éditeur de journal libre, corrections structurantes, réouverture motivée, sauvegarde et restauration, Google Sheets, OCR, mobile-first. Postgres comme base du dossier v1. Millésime 2027 et dépôt réel : hors de ce chantier.

## Critères

CA1 à CA6 : trois dossiers de référence, FEC, bilan équilibré, continuité, chaque case reliée à ses comptes et écritures. CA7 : une commande, zéro secret (`python scripts/start_v1.py`). CA8 : saisie d'une année par Léo (jalon J4, parcours `/v1`). CA9 : le même parcours en ligne, un compte hors liste est refusé, un autre compte ne voit pas le dossier.

## États

Brouillon : calcul de travail. Vérifié par l'utilisateur : registre de cases du millésime chargé, golden tests verts en CI, case « j'ai relu les cases contre la notice ». Déclaré : date de dépôt et accusé EFI, sorties figées avec empreinte SHA-256. Le verrou `validation.json` n'est plus la porte de la v1.

## Règle de travail

Ne pas modifier le mapping fiscal (`fiscal/*/forms/`) sans un golden test qui prouve le changement. Réduire le code existant, ne pas le réécrire : moteur 39 C, FEC, liasse, mappings 2025, plan de comptes, composants, emprunt.
