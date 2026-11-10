# SoloLMNP v1

Contrat produit. Une demande hors de cette page est refusée. Léo est le seul arbitre.

## Promesse

Outil local, mono-utilisateur, une commande, aucun secret. Il prépare la liasse LMNP à l'impôt sur le revenu, réel simplifié, exercice civil (premier exercice partiel possible) : feuille de recopie dans l'ordre des écrans EFI, PDF, montants 2042-C-PRO, état de suivi des amortissements non déduits (article 39 C), FEC et description. Pas de télétransmission. L'outil calcule, l'utilisateur signe. Aucun libellé « conforme » ou « certifié ».

## Dans la v1

LMNP, 1 à 3 logements meublés longue durée, plusieurs biens, composants, mobilier, prorata en jours, emprunt (capital, intérêts, assurance), plafonnement 39 C, déficits LMNP 10 ans par année d'origine, continuité N vers N+1. Formulaires : 2031, 2031-bis, 2033-A, 2033-B, 2033-C, 2033-D (cadre II mentionné néant), 2033-E, 2042-C-PRO, FEC. Dossier source YAML + CSV. Écritures dérivées, centimes entiers, partie double. Une OD justifiée peut venir d'un fichier. Trois états : Brouillon, Vérifié par l'utilisateur, Déclaré.

## Hors v1

LMP, micro-BIC, location nue, SCI, TVA, cession, plus-value (alerte seulement), télétransmission EDI, auth, multi-utilisateur, Neon, Postgres, Vercel, Blob, éditeur de journal libre, corrections structurantes, réouverture motivée, sauvegarde et restauration, Google Sheets, OCR, mobile-first. Millésime 2027 et dépôt réel : hors de ce chantier.

## Critères

CA1 à CA6 : trois dossiers de référence, FEC, bilan équilibré, continuité, chaque case reliée à ses comptes et écritures. CA7 : une commande, zéro secret. CA8 : saisie d'une année par Léo (jalon suivant, hors de ce chantier).

## États

Brouillon : calcul de travail. Vérifié par l'utilisateur : registre de cases du millésime chargé, golden tests verts en CI, case « j'ai relu les cases contre la notice ». Déclaré : date de dépôt et accusé EFI, sorties figées avec empreinte SHA-256. Le verrou `validation.json` n'est plus la porte de la v1.

## Règle de travail

Ne pas modifier le mapping fiscal (`fiscal/*/forms/`) sans un golden test qui prouve le changement. Réduire le code existant, ne pas le réécrire : moteur 39 C, FEC, liasse, mappings 2025, plan de comptes, composants, emprunt.
