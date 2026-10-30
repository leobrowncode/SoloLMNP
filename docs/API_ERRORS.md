# Contrat d’erreur API

Les réponses d’échec JSON exposent un objet `detail` structuré, identique pour le backend FastAPI et le client React.

## Forme

| Clé | Rôle |
| --- | --- |
| `code` | Identifiant stable (`VALIDATION_ERROR`, `CSV_AMOUNT`, `ACTIVITY_REQUIRED`, …) |
| `message` | Texte lisible pour l’utilisateur |
| `field` | Chemin de champ (validation ou refus métier ciblé) |
| `location` | `body`, `query` ou `import` |
| `line` | Numéro de ligne CSV / tableau (imports) |
| `column` | Libellé de la colonne du fichier (rejet d’import) |
| `value` | Valeur lue, tronquée (rejet d’import). Chaîne vide si la cellule est vide. |
| `correction` | Correction attendue, en français (rejet d’import) |
| `action` | `{ "label", "href" }` lien interne de résolution |
| `help` | Identifiant optionnel du glossaire (`fec`, `extourne`, `a-nouveaux`, `import-csv`, …). Absent si le code n’a pas d’entrée. Une valeur inconnue est ignorée par l’interface. |
| `issues` | Liste d’erreurs de validation ou de rejet d’import (champ, message, et le cas échéant `line`, `column`, `value`, `correction`, `help`) |

Les erreurs Pydantic (`422`) sont normalisées en `VALIDATION_ERROR` avec `issues`. Les refus métier (`fail()`) renvoient `code`, `message` et, le cas échéant, `field`, `line`, `action`, `help` ou `issues`.

`help` pointe vers le glossaire du frontend (`frontend/src/features/glossary.ts`). Le serveur le remplit pour les codes listés dans `HELP_IDS` (`backend/app/core/api_errors.py`). Si le champ est absent, l’interface applique la même table (`ERROR_HELP`). Un `help` explicite et connu l’emporte sur cette table. Ce n’est pas un lien de navigation : la pastille **?** ouvre la définition (ce que c’est, pourquoi, un exemple, l’erreur fréquente). Le glossaire ne présente pas la liasse comme déclarable : les millésimes restent en recherche.

Les refus de justificatif (`INVALID_DOCUMENT`, `DOCUMENT_SIZE`, `DOCUMENT_SIGNATURE`, `DOCUMENT_PATH`, `DOCUMENT_NOT_FOUND`) pointent vers `justificatif`. La recherche et la liaison d’écriture (`ENTRY_SEARCH`, `ENTRY_NOT_FOUND`, `ENTRY_AMBIGUOUS`) pointent vers `ecriture`. Les refus d’archive (`BACKUP_PATH`, `BACKUP_NOT_FOUND`, `BACKUP_REJECTED`) pointent vers `sauvegarde`. `RESTORE_CONFIRMATION` pointe vers `restauration`.

Un téléchargement de liasse, de PDF, de FEC ou de dossier de contrôle refusé parce que la posture est Bloquée utilise ce contrat (`409`). L’interface affiche le message, la liste `issues` lorsqu’il y en a plusieurs, et le lien `action`. Elle ne quitte pas la page.

## Interface

- **Champ** : message sous le contrôle, relié par `aria-describedby`.
- **Métier** : bandeau avec message, pastille d’aide lorsque `help` (ou le code) désigne une entrée du glossaire, et lien `action` (ex. ouvrir Comptabilité).
- **Import** : liste « Ligne n, colonne Col : message. Valeur « … ». Correction attendue : … » lorsque `line` est présent. `column`, `value` et `correction` sont omis s’ils ne s’appliquent pas.

L’assistant d’import (`POST /api/operations/imports/{profil}/preview` et `/commit`, profils `bank`, `operations`, `loan_payments`) renvoie ces rejets dans `issues` et sur chaque ligne en erreur, avec `location: "import"`. Le fichier des rejets reprend les mêmes colonnes françaises et une colonne `Correction`. Les anciens points `POST /api/operations/bank/import`, `/import` et `/loans/{id}/payments/import` restent inchangés : un refus y arrête tout le fichier.
- **Chargement** : chaque écran distingue `idle`, `loading`, `error`, `empty` et `loaded`. Une erreur de lecture affiche ce `detail` (`ApiErrorAlert`) et un bouton **Réessayer**. L’indicateur de chargement disparaît. `empty` n’apparaît qu’après une réponse réussie sans donnée : une panne n’est pas un dossier vide.

Lorsqu’un rafraîchissement échoue et que les données précédentes ne sont pas des montants calculés (états comptables, balance, grand livre, à-nouveaux), elles restent visibles avec la mention « Ces informations peuvent être périmées ». Les totaux et la prévisualisation des à-nouveaux sont retirés. Les cartes de posture (Provisoire, Bloquée, Finale) restent affichées dans ce cas : le serveur refuse toujours un téléchargement bloqué.

Voir `frontend/src/api/errors.ts`, `frontend/src/features/screenState.ts` et `backend/app/core/api_errors.py`.

## Mutations et lots

Chaque action qui écrit (immobilisation, clôture, sauvegarde, restauration, import, comptabilisation) désactive son bouton jusqu’à la réponse et affiche l’étape en cours. Un second clic pendant ce temps est ignoré.

`POST /api/assets/years/{id}/post` comptabilise un lot de dotations. L’en-tête `Idempotency-Key` (8 à 80 caractères) est obligatoire. La réponse est toujours `200` lorsque le lot a été accepté, avec le statut de chaque période : `posted`, `error` ou `skipped`. Les périodes déjà passées avant l’erreur restent comptabilisées ; les suivantes ne sont pas traitées. Une écriture validée n’est pas réécrite : la période est la clé naturelle, un nouvel envoi retrouve la même écriture.

La même clé et le même lot renvoient le résultat enregistré (`replayed: true`), y compris après une réponse perdue. Une clé déjà utilisée pour un autre lot répond `409` `IDEMPOTENCY_CONFLICT`. Après une erreur partielle, l’écran recharge les périodes réellement enregistrées. Un nouvel envoi des périodes encore ouvertes utilise une nouvelle clé.

`IDEMPOTENCY_KEY_REQUIRED`, `PERIOD_NOT_FOUND`, `PERIOD_YEAR_MISMATCH`, `ZERO_DEPRECIATION` et `BATCH_INTERRUPTED` pointent vers le glossaire `dotation`.
