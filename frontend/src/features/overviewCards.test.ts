import { describe, expect, it } from "vitest";
import { dashboardFixture } from "./dashboardFixture";
import { presentStep } from "./overviewCards";

function contextOf(kind: Parameters<typeof dashboardFixture>[0]) {
  const board = dashboardFixture(kind);
  return {
    board,
    context: {
      sharedSummary: board.progression.summary,
      currentStep: board.progression.current_step,
    },
  };
}

describe("overview card lines", () => {
  it("keeps one status line on an empty dossier and does not copy the same lack", () => {
    const { board, context } = contextOf("empty");
    const cards = board.steps.map((step) => presentStep(step, context));
    const sentences = cards.flatMap((card) => card.summary === null ? [] : [card.summary]);
    expect(sentences.filter((line) => line.includes("L’activité n’est pas créée."))).toEqual([
      "L’activité n’est pas créée.",
    ]);
    expect(cards.every((card) => card.actions.length === 0 && card.missing.length === 0)).toBe(true);
    expect(cards.every((card) => !card.showEvent)).toBe(true);
    expect(cards.filter((card) => card.summary === null && card.statusLabel === "À faire")).toHaveLength(
      board.steps.length - 1,
    );
  });

  it("shows a different empty-dossier sentence once", () => {
    const { board, context } = contextOf("empty");
    const assets = board.steps.find((step) => step.id === "assets");
    if (!assets) throw new Error("Étape immobilisations absente.");
    const card = presentStep(
      { ...assets, summary: "Aucun bien n’est enregistré." },
      context,
    );
    expect(card.statusLabel).toBe("À faire");
    expect(card.summary).toBe("Aucun bien n’est enregistré.");
    expect(card.missing).toEqual([]);
  });

  it("turns a repeated in-progress sentence into one action link", () => {
    const { board, context } = contextOf("partial");
    const structure = board.steps.find((step) => step.id === "structure");
    if (!structure) throw new Error("Étape structure absente.");
    const card = presentStep(structure, context);
    expect(card.statusLabel).toBe("En cours");
    expect(card.summary).toBe("Le SIREN n’est pas renseigné.");
    expect(card.missing).toEqual([]);
    expect(card.actions).toEqual([
      { label: "Renseigner le SIREN", href: "/comptabilite/brouillons#identite-liasse" },
    ]);
    expect(card.showEvent).toBe(true);
  });

  it("leaves the export sentence on the filing card only", () => {
    const { board, context } = contextOf("blocked");
    const filing = board.steps.find((step) => step.id === "filing");
    if (!filing) throw new Error("Étape fiscalité absente.");
    const card = presentStep(filing, context);
    expect(card.summary).toContain("Liasse Bloquée");
    expect(card.summary).not.toBe(context.sharedSummary);
  });
});
