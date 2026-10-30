import { useId, useState, type ReactNode } from "react";
import FitSelect from "../lib/FitSelect";
import { EmptyState, NoResults, type ListAction } from "./EmptyState";
import {
  EMPTY_CRITERIA, criteriaActive, filterList, groupByKey, type ListCriteria,
} from "./listQuery";

/**
 * Search, status and category for a list that is already loaded.
 * Callers must not mount this during loading or an error: an empty `items`
 * array here means the request succeeded with nothing to show.
 */
export function BrowsableList<T>({
  items,
  text,
  statusOf,
  categoryOf,
  statusChoices,
  categoryChoices,
  statusLabel = "Filtrer par statut",
  categoryLabel = "Filtrer par catégorie",
  searchLabel,
  emptyTitle,
  emptyReason,
  emptyAction,
  noResultsReason = "Aucun élément ne correspond à la recherche ou aux filtres.",
  groupBy,
  groupTitle,
  children,
}: {
  items: readonly T[];
  text: (item: T) => string;
  statusOf?: (item: T) => string;
  categoryOf?: (item: T) => string;
  statusChoices?: readonly (readonly [string, string])[];
  categoryChoices?: readonly (readonly [string, string])[];
  statusLabel?: string;
  categoryLabel?: string;
  searchLabel: string;
  emptyTitle: string;
  emptyReason: string;
  emptyAction?: ListAction;
  noResultsReason?: string;
  groupBy?: (item: T) => string;
  groupTitle?: (key: string) => string;
  children: (items: readonly T[]) => ReactNode;
}) {
  const statusId = useId();
  const categoryId = useId();
  const [criteria, setCriteria] = useState<ListCriteria>(EMPTY_CRITERIA);
  const active = criteriaActive(criteria);
  const visible = filterList(items, criteria, {
    text,
    ...(statusOf ? { status: statusOf } : {}),
    ...(categoryOf ? { category: categoryOf } : {}),
  });

  function update(patch: Partial<ListCriteria>) {
    setCriteria((current) => ({ ...current, ...patch }));
  }

  function reset() {
    setCriteria(EMPTY_CRITERIA);
  }

  if (items.length === 0 && !active) {
    return <EmptyState title={emptyTitle} reason={emptyReason} {...(emptyAction ? { action: emptyAction } : {})} />;
  }

  const grouped = groupBy && !criteria.category ? groupByKey(visible, groupBy) : null;

  return (
    <div className="browsable-list">
      <div className="chart-filters list-toolbar">
        <label>
          {searchLabel}
          <input
            type="search"
            value={criteria.search}
            autoComplete="off"
            onChange={(event) => update({ search: event.target.value })}
          />
        </label>
        {statusChoices && statusChoices.length > 0 ? (
          <div>
            <label htmlFor={statusId}>{statusLabel}</label>
            <FitSelect id={statusId} value={criteria.status} onChange={(event) => update({ status: event.target.value })}>
              <option value="">Tous les statuts</option>
              {statusChoices.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </FitSelect>
          </div>
        ) : null}
        {categoryChoices && categoryChoices.length > 0 ? (
          <div>
            <label htmlFor={categoryId}>{categoryLabel}</label>
            <FitSelect id={categoryId} value={criteria.category} onChange={(event) => update({ category: event.target.value })}>
              <option value="">Toutes les catégories</option>
              {categoryChoices.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </FitSelect>
          </div>
        ) : null}
      </div>
      {active && visible.length > 0 ? (
        <button type="button" onClick={reset}>Réinitialiser les filtres</button>
      ) : null}
      {visible.length === 0 ? (
        <NoResults reason={noResultsReason} onReset={reset} />
      ) : grouped ? (
        grouped.map((group) => (
          <section key={group.key || "sans-categorie"} aria-label={groupTitle?.(group.key) ?? group.key}>
            <p className="list-group-title">{groupTitle?.(group.key) ?? group.key}</p>
            {children(group.items)}
          </section>
        ))
      ) : children(visible)}
    </div>
  );
}
