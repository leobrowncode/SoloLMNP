export interface PrerequisiteItem {
  code: string;
  message: string;
  action?: { label: string; href: string };
}

export default function PrerequisiteList({
  id,
  causes,
  intro = "Action indisponible :",
}: {
  id?: string;
  causes: readonly PrerequisiteItem[];
  intro?: string;
}) {
  if (causes.length === 0) return null;
  return (
    <div id={id} className={intro ? "action-prerequisites" : undefined}>
      {intro ? <p>{intro}</p> : null}
      <ul>
        {causes.map((cause) => (
          <li key={`${cause.code}-${cause.message}`}>
            <span>{cause.message}</span>
            {cause.action ? <> <a href={cause.action.href}>{cause.action.label}</a></> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
