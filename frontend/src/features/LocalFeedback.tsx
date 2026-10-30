import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { SAVE_NOTICE_MS, type SaveNotice } from "./localFeedback";
import "./ledger.css";

function scrollTo(target: HTMLElement) {
  if (typeof target.scrollIntoView !== "function") return;
  try {
    target.scrollIntoView({ block: "nearest" });
  } catch {
    target.scrollIntoView();
  }
}

function focusElement(target: HTMLElement) {
  const naturally = target.matches("a,button,input,select,textarea") || target.tabIndex >= 0;
  if (!naturally) {
    target.tabIndex = -1;
    target.dataset.saveFocus = "added";
  }
  try {
    target.focus({ preventScroll: true });
  } catch {
    target.focus();
  }
}

function LocalFeedbackView({
  notice,
  containerId,
  onDismiss,
}: {
  notice: SaveNotice;
  containerId: string;
  onDismiss: () => void;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const onDismissRef = useRef(onDismiss);
  useEffect(() => {
    onDismissRef.current = onDismiss;
  }, [onDismiss]);

  useEffect(() => {
    const target = document.getElementById(containerId);
    if (!(target instanceof HTMLElement)) return undefined;
    target.classList.add("save-highlight");
    scrollTo(target);
    if (notice.focus) focusElement(target);
    return () => {
      target.classList.remove("save-highlight");
      if (target.dataset.saveFocus === "added") {
        target.removeAttribute("tabindex");
        delete target.dataset.saveFocus;
      }
    };
  }, [containerId, notice.focus, notice.id]);

  useEffect(() => {
    const node = rootRef.current;
    let left = SAVE_NOTICE_MS;
    let started = Date.now();
    let timer = window.setTimeout(() => onDismissRef.current(), left);
    const pause = () => {
      window.clearTimeout(timer);
      left -= Date.now() - started;
      if (left < 0) left = 0;
    };
    const resume = () => {
      window.clearTimeout(timer);
      started = Date.now();
      timer = window.setTimeout(() => onDismissRef.current(), left);
    };
    node?.addEventListener("pointerenter", pause);
    node?.addEventListener("pointerleave", resume);
    node?.addEventListener("focusin", pause);
    const onFocusOut = (event: FocusEvent) => {
      if (!node?.contains(event.relatedTarget as Node | null)) resume();
    };
    node?.addEventListener("focusout", onFocusOut);
    return () => {
      window.clearTimeout(timer);
      node?.removeEventListener("pointerenter", pause);
      node?.removeEventListener("pointerleave", resume);
      node?.removeEventListener("focusin", pause);
      node?.removeEventListener("focusout", onFocusOut);
    };
  }, [notice.id]);

  const next = notice.next;
  return (
    <div className="local-feedback" ref={rootRef}>
      <p role="status" aria-live="polite" aria-atomic="true">
        {notice.text}
        {notice.detail ? ` ${notice.detail}` : ""}
      </p>
      <div className="local-feedback-actions">
        {next?.href ? <a href={next.href}>{next.label}</a> : null}
        {next && !next.href && next.onClick ? (
          <button type="button" onClick={next.onClick}>{next.label}</button>
        ) : null}
        <button type="button" onClick={onDismiss}>Fermer le message</button>
      </div>
    </div>
  );
}

/**
 * Renders the acknowledgement inside `place` (the triggering control).
 * When `highlightId` is mounted, the message moves into that created or modified row.
 */
export function SaveNoticeHost({
  place,
  notice,
  onDismiss,
}: {
  place: string;
  notice: SaveNotice | null;
  onDismiss: () => void;
}) {
  const active = notice?.targetId === place ? notice : null;
  const highlightId = active?.highlightId;
  const [found, setFound] = useState<{ id: string; node: HTMLElement } | null>(null);
  const row = found && highlightId === found.id ? found.node : null;

  useEffect(() => {
    if (!highlightId) return undefined;
    let seen: HTMLElement | null = null;
    const look = () => {
      const node = document.getElementById(highlightId);
      if (!(node instanceof HTMLElement)) {
        if (seen) {
          seen = null;
          setFound(null);
        }
        return;
      }
      if (node !== seen) {
        seen = node;
        setFound({ id: highlightId, node });
      }
    };
    const first = window.setTimeout(look, 0);
    const timer = window.setInterval(look, 100);
    const stop = window.setTimeout(() => window.clearInterval(timer), 4000);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
      window.clearTimeout(stop);
    };
  }, [highlightId, active?.id]);

  if (!active) return null;
  const containerId = row ? highlightId ?? active.targetId : active.targetId;
  const view = <LocalFeedbackView notice={active} containerId={containerId} onDismiss={onDismiss} />;
  if (row) return createPortal(view, row);
  return view;
}

export default LocalFeedbackView;
