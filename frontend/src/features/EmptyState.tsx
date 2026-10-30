export type ListAction = { label: string; href: string } | { label: string; onClick: () => void };

export function EmptyState({
  title,
  reason,
  action,
}: {
  title: string;
  reason: string;
  action?: ListAction;
}) {
  return (
    <div className="empty-state" data-list-state="empty">
      <p className="empty-state-title">{title}</p>
      <p>{reason}</p>
      {action && "href" in action ? <a href={action.href}>{action.label}</a> : null}
      {action && "onClick" in action ? (
        <button type="button" onClick={action.onClick}>{action.label}</button>
      ) : null}
    </div>
  );
}

export function NoResults({
  reason,
  onReset,
}: {
  reason: string;
  onReset: () => void;
}) {
  return (
    <div className="empty-state" data-list-state="no-results">
      <p className="empty-state-title">Aucun résultat</p>
      <p>{reason}</p>
      <button type="button" onClick={onReset}>Réinitialiser les filtres</button>
    </div>
  );
}
