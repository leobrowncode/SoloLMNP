import { useState, type ReactNode } from "react";
import { MOBILE_QUERY, useMediaQuery } from "./viewport";

export function PageAnchors({
  label,
  links,
}: {
  label: string;
  links: { href: string; label: string }[];
}) {
  const mobile = useMediaQuery(MOBILE_QUERY);
  if (!mobile || links.length === 0) return null;
  return (
    <nav className="page-anchors" aria-label={label}>
      <ul>
        {links.map((link) => (
          <li key={link.href}>
            <a href={link.href}>{link.label}</a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/**
 * On a narrow viewport, a disclosure the reader can open.
 * Wider screens keep a plain wrapper so the desktop layout stays the same.
 * `open` is the preferred initial state; the reader can still toggle it.
 */
export function MobileSection({
  id,
  title,
  children,
  open = false,
  className,
}: {
  id: string;
  title: string;
  children: ReactNode;
  open?: boolean;
  className?: string;
}) {
  const mobile = useMediaQuery(MOBILE_QUERY);
  const [preferred, setPreferred] = useState(open);
  const [opened, setOpened] = useState(open);
  if (preferred !== open) {
    setPreferred(open);
    setOpened(open);
  }

  if (!mobile) {
    return <div id={id} className={className}>{children}</div>;
  }

  return (
    <details
      id={id}
      className={["mobile-section", className].filter(Boolean).join(" ")}
      open={opened}
      onToggle={(event) => setOpened(event.currentTarget.open)}
    >
      <summary>{title}</summary>
      {children}
    </details>
  );
}
