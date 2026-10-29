import { expect, test } from "vitest";
import { correctionMessage, editTitle, locked } from "./correction";

const posted = {
  locks: [
    {
      code: "DEPRECIATION_POSTED",
      fields: ["value", "life", "dates", "account"],
      message: "gelé",
    },
  ],
  calculated_periods: 0,
};

test("locked reads the group and ignores an unknown one", () => {
  expect(locked(posted, "value")).toBe(true);
  expect(locked(posted, "justification")).toBe(false);
  expect(locked(undefined, "value")).toBe(false);
});

test("edit title switches when every structural group is locked", () => {
  expect(editTitle("Mobilier", posted, ["value", "life", "dates", "account"])).toBe(
    "Préciser la justification de Mobilier",
  );
  expect(editTitle("Mobilier", posted, ["value", "dates", "account"])).toBe(
    "Préciser la justification de Mobilier",
  );
  expect(editTitle("Mobilier", undefined, ["value", "life"])).toBe("Modifier Mobilier");
});

test("correction message counts every invalidated output", () => {
  const text = correctionMessage({
    dropped_period_ids: [4, 5],
    fiscal_computations: 1,
    ready_years_reset: [2],
    snapshots_superseded: 1,
  });
  expect(text).toContain("2 période");
  expect(text).toContain("1 calcul");
  expect(text).toContain("1 exercice");
  expect(text).toContain("1 instantané");
  expect(text).toContain("FEC");
});
