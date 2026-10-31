import { expect, test } from "vitest";
import {
  depreciationPostedSentence, isSharedText, postedTotalCents, repeatedTexts,
} from "./assetJustification";

const SHARED = "Durée d’usage proposée pour un logement. Ce n’est pas un barème légal.";

test("keeps a text that is repeated and drops a text that is unique", () => {
  expect(repeatedTexts([SHARED, SHARED, SHARED, "Toiture refaite en 2020"])).toEqual([SHARED]);
  expect(repeatedTexts(["Une seule ligne"])).toEqual([]);
  expect(repeatedTexts(["", "  ", null, undefined])).toEqual([]);
  expect(isSharedText(SHARED, [SHARED])).toBe(true);
  expect(isSharedText("Toiture refaite en 2020", [SHARED])).toBe(false);
  expect(isSharedText("  ", [SHARED])).toBe(false);
});

test("sums only the periods the batch actually posted", () => {
  const periods = [
    { id: 2, amount: "120.92" },
    { id: 3, amount: "80.00" },
    { id: 4, amount: "40.00" },
  ];
  expect(postedTotalCents(periods, [
    { period_id: 2, status: "posted" },
    { period_id: 3, status: "error" },
    { period_id: 4, status: "posted" },
  ])).toBe(16092n);
  expect(depreciationPostedSentence(3, 24092n, false)).toMatch(/^3 dotations comptabilisées, total .+€\.$/);
  expect(depreciationPostedSentence(1, 12092n, false)).toMatch(/^1 dotation comptabilisée, total .+€\.$/);
  expect(depreciationPostedSentence(3, 24092n, true)).toContain("déjà comptabilisées, sans doublon");
  expect(depreciationPostedSentence(3, 24092n, false).split(".").filter(Boolean)).toHaveLength(1);
});
