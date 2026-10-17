import { describe, expect, it } from "vitest";
import {
  buildPieceReference,
  defaultType,
  findType,
  slugifyParty,
  typesFor,
} from "./operationTypes";

describe("operationTypes", () => {
  it("slugifies counterparties and falls back when empty", () => {
    expect(slugifyParty("Dupont")).toBe("Dupont");
    expect(slugifyParty("Jean-François")).toBe("JeanFrancois");
    expect(slugifyParty("Éléonore d'Arc")).toBe("EleonoredArc");
    expect(slugifyParty("  ")).toBe("SANSNOM");
    expect(slugifyParty("A".repeat(40))).toHaveLength(24);
  });

  it("builds PREFIX-YYYY-MM-Party references", () => {
    expect(buildPieceReference("LOY", "2026-03-15", "Dupont")).toBe("LOY-2026-03-Dupont");
    expect(buildPieceReference("TROP", "2026-01-01", "Marie Curie")).toBe("TROP-2026-01-MarieCurie");
    expect(buildPieceReference("ASS", "", "")).toBe("ASS-XXXX-XX-SANSNOM");
  });

  it("exposes default types and accounts for revenue and expense", () => {
    expect(defaultType("REVENUE")).toEqual({ code: "LOY", label: "Loyer", account: "706000" });
    expect(defaultType("EXPENSE")).toEqual({ code: "ASS", label: "Assurance", account: "616000" });
    expect(findType("REVENUE", "CHG")?.account).toBe("706000");
    expect(findType("EXPENSE", "ENT")?.account).toBe("615000");
    expect(typesFor("REVENUE").map((item) => item.code)).toEqual(["LOY", "TROP", "CHG", "AUT"]);
  });
});
