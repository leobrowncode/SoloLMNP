import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { analyze, type Pair } from "./contrast";

const HERE = dirname(fileURLToPath(import.meta.url));

function sheet(name: string): { file: string; css: string } {
  return { file: name, css: readFileSync(join(HERE, name), "utf8") };
}

const analysis = analyze(readFileSync(join(HERE, "tokens.css"), "utf8"), [
  sheet("style.css"),
  sheet("features/ledger.css"),
]);

function pairsFor(selector: string, kind?: Pair["kind"]): Pair[] {
  return analysis.pairs.filter((pair) => pair.selector.includes(selector) && (kind === undefined || pair.kind === kind));
}

describe("contraste WCAG AA", () => {
  it("calcule un contraste suffisant pour chaque paire de jetons utilisée", () => {
    expect(analysis.rawColorViolations).toEqual([]);
    expect(analysis.stateViolations).toEqual([]);
    expect(analysis.violations).toEqual([]);
    expect(analysis.pairs.length).toBeGreaterThan(40);
  });

  it("relève les numéros d’étape, l’introduction et les descriptions signalés par l’audit", () => {
    for (const selector of [".stage-number", ".nav-step", ".step-index", ".intro-description", ".dossier-hint"]) {
      const pairs = pairsFor(selector, "text").concat(pairsFor(selector, "disabled"));
      const text = pairs.filter((pair) => pair.property === "color" || pair.property === "background-text" || pair.property === "disabled");
      expect(text.length, selector).toBeGreaterThan(0);
      for (const pair of text) expect(pair.ratio).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("garde le focus, les bordures de contrôle et les icônes au-dessus de 3:1", () => {
    const ui = analysis.pairs.filter((pair) => pair.kind === "ui");
    expect(ui.length).toBeGreaterThan(5);
    for (const pair of ui) expect(pair.ratio).toBeGreaterThanOrEqual(3);
    expect(pairsFor(":focus-visible", "ui").length).toBeGreaterThan(0);
  });

  it("distingue survol, focus, actif et désactivé", () => {
    const css = `${sheet("style.css").css}\n${sheet("features/ledger.css").css}`;
    for (const selector of [
      ".sidebar nav a:hover",
      ".sidebar nav a.nav-active",
      "button:focus-visible",
      "button:disabled",
      ".ledger-page button:hover",
      ".ledger-page button:active",
      '.ledger-page button[aria-pressed="true"]',
      ".ledger-page button:disabled",
      ".section-heading button:hover",
      ".section-heading button:active",
      ".nav-toggle:hover",
      ".nav-toggle:active",
      ".dashboard-continue:hover",
      ".dashboard-continue:active",
    ]) {
      expect(css, selector).toContain(selector);
    }
    const disabled = analysis.pairs.filter((pair) => pair.kind === "disabled");
    expect(disabled.length).toBeGreaterThan(0);
    for (const pair of disabled) expect(pair.ratio).toBeGreaterThanOrEqual(3);
  });
});
