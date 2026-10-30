import { Fragment, useState, type FormEvent } from "react";
import type { Account } from "../api/ledger";
import {
  ACCOUNT_NATURES,
  ACCOUNT_TYPES,
  USAGE_OPTIONS,
  accountNatureLabel,
  accountUsageLabel,
  isAccountType,
  matchesChartFilters,
  type AccountType,
  type UsageFilter,
} from "./accountNature";
import { EmptyState, NoResults } from "./EmptyState";
import { matchesText } from "./listQuery";
import GlossaryTip from "./GlossaryTip";
import { SaveNoticeHost } from "./LocalFeedback";
import type { SaveNotice } from "./localFeedback";
import FrenchForm from "../lib/FrenchForm";
import { MOBILE_QUERY, useMediaQuery } from "../lib/viewport";
import FitSelect from "../lib/FitSelect";

export default function ChartOfAccounts({
  accounts,
  busy,
  notice,
  onDismiss,
  onCreate,
  onToggle,
}: {
  accounts: Account[];
  busy: boolean;
  notice: SaveNotice | null;
  onDismiss: () => void;
  onCreate: (input: { number: string; label: string; account_type: string }) => void;
  onToggle: (account: Account) => void;
}) {
  const [nature, setNature] = useState("");
  const [usage, setUsage] = useState<UsageFilter>("");
  const [search, setSearch] = useState("");
  const mobile = useMediaQuery(MOBILE_QUERY);
  const narrowed = Boolean(nature || usage || search.trim());
  const visible = sortChart(accounts.filter((account) => (
    matchesChartFilters(account, nature, usage)
    && matchesText(
      `${account.number} ${account.label} ${accountNatureLabel(account.account_type)} ${accountUsageLabel(account.active)}`,
      search,
    )
  )));

  function resetFilters() {
    setNature("");
    setUsage("");
    setSearch("");
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const accountType = String(data.get("account_type") ?? "");
    if (!isAccountType(accountType)) return;
    onCreate({
      number: String(data.get("number") ?? ""),
      label: String(data.get("label") ?? ""),
      account_type: accountType,
    });
  }

  return (
    <>
      <div className="heading-with-help">
        <h3>Nature et utilisation</h3>
        <GlossaryTip id="nature-compte" />
      </div>
      <p>La nature (Actif, Dette, Capitaux, Charge, Produit) ne dit pas si le compte est utilisé. Activé ou Inactif est un autre choix.</p>
      <FrenchForm id="ajouter-compte" onSubmit={submit}>
        <div className="form-grid">
          <label>Numéro<input name="number" required pattern="[1-7][0-9]{2,9}" /></label>
          <label>Libellé du compte<input name="label" required /></label>
          <label>Nature
            <FitSelect name="account_type" required>
              {ACCOUNT_TYPES.map((type) => (
                <option key={type} value={type}>{ACCOUNT_NATURES[type]}</option>
              ))}
            </FitSelect>
          </label>
        </div>
        <button disabled={busy}>Ajouter le compte</button>
        <SaveNoticeHost place="ajouter-compte" notice={notice} onDismiss={onDismiss} />
      </FrenchForm>
      <div className="chart-filters">
        <label>
          Rechercher un compte
          <input
            type="search"
            value={search}
            autoComplete="off"
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <div>
          <label htmlFor="chart-nature-filter">Filtrer par nature</label>
          <FitSelect id="chart-nature-filter" value={nature} onChange={(event) => setNature(event.target.value)}>
            <option value="">Toutes les natures</option>
            {ACCOUNT_TYPES.map((type) => (
              <option key={type} value={type}>{ACCOUNT_NATURES[type]}</option>
            ))}
          </FitSelect>
        </div>
        <div>
          <label htmlFor="chart-usage-filter">Filtrer par utilisation</label>
          <FitSelect
            id="chart-usage-filter"
            value={usage}
            onChange={(event) => setUsage(event.target.value as UsageFilter)}
          >
            <option value="">Tous les états</option>
            {USAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </FitSelect>
        </div>
      </div>
      {accounts.length === 0 ? (
        <EmptyState
          title="Aucun compte dans le plan."
          reason="Ajoutez un compte pour pouvoir le mouvementer dans une écriture. La nature (Actif, Dette, Capitaux, Charge, Produit) reste distincte de l’utilisation."
          action={{ label: "Renseigner le formulaire", href: "#ajouter-compte" }}
        />
      ) : visible.length === 0 ? (
        <NoResults
          reason={search.trim() && !nature && !usage
            ? "Aucun compte ne correspond à cette recherche."
            : "Aucun compte pour cette nature ou cette utilisation."}
          onReset={resetFilters}
        />
      ) : (
        <>
          {narrowed && <button type="button" onClick={resetFilters}>Réinitialiser les filtres</button>}
          <>
          {mobile && <p className="mobile-table-priority">Colonnes principales : numéro, libellé, nature et utilisation.</p>}
          <ul className="chart-accounts" aria-label="Plan comptable" {...(mobile ? { "data-mobile-variant": "cards" } : {})}>
            {visible.map((account, index) => {
              const natureLabel = accountNatureLabel(account.account_type);
              const usageLabel = accountUsageLabel(account.active);
              const previous = index > 0 ? visible[index - 1] : undefined;
              const showGroup = nature === "" && previous?.account_type !== account.account_type;
              return (
              <Fragment key={account.number}>
              {showGroup ? <li className="chart-group-label"><p className="list-group-title">{natureLabel}</p></li> : null}
              <li
                id={`compte-${account.number}`}
                aria-label={`${account.number} ${account.label} ${natureLabel} ${usageLabel}`}
              >
                <span className="chart-id">{account.number} · {account.label}</span>
                <span>
                  <span className="chart-k">Nature</span>
                  {natureLabel}
                </span>
                <span>
                  <span className="chart-k">Utilisation</span>
                  {usageLabel}
                </span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onToggle(account)}
                >
                  {account.active ? "Désactiver" : "Réactiver"} {account.number}
                </button>
                <SaveNoticeHost place={`compte-${account.number}`} notice={notice} onDismiss={onDismiss} />
              </li>
              </Fragment>
              );
            })}
          </ul>
          </>
        </>
      )}
    </>
  );
}

function sortChart(rows: Account[]): Account[] {
  const rank = (type: string) => {
    const index = ACCOUNT_TYPES.indexOf(type as AccountType);
    return index === -1 ? ACCOUNT_TYPES.length : index;
  };
  return [...rows].sort((left, right) => (
    rank(left.account_type) - rank(right.account_type) || left.number.localeCompare(right.number, "fr")
  ));
}
