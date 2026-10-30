import { useState, type FormEvent } from "react";
import type { Account } from "../api/ledger";
import {
  ACCOUNT_NATURES,
  ACCOUNT_TYPES,
  USAGE_OPTIONS,
  accountNatureLabel,
  accountUsageLabel,
  isAccountType,
  matchesChartFilters,
  type UsageFilter,
} from "./accountNature";
import GlossaryTip from "./GlossaryTip";

export default function ChartOfAccounts({
  accounts,
  busy,
  onCreate,
  onToggle,
}: {
  accounts: Account[];
  busy: boolean;
  onCreate: (input: { number: string; label: string; account_type: string }) => void;
  onToggle: (account: Account) => void;
}) {
  const [nature, setNature] = useState("");
  const [usage, setUsage] = useState<UsageFilter>("");
  const visible = accounts.filter((account) => matchesChartFilters(account, nature, usage));

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
      <form onSubmit={submit}>
        <div className="form-grid">
          <label>Numéro<input name="number" required pattern="[1-7][0-9]{2,9}" /></label>
          <label>Libellé du compte<input name="label" required /></label>
          <label>Nature
            <select name="account_type" required>
              {ACCOUNT_TYPES.map((type) => (
                <option key={type} value={type}>{ACCOUNT_NATURES[type]}</option>
              ))}
            </select>
          </label>
        </div>
        <button disabled={busy}>Ajouter le compte</button>
      </form>
      <div className="chart-filters">
        <div>
          <label htmlFor="chart-nature-filter">Filtrer par nature</label>
          <select id="chart-nature-filter" value={nature} onChange={(event) => setNature(event.target.value)}>
            <option value="">Toutes les natures</option>
            {ACCOUNT_TYPES.map((type) => (
              <option key={type} value={type}>{ACCOUNT_NATURES[type]}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="chart-usage-filter">Filtrer par utilisation</label>
          <select
            id="chart-usage-filter"
            value={usage}
            onChange={(event) => setUsage(event.target.value as UsageFilter)}
          >
            <option value="">Tous les états</option>
            {USAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>
      </div>
      {visible.length === 0
        ? <p>Aucun compte pour cette nature ou cette utilisation.</p>
        : (
          <ul className="chart-accounts" aria-label="Plan comptable">
            {visible.map((account) => {
              const natureLabel = accountNatureLabel(account.account_type);
              const usageLabel = accountUsageLabel(account.active);
              return (
              <li
                key={account.number}
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
              </li>
              );
            })}
          </ul>
        )}
    </>
  );
}
