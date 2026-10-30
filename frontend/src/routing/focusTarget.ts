export function focusRouteTarget(hash: string): boolean {
  const raw = hash.startsWith("#") ? hash.slice(1) : "";
  if (!raw) {
    document.getElementById("main")?.focus();
    return true;
  }
  let id: string;
  try {
    id = decodeURIComponent(raw);
  } catch {
    id = raw;
  }
  const target = document.getElementById(id);
  if (!(target instanceof HTMLElement)) return false;
  if (typeof target.scrollIntoView === "function") target.scrollIntoView({ block: "start" });
  target.focus({ preventScroll: true });
  return true;
}
