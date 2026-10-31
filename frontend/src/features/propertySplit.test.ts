import { describe, expect, it } from "vitest";
import { formatCents } from "../lib/format";
import { propertySplitGap, proposeLandFromArea } from "./propertySplit";

function euros(cents: bigint): string {
  return formatCents(cents);
}

describe("property land split", () => {
  it("proposes land and building from an optional area and price per square metre", () => {
    expect(proposeLandFromArea({
      lot_m2: "10",
      price_m2: "2000,00",
      acquisition_price: "100000,00",
    }, "price_m2")).toEqual({
      land_value: "20000.00",
      building_value: "80000.00",
    });
  });

  it("does not propose a split when the area or the price per square metre is empty", () => {
    expect(proposeLandFromArea({
      lot_m2: "",
      price_m2: "",
      acquisition_price: "100000.00",
    }, "acquisition_price")).toEqual({});
    expect(proposeLandFromArea({
      lot_m2: "10",
      price_m2: "",
      acquisition_price: "100000.00",
    }, "lot_m2")).toEqual({});
  });

  it("explains a land and building gap in one sentence", () => {
    const less = propertySplitGap({
      acquisition_price: "100000.00",
      land_value: "20000.00",
      building_value: "70000.00",
    });
    expect(less).toBe(
      `Le terrain et le bâtiment totalisent ${euros(9000000n)}, `
      + `soit ${euros(1000000n)} de moins que le prix d’acquisition (${euros(10000000n)}).`,
    );
    const more = propertySplitGap({
      acquisition_price: "100000,00",
      land_value: "30000,00",
      building_value: "80000,00",
    });
    expect(more).toContain("de plus que le prix d’acquisition");
    expect(propertySplitGap({
      acquisition_price: "100000.00",
      land_value: "20000.00",
      building_value: "80000.00",
    })).toBe("");
  });

  it("stays silent when the split fields are absent or not amounts", () => {
    expect(propertySplitGap({ name: "Studio" })).toBe("");
    expect(propertySplitGap({
      acquisition_price: "abc",
      land_value: "1,00",
      building_value: "1,00",
    })).toBe("");
  });
});
