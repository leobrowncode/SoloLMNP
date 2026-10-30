import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";
import HelpTip from "./HelpTip";

function domRect(box: { left: number; top: number; width: number; height: number }): DOMRect {
  const right = box.left + box.width;
  const bottom = box.top + box.height;
  return {
    x: box.left,
    y: box.top,
    left: box.left,
    top: box.top,
    right,
    bottom,
    width: box.width,
    height: box.height,
    toJSON() { return this; },
  };
}

function mockViewport(width: number, height = 700) {
  Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
  Object.defineProperty(window, "innerHeight", { configurable: true, value: height });
  document.documentElement.style.width = `${width}px`;
  document.documentElement.style.overflowX = "auto";
  document.body.style.width = `${width}px`;
  document.body.style.margin = "0";
  document.body.style.overflowX = "auto";
}

afterEach(() => {
  document.documentElement.style.width = "";
  document.documentElement.style.overflowX = "";
  document.body.style.width = "";
  document.body.style.margin = "";
  document.body.style.overflowX = "";
  vi.restoreAllMocks();
});

describe("keyboard", () => {
  test("Escape, a second click and an outside click close the popover", async () => {
    const user = userEvent.setup();
    render(
      <div>
        <HelpTip label="Plafond">L’excédent est reporté, pas perdu.</HelpTip>
        <button type="button">Ailleurs</button>
      </div>,
    );
    const trigger = screen.getByRole("button", { name: "Aide : Plafond" });

    await user.click(trigger);
    const panel = screen.getByRole("tooltip");
    expect(panel).toHaveTextContent("L’excédent est reporté, pas perdu.");
    expect(panel).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();

    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    await user.click(screen.getByRole("tooltip"));
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    await user.click(trigger);
    await user.click(screen.getByRole("button", { name: "Ailleurs" }));
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });
});

describe("screen reader", () => {
  test("exposes the open state, an id relation and an accessible name", async () => {
    const user = userEvent.setup();
    render(<HelpTip label="Déficit">Un déficit LMNP se reporte sur les revenus LMNP.</HelpTip>);
    const trigger = screen.getByRole("button", { name: "Aide : Déficit" });

    expect(trigger).toHaveAccessibleName("Aide : Déficit");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    const controls = trigger.getAttribute("aria-controls");
    const describedBy = trigger.getAttribute("aria-describedby");
    expect(controls).toBeTruthy();
    expect(describedBy).toBe(controls);
    const closedPanel = document.getElementById(controls ?? "");
    expect(closedPanel).not.toBeNull();
    expect(closedPanel).toHaveAttribute("role", "tooltip");
    expect(closedPanel).toHaveAttribute("id", controls);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(trigger).toHaveAttribute("aria-controls", controls);
    expect(trigger).toHaveAttribute("aria-describedby", describedBy);
    const panel = screen.getByRole("tooltip");
    expect(panel).toBe(closedPanel);
    expect(panel).toHaveTextContent("Un déficit LMNP se reporte sur les revenus LMNP.");
    expect(panel).not.toHaveAttribute("hidden");

    const style = getComputedStyle(trigger);
    expect(parseFloat(style.minWidth)).toBeGreaterThanOrEqual(44);
    expect(parseFloat(style.minHeight)).toBeGreaterThanOrEqual(44);
    expect(parseFloat(style.width)).toBeGreaterThanOrEqual(44);
    expect(parseFloat(style.height)).toBeGreaterThanOrEqual(44);
  });
});

describe("mobile viewport", () => {
  test.each([320, 390, 768])("does not widen the document at %ipx", async (width) => {
    mockViewport(width);
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
      if (this.classList.contains("help-tip-btn")) {
        return domRect({ left: width - 48, top: 24, width: 44, height: 44 });
      }
      if (this.classList.contains("help-tip-panel")) {
        const left = this.style.left ? Number.parseFloat(this.style.left) : 12;
        const top = this.style.top ? Number.parseFloat(this.style.top) : width;
        const panelWidth = this.style.width ? Number.parseFloat(this.style.width) : Math.min(288, width);
        return domRect({ left, top, width: panelWidth, height: 140 });
      }
      return domRect({ left: 0, top: 0, width: 0, height: 0 });
    });

    const user = userEvent.setup();
    render(
      <div style={{ width: `${width}px` }}>
        <HelpTip label="Plafond">
          L’amortissement déductible ne peut pas dépasser les loyers diminués des autres charges.
        </HelpTip>
      </div>,
    );
    const before = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
    await user.click(screen.getByRole("button", { name: "Aide : Plafond" }));
    const panel = screen.getByRole("tooltip");
    const left = Number.parseFloat(panel.style.left);
    const panelWidth = Number.parseFloat(panel.style.width);
    expect(left).toBeGreaterThanOrEqual(0);
    expect(panelWidth).toBeGreaterThan(0);
    expect(left + panelWidth).toBeLessThanOrEqual(width);
    const rect = panel.getBoundingClientRect();
    expect(rect.left).toBeGreaterThanOrEqual(0);
    expect(rect.right).toBeLessThanOrEqual(width);
    const after = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
    expect(after).toBeLessThanOrEqual(Math.max(before, width));
  });
});
