import { describe, expect, it } from "vitest";
import { ENUM_LABELS } from "../lib/format";
import {
  EMPTY_CRITERIA, criteriaActive, filterList, groupByKey, listOutcome, matchesText,
} from "./listQuery";

const rows = [
  { label: "Mobilier salon", status: "CALCULATED", category: "FURNITURE" },
  { label: "Terrain", status: "POSTED", category: "LAND" },
  { label: "Équipement cuisine", status: "CALCULATED", category: "EQUIPMENT" },
];

describe("list query", () => {
  it("treats a successful empty collection as empty, and a filtered miss as no results", () => {
    expect(listOutcome(0, 0, false)).toBe("empty");
    expect(listOutcome(0, 0, true)).toBe("no-results");
    expect(listOutcome(3, 0, true)).toBe("no-results");
    expect(listOutcome(3, 2, true)).toBe("data");
    expect(listOutcome(3, 3, false)).toBe("data");
  });

  it("matches search without accents and keeps status and category independent", () => {
    expect(matchesText("Équipement cuisine", "equipement")).toBe(true);
    expect(criteriaActive(EMPTY_CRITERIA)).toBe(false);
    const selectors = {
      text: (row: (typeof rows)[number]) => row.label,
      status: (row: (typeof rows)[number]) => row.status,
      category: (row: (typeof rows)[number]) => row.category,
    };
    expect(filterList(rows, { ...EMPTY_CRITERIA, search: "terrain" }, selectors).map((row) => row.label)).toEqual(["Terrain"]);
    expect(filterList(rows, { ...EMPTY_CRITERIA, status: "POSTED" }, selectors)).toHaveLength(1);
    expect(filterList(rows, { ...EMPTY_CRITERIA, category: "FURNITURE", status: "POSTED" }, selectors)).toHaveLength(0);
    expect(filterList(rows, { ...EMPTY_CRITERIA, category: "FURNITURE" }, selectors)[0]?.label).toBe("Mobilier salon");
    expect(ENUM_LABELS.assetCategory.FURNITURE).toBe("Mobilier");
    expect(groupByKey(rows, (row) => row.status).map((group) => group.key)).toEqual(["CALCULATED", "POSTED"]);
  });
});
