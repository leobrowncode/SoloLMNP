#!/bin/sh
set -eu
command -v gh >/dev/null || { echo "gh requis" >&2; exit 1; }
git remote get-url origin >/dev/null 2>&1 || { echo "remote origin requis" >&2; exit 1; }
for title in \
  '[P1] Fondations persistantes et migration initiale' \
  '[P2] Ledger en partie double et projections comptables' \
  '[P3] Recettes, dépenses, banque CSV et emprunts' \
  '[P4] Registre des immobilisations et amortissements comptables' \
  '[P5] Inventaire, bilan, résultat et continuité' \
  '[P6] Moteur fiscal versionné et reports séparés' \
  '[P7] Contrôles, audit, clôture et réouverture' \
  '[P8] Export et validation FEC sourcés' \
  '[P9] Mappings 2031/2033, package et snapshot' \
  '[P10] Feuille de saisie EFI et 2042-C-PRO' \
  '[P11] Justificatifs durcis, backup et restauration' \
  '[P12] E2E, sécurité, accessibilité et performance'
do
  if gh issue list --state all --limit 1000 --json title --jq '.[].title' | grep -Fxq -- "$title"; then
    printf 'Issue existante : %s\n' "$title"
    continue
  fi
  gh issue create --title "$title" --body "Voir ROADMAP.md. Critères obligatoires : tests, documentation, traçabilité et sources officielles pour toute règle fiscale/comptable."
done
