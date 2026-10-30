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
| `action` | `{ "label", "href" }` lien interne de résolution |
| `help` | Identifiant optionnel du glossaire (`fec`, `extourne`, `a-nouveaux`, …). Absent si le code n’a pas d’entrée. Une valeur inconnue est ignorée par l’interface. |
| `issues` | Liste d’erreurs de validation (champ + message, et `help` optionnel) |

Les erreurs Pydantic (`422`) sont normalisées en `VALIDATION_ERROR` avec `issues`. Les refus métier (`fail()`) renvoient `code`, `message` et, le cas échéant, `field`, `line`, `action`, `help` ou `issues`.

`help` pointe vers le glossaire du frontend (`frontend/src/features/glossary.ts`). Le serveur le remplit pour les codes listés dans `HELP_IDS` (`backend/app/core/api_errors.py`). Si le champ est absent, l’interface applique la même table (`ERROR_HELP`). Un `help` explicite et connu l’emporte sur cette table. Ce n’est pas un lien de navigation : la pastille **?** ouvre la définition (ce que c’est, pourquoi, un exemple, l’erreur fréquente). Le glossaire ne présente pas la liasse comme déclarable : les millésimes restent en recherche.

Un téléchargement de liasse, de PDF, de FEC ou de dossier de contrôle refusé parce que la posture est Bloquée utilise ce contrat (`409`). L’interface affiche le message, la liste `issues` lorsqu’il y en a plusieurs, et le lien `action`. Elle ne quitte pas la page.

## Interface

- **Champ** : message sous le contrôle, relié par `aria-describedby`.
- **Métier** : bandeau avec message, pastille d’aide lorsque `help` (ou le code) désigne une entrée du glossaire, et lien `action` (ex. ouvrir Comptabilité).
- **Import** : liste « Ligne n : … » lorsque `line` est présent.
- **Chargement** : chaque écran distingue `idle`, `loading`, `error`, `empty` et `loaded`. Une erreur de lecture affiche ce `detail` (`ApiErrorAlert`) et un bouton **Réessayer**. L’indicateur de chargement disparaît. `empty` n’apparaît qu’après une réponse réussie sans donnée : une panne n’est pas un dossier vide.

Lorsqu’un rafraîchissement échoue et que les données précédentes ne sont pas des montants calculés (états comptables, balance, grand livre, à-nouveaux), elles restent visibles avec la mention « Ces informations peuvent être périmées ». Les totaux et la prévisualisation des à-nouveaux sont retirés. Les cartes de posture (Provisoire, Bloquée, Finale) restent affichées dans ce cas : le serveur refuse toujours un téléchargement bloqué.

Voir `frontend/src/api/errors.ts`, `frontend/src/features/screenState.ts` et `backend/app/core/api_errors.py`.
