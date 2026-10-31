import { expect, test } from "vitest";
import { contentHasPaidLines } from "./csvPaidLines";

const HEADER = "Nature;Date;Type;Tiers;Montant;Libellé;Référence de pièce;Déjà payée";

test("detects an already-paid line from the French header", () => {
  const paid = `${HEADER}\nRecette;15/03/2025;LOY;Dupont;800,00;Loyer;LOY-1;oui`;
  const unpaid = `${HEADER}\nDépense;20/03/2025;ASS;Assureur;240,00;Entretien;ENT-1;non`;
  expect(contentHasPaidLines(paid)).toBe(true);
  expect(contentHasPaidLines(unpaid)).toBe(false);
  expect(contentHasPaidLines(`\uFEFF${HEADER}\nRecette;15/03/2025;LOY;Dupont;800,00;Loyer;LOY-1;Oui`)).toBe(true);
});

test("reads a mapped column and a tab-separated sheet", () => {
  const sheet = "Quand\tPayé\n15/03/2025\toui";
  expect(contentHasPaidLines(sheet, "Payé")).toBe(true);
  expect(contentHasPaidLines("Nature;Montant\nRecette;800,00")).toBe(false);
  expect(contentHasPaidLines(HEADER)).toBe(false);
});
