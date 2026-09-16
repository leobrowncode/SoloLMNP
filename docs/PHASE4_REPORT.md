# Phase 4 — immobilisations et amortissements comptables

## Périmètre livré

La version 0.5.0 ajoute un registre immuable des immobilisations et composants,
des plans linéaires en jours calendaires, des périodes par exercice et la
comptabilisation des dotations dans le ledger. Le calcul est comptable : il ne
calcule ni le plafond fiscal LMNP ni un amortissement fiscalement déductible.

## Principes sourcés

- Le PCG 2026, articles 214-4, 214-11, 214-12 et 214-13, définit le montant
  amortissable, impose une dotation à la clôture pour chaque actif amortissable,
  fait généralement partir l'amortissement à la mise en service et retient la
  durée et le mode propres à l'utilisation de l'actif. Le linéaire s'applique à
  défaut de mode mieux adapté.
- Le BOFiP BOI-BIC-AMT-20-10 § 120 et § 240 confirme, sur le plan fiscal qui
  sera traité séparément, la mise en service et le prorata en jours.
- Le BOFiP LMNP BOI-BIC-CHAMP-40-20 § 58 impose au loueur de distinguer sous sa
  responsabilité le terrain non amortissable de la construction.

Sources consultées le 16 septembre 2026 :

- [Recueil PCG ANC 2026](https://www.anc.gouv.fr/files/anc/files/1_Normes_fran%C3%A7aises/recueil/2026/Recueil-PCG-Janvier-2026.pdf) ;
- [BOI-BIC-AMT-20-10](https://bofip.impots.gouv.fr/bofip/4543-PGP.html/identifiant=BOI-BIC-AMT-20-10-20120912) ;
- [BOI-BIC-CHAMP-40-20](https://bofip.impots.gouv.fr/bofip/3610-PGP.html/identifiant=BOI-BIC-CHAMP-40-20-20240214).

## Modèle et invariants

- `asset` conserve valeur d'acquisition, base, part non amortissable, valeur
  résiduelle, mise en service, durée, comptes et justifications.
- `asset_component` décompose uniquement une construction. Les composants ne
  peuvent dépasser la base et doivent la couvrir exactement avant calcul.
- `depreciation_schedule` fige les paramètres qui ont servi au calcul.
- `depreciation_period` conserve jours, dotation, cumul, VNC de la base et lien
  vers l'écriture comptable.
- Un terrain exige méthode `NONE`, base nulle, part non amortissable égale à sa
  valeur et aucun compte 28. Les contraintes Pydantic, service, SQL et triggers
  rendent son amortissement impossible.
- Les enregistrements du registre et les plans sont immuables. Une correction
  future devra être explicite et auditée, sans réécriture silencieuse.

## Calcul reproductible

Le plan linéaire couvre l'intervalle de la mise en service jusqu'à la veille du
même quantième après la durée saisie en mois. Pour chaque clôture, la dotation
est la différence entre deux cumuls arrondis au centime :

```text
cumul(date) = arrondi(base × jours écoulés / jours totaux du plan)
dotation exercice = cumul(fin) - cumul(début - 1)
```

Cette formulation gère les années bissextiles, garantit que le cumul ne dépasse
jamais la base et affecte exactement toute la base à la fin du plan. Aucune
durée standard n'est proposée automatiquement : la justification est obligatoire.

## Écriture de dotation

Après contrôle utilisateur, chaque période produit dans le journal OD :

```text
Débit  681100  Dotations aux amortissements
Crédit 28xxxx  Amortissements cumulés de l'actif
```

L'écriture est équilibrée, validée et rattachée à la période. Un trigger vérifie
exercice, date, montant, source et comptes avant d'autoriser le passage de la
période à `POSTED`.

## Limites explicites

- L'inscription au registre ne crée pas encore l'écriture d'acquisition ou
  d'à-nouveau ; ces flux seront traités avec l'inventaire et la continuité P5.
- La sortie d'actif est modélisée, mais le workflow de cession et les écritures
  correspondantes ne sont pas encore disponibles.
- Aucun changement prospectif de durée, dépréciation, amortissement dérogatoire
  ou calcul fiscal LMNP n'est produit dans cette phase.
- Les durées et ventilations sont des choix documentés de l'utilisateur ; le
  logiciel ne présente aucune durée indicative comme une règle normative.
