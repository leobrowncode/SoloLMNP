import { expect, test } from "vitest";
import type { Account } from "../api/ledger";
import {
  alignAssetDraft,
  assetAccountChoices,
  categoryOfAccount,
  componentAssetChoices,
  depreciationAccountChoices,
  mirrorDepreciation,
} from "./assetAccounts";

const accounts: Account[] = [
  ["211000", "Terrains"],
  ["213000", "Constructions"],
  ["213100", "Construction inactive"],
  ["213500", "Installations"],
  ["218300", "Matériel"],
  ["218400", "Mobilier"],
  ["218500", "Autre"],
  ["281300", "Amort. constructions"],
  ["281350", "Amort. installations"],
  ["281830", "Amort. matériel"],
  ["281840", "Amort. mobilier"],
  ["281850", "Amort. autre"],
  ["512000", "Banques"],
].map(([number, label], index) => ({
  number: number ?? "",
  label: label ?? "",
  account_type: "ASSET",
  active: index !== 2,
}));

test("mirrors the chart and ignores depreciation accounts", () => {
  expect(mirrorDepreciation("213000")).toBe("281300");
  expect(mirrorDepreciation("213500")).toBe("281350");
  expect(mirrorDepreciation("218400")).toBe("281840");
  expect(mirrorDepreciation("211000")).toBe("281100");
  expect(mirrorDepreciation("213")).toBeNull();
  expect(categoryOfAccount("213500")).toBe("IMPROVEMENT");
  expect(categoryOfAccount("213000")).toBe("BUILDING");
  expect(categoryOfAccount("281300")).toBeNull();
  expect(categoryOfAccount("512000")).toBeNull();
});

test("filters asset and depreciation choices by category", () => {
  expect(assetAccountChoices(accounts, "BUILDING").map(([number]) => number)).toEqual(["213000"]);
  expect(assetAccountChoices(accounts, "LAND").map(([number]) => number)).toEqual(["211000"]);
  expect(assetAccountChoices(accounts, "FURNITURE").map(([number]) => number)).toEqual(["218400"]);
  expect(assetAccountChoices(accounts, "OTHER").map(([number]) => number)).toEqual(["218500"]);
  expect(depreciationAccountChoices(accounts, "213000").map(([number]) => number)).toEqual(["281300"]);
  expect(depreciationAccountChoices(accounts, "218400").map(([number]) => number)).toEqual(["281840"]);
  expect(componentAssetChoices(accounts).map(([number]) => number)).toEqual(["213000", "213500"]);
});

test("realigns accounts when the category changes and leaves a component label alone", () => {
  const moved = alignAssetDraft(accounts, {
    category: "FURNITURE",
    asset_account: "213000",
    depreciation_account: "281300",
  }, "category", "asset");
  expect(moved).toEqual({ asset_account: "218400", depreciation_account: "281840" });
  expect(alignAssetDraft(accounts, {
    category: "STRUCTURE",
    asset_account: "213500",
    depreciation_account: "281300",
  }, "category", "component")).toEqual({});
  expect(alignAssetDraft(accounts, {
    category: "STRUCTURE",
    asset_account: "213500",
    depreciation_account: "281300",
  }, "asset_account", "component")).toEqual({ depreciation_account: "281350" });
});
