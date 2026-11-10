import { describe, expect, it } from "vitest";
import { siretValide } from "./siret";

describe("siretValide", () => {
  it("accepte une clé Luhn valide", () => {
    expect(siretValide("12345678900015")).toBe(true);
  });

  it("refuse le SIRET fictif du golden sans Luhn", () => {
    expect(siretValide("12345678900017")).toBe(false);
  });
});
