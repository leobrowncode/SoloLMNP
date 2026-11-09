import { describe, expect, it } from "vitest";
import { guideNoteForOperations } from "./declarationSetup";

describe("guideNoteForOperations", () => {
  it("hides the property reminder once a property exists and the bank is missing", () => {
    const note = guideNoteForOperations(
      { guideNote: "Exercice 2025 enregistré. Indiquez le logement." },
      1,
      0,
    );
    expect(note).toBe("Logement enregistré. Ajoutez un compte bancaire.");
  });

  it("clears the banner when both property and bank exist", () => {
    expect(guideNoteForOperations(
      { guideNote: "Exercice 2025 enregistré. Indiquez le logement." },
      1,
      1,
    )).toBe("");
  });
});
