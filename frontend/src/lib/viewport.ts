import { useEffect, useState } from "react";

/** Phone and small tablet. 768 px is included so the checked widths match. */
export const MOBILE_QUERY = "(max-width: 768px)";

/** Widths where a fixed control can be clipped by the viewport. */
export const NARROW_CONTROL_QUERY = "(max-width: 430px)";

function queryMatches(query: string): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
  return window.matchMedia(query).matches;
}

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => queryMatches(query));

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(query);
    const apply = () => setMatches(media.matches);
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [query]);

  return matches;
}
