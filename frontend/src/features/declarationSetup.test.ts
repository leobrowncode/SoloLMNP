import { describe, expect, it } from "vitest";
import {
  identityFromSiren,
  identityFromSiret,
  identityIssue,
  sirenDerivedFromSiret,
  suggestedExercise,
} from "./declarationSetup";

const empty = { siren: "", siret: "" };

describe("declaration identity", () => {
  it("fills the SIREN from the first nine digits of the SIRET", () => {
    const draft = identityFromSiret("123 456 789 00019", empty);
    expect(draft).toEqual({ siret: "12345678900019", siren: "123456789" });
    expect(sirenDerivedFromSiret(draft)).toBe(true);
    expect(identityIssue(draft)).toBe("");
  });

  it("clears a derived SIREN when the SIRET is removed", () => {
    const filled = identityFromSiret("12345678900019", empty);
    expect(identityFromSiret("", filled)).toEqual(empty);
  });

  it("keeps a SIREN typed on its own", () => {
    const typed = identityFromSiren("123456789", empty);
    expect(typed).toEqual({ siren: "123456789", siret: "" });
    expect(identityIssue(typed)).toBe("");
    expect(identityFromSiret("", typed)).toEqual(typed);
  });

  it("treats a 14-digit paste in the SIREN field as a SIRET", () => {
    expect(identityFromSiren("12345678900019", empty)).toEqual({
      siret: "12345678900019",
      siren: "123456789",
    });
  });

  it("refuses a partial SIRET and an empty identity", () => {
    expect(identityIssue(identityFromSiret("123456789000", empty))).toMatch(/14 chiffres/);
    expect(identityIssue(empty)).toMatch(/SIRET/);
    expect(identityIssue({ siren: "12345678", siret: "" })).toMatch(/9 chiffres/);
  });
});

describe("suggested exercise", () => {
  it("runs from the activity start to 31 December of that year", () => {
    expect(suggestedExercise("2026-04-06")).toEqual({
      start: "2026-04-06",
      end: "2026-12-31",
      vintage: "2026",
    });
  });

  it("ignores a missing or non-ISO start", () => {
    expect(suggestedExercise(null)).toBeNull();
    expect(suggestedExercise("06/04/2026")).toBeNull();
  });
});
