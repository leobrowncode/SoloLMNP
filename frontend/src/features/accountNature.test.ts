import { describe, expect, it } from "vitest";
import {
  ACCOUNT_NATURES,
  ACCOUNT_TYPES,
  accountNatureLabel,
  accountUsageLabel,
  matchesChartFilters,
} from "./accountNature";

describe("account nature", () => {
  it("translates the five ledger account types", () => {
    expect(ACCOUNT_TYPES).toEqual(["ASSET", "LIABILITY", "EQUITY", "EXPENSE", "INCOME"]);
    expect(accountNatureLabel("ASSET")).toBe("Actif");
    expect(accountNatureLabel("LIABILITY")).toBe("Dette");
    expect(accountNatureLabel("EQUITY")).toBe("Capitaux");
    expect(accountNatureLabel("EXPENSE")).toBe("Charge");
    expect(accountNatureLabel("INCOME")).toBe("Produit");
    expect(ACCOUNT_NATURES.ASSET).toBe("Actif");
  });

  it("keeps an unknown account_type visible instead of calling it Actif", () => {
    expect(accountNatureLabel("PASSIF")).toBe("PASSIF");
    expect(accountNatureLabel("")).toBe("");
  });

  it("names both usage states without using the asset nature", () => {
    expect(accountUsageLabel(true)).toBe("Activé");
    expect(accountUsageLabel(false)).toBe("Inactif");
    expect(accountUsageLabel(true)).not.toBe(accountNatureLabel("ASSET"));
  });

  it("filters by nature and by usage independently", () => {
    const loan = { account_type: "LIABILITY", active: true };
    const expense = { account_type: "EXPENSE", active: false };
    expect(matchesChartFilters(loan, "LIABILITY", "active")).toBe(true);
    expect(matchesChartFilters(loan, "ASSET", "")).toBe(false);
    expect(matchesChartFilters(loan, "", "inactive")).toBe(false);
    expect(matchesChartFilters(expense, "EXPENSE", "inactive")).toBe(true);
    expect(matchesChartFilters(expense, "", "active")).toBe(false);
    expect(matchesChartFilters(expense, "", "")).toBe(true);
  });
});
