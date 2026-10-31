import { expect, test } from "vitest";
import { parseAmountToCents } from "../lib/format";
import { presentPlan } from "./planPreview";

const land = { kind: "LAND", label: "Terrain", amount: "20000.00" };
const building = { kind: "BUILDING", label: "Construction — Bien fictif", amount: "134262.00" };
const structure = { kind: "COMPONENT", label: "Gros œuvre", amount: "80000.00" };
const roof = { kind: "COMPONENT", label: "Toiture", amount: "54262.00" };

test("components that already total the building are not added again", () => {
  const presented = presentPlan([land, building, structure, roof]);
  expect(presented.buildingIsBreakdown).toBe(true);
  expect(presented.building).toBe(building);
  expect(presented.lines.map((item) => item.kind)).toEqual(["LAND", "COMPONENT", "COMPONENT"]);
  const additive = presented.lines.reduce((sum, item) => sum + parseAmountToCents(item.amount), 0n);
  const once = parseAmountToCents(land.amount) + parseAmountToCents(building.amount);
  expect(additive).toBe(once);
  expect(additive).not.toBe(once + parseAmountToCents(building.amount));
});

test("keeps the building row when components do not sum to it", () => {
  const presented = presentPlan([land, building, structure]);
  expect(presented.buildingIsBreakdown).toBe(false);
  expect(presented.lines.map((item) => item.label)).toEqual([
    "Terrain",
    "Construction — Bien fictif",
    "Gros œuvre",
  ]);
});
