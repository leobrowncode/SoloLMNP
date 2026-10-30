import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import "./ledger.css";

const PANEL_MARGIN = 12;
const PANEL_GAP = 8;
const PANEL_MAX_WIDTH = 288;

function clampHelpPanel(box: {
  triggerLeft: number;
  triggerTop: number;
  triggerWidth: number;
  triggerBottom: number;
  panelHeight: number;
  viewportWidth: number;
  viewportHeight: number;
}): { left: number; top: number; width: number } {
  const margin = PANEL_MARGIN;
  const viewportWidth = Math.max(0, box.viewportWidth);
  const available = Math.max(0, viewportWidth - margin * 2);
  const width = available === 0 ? viewportWidth : Math.min(PANEL_MAX_WIDTH, available);
  const minLeft = available === 0 ? 0 : margin;
  const maxLeft = available === 0 ? 0 : margin + Math.max(0, available - width);
  const centered = box.triggerLeft + box.triggerWidth / 2 - width / 2;
  const left = Math.min(Math.max(centered, minLeft), maxLeft);
  let top = box.triggerBottom + PANEL_GAP;
  const bottomLimit = Math.max(margin, box.viewportHeight - margin);
  if (box.panelHeight > 0 && top + box.panelHeight > bottomLimit) {
    const above = box.triggerTop - PANEL_GAP - box.panelHeight;
    top = above >= margin ? above : Math.max(margin, bottomLimit - box.panelHeight);
  }
  return { left, top, width };
}

function placePanel(button: HTMLButtonElement, panel: HTMLElement) {
  const trigger = button.getBoundingClientRect();
  const measured = panel.getBoundingClientRect();
  const next = clampHelpPanel({
    triggerLeft: trigger.left,
    triggerTop: trigger.top,
    triggerWidth: trigger.width,
    triggerBottom: trigger.bottom,
    panelHeight: measured.height,
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
  });
  panel.style.left = `${next.left}px`;
  panel.style.right = "auto";
  panel.style.top = `${next.top}px`;
  panel.style.bottom = "auto";
  panel.style.width = `${next.width}px`;
  panel.style.maxWidth = `${next.width}px`;
  panel.style.transform = "none";
}

export default function HelpTip({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const panelId = `help-tip-${useId().replace(/:/g, "")}`;
  const rootRef = useRef<HTMLSpanElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLSpanElement>(null);

  useLayoutEffect(() => {
    if (!open) return;
    const button = buttonRef.current;
    const panel = panelRef.current;
    if (!button || !panel) return;
    const place = () => placePanel(button, panel);
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.focus({ preventScroll: true });
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      setOpen(false);
      buttonRef.current?.focus({ preventScroll: true });
    };
    const onPointer = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (rootRef.current?.contains(target) || panelRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  return (
    <span className="help-tip" ref={rootRef}>
      <button
        ref={buttonRef}
        type="button"
        className="help-tip-btn"
        aria-label={`Aide : ${label}`}
        aria-expanded={open}
        aria-controls={panelId}
        aria-describedby={panelId}
        style={{ width: 44, height: 44, minWidth: 44, minHeight: 44 }}
        onClick={() => setOpen((value) => !value)}
      >
        ?
      </button>
      {createPortal(
        <span
          ref={panelRef}
          id={panelId}
          role="tooltip"
          tabIndex={-1}
          hidden={!open}
          className="help-tip-panel"
        >
          {children}
        </span>,
        document.body,
      )}
    </span>
  );
}
