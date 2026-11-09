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
 * Wider screens keep the same DOM node (`details`) and hide the summary
 * so resizing the window does not remount children and wipe in-progress input.
 * `open` is the preferred initial state; the reader can still toggle it on mobile.
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

  const sectionClass = [
    "mobile-section",
    mobile ? "mobile-section--narrow" : "mobile-section--wide",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <details
      id={id}
      className={sectionClass}
      open={mobile ? opened : true}
      onToggle={
        mobile
          ? (event) => setOpened(event.currentTarget.open)
          : (event) => {
              event.preventDefault();
              event.currentTarget.open = true;
            }
      }
    >
      <summary>{title}</summary>
      {children}
    </details>
  );
}
