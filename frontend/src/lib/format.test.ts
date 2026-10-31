import { describe, expect, it } from "vitest";
import {
  AMOUNT_INPUT_ERROR,
  DATE_HINT,
  DATE_PLACEHOLDER,
  centsToApiAmount,
  enumLabel,
  frenchCount,
  importPreviewSummary,
  importValidOnlyLabel,
  formatAmount,
  formatCents,
  formatEuros,
  formatClockTime,
  formatIsoDate,
  formatTimestamp,
  parseAmountToCents,
} from "./format";
import { cents } from "../api/ledger";

function spaces(value: string): string {
  return value.replace(/[\u00a0\u202f\u2009\u2007]/g, " ");
}

describe("French amounts", () => {
  it("parses French and API amounts to exact cents", () => {
    expect(parseAmountToCents("1 234,56")).toBe(123456n);
    expect(parseAmountToCents("1\u00a0234,56")).toBe(123456n);
    expect(parseAmountToCents("1\u202f234,56")).toBe(123456n);
    expect(parseAmountToCents("1.234,56")).toBe(123456n);
    expect(parseAmountToCents("1,234.56")).toBe(123456n);
    expect(parseAmountToCents("1234.56")).toBe(123456n);
    expect(parseAmountToCents("1234,5")).toBe(123450n);
    expect(parseAmountToCents("-1 234,56")).toBe(-123456n);
    expect(parseAmountToCents("90071992547409,91")).toBe(9007199254740991n);
  });

  it("rejects incomplete or floating amounts", () => {
    for (const invalid of ["", "0.001", "1e4", "NaN", "12,345", "1.2.3"]) {
      expect(() => parseAmountToCents(invalid)).toThrow(AMOUNT_INPUT_ERROR);
    }
    expect(() => cents("-1")).toThrow(AMOUNT_INPUT_ERROR);
  });

  it("keeps the API decimal exact and displays fr-FR currency from cents", () => {
    const centsValue = parseAmountToCents("90071992547409,91");
    expect(centsToApiAmount(centsValue)).toBe("90071992547409.91");
    expect(spaces(formatCents(centsValue))).toBe("90 071 992 547 409,91 €");
    expect(spaces(formatEuros("1234.56"))).toBe("1 234,56 €");
    expect(spaces(formatAmount("1234.56"))).toBe("1 234,56");
    expect(spaces(formatCents(0n))).toBe("0,00 €");
    expect(spaces(formatEuros("-10.01"))).toBe("-10,01 €");
  });
});

describe("French dates and enums", () => {
  it("shows dates as JJ/MM/AAAA and keeps the input hint", () => {
    expect(DATE_PLACEHOLDER).toBe("JJ/MM/AAAA");
    expect(DATE_HINT).toBe("Format JJ/MM/AAAA.");
    expect(formatIsoDate("2026-03-01")).toBe("01/03/2026");
    expect(formatIsoDate("2026-03-01T08:15:00Z")).toBe("01/03/2026");
    expect(formatTimestamp("2026-03-01T08:15:00Z")).toBe("01/03/2026 08:15");
    expect(formatIsoDate("pas une date")).toBe("pas une date");
    expect(formatClockTime(new Date(2026, 9, 30, 15, 42))).toBe("15:42");
    expect(formatClockTime(new Date(2026, 9, 30, 9, 5))).toBe("09:05");
  });

  it("translates visible enums and leaves an unknown code visible", () => {
    expect(enumLabel("assetCategory", "LAND")).toBe("Terrain");
    expect(enumLabel("assetCategory", "BUILDING")).toBe("Construction");
    expect(enumLabel("accountType", "LIABILITY")).toBe("Dette");
    expect(enumLabel("accountType", "EXPENSE")).toBe("Charge");
    expect(enumLabel("entrySource", "EXPENSE")).toBe("Dépenses");
    expect(enumLabel("operationKind", "EXPENSE")).toBe("Dépense");
    expect(enumLabel("yearStatus", "CLOSED")).toBe("clôturé");
    expect(enumLabel("yearStatus", "READY_TO_CLOSE")).toBe("prêt à clôturer");
    expect(enumLabel("entrySource", "OPENING")).toBe("À-nouveaux");
    expect(enumLabel("importStatus", "warning")).toBe("Avertissement");
    expect(enumLabel("accountType", "PASSIF")).toBe("PASSIF");
  });

  it("counts import lines in French", () => {
    expect(frenchCount(0, "ligne", "lignes")).toBe("0 lignes");
    expect(frenchCount(1, "valide", "valides")).toBe("1 valide");
    expect(frenchCount(11, "rejet", "rejets")).toBe("11 rejets");
    expect(importPreviewSummary({
      count: 12, valid: 1, error: 11, duplicate: 0, warning: 0,
    })).toBe("12 lignes : 1 valide, 11 rejets.");
    expect(importPreviewSummary({
      count: 2, valid: 2, error: 0, duplicate: 0, warning: 0,
    })).toBe("2 lignes : 2 valides.");
    expect(importValidOnlyLabel(1)).toBe("Importer uniquement la ligne valide");
    expect(importValidOnlyLabel(11)).toBe("Importer uniquement les 11 lignes valides");
  });
});
