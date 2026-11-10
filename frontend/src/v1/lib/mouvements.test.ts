import { describe, expect, it } from "vitest";
import { parserCsvMouvements, totalParCompte } from "./mouvements";

const EXEMPLE = `date,piece,libelle,compte,debit_centimes,credit_centimes
2025-07-15,LOY-1,Loyer,706000,0,200000
2025-07-20,PNO-1,Assurance,616000,20000,0`;

describe("mouvements", () => {
  it("parse le CSV v1", () => {
    const lignes = parserCsvMouvements(EXEMPLE);
    expect(lignes).toHaveLength(2);
    expect(lignes[0]?.compte).toBe("706000");
  });

  it("totalise par compte", () => {
    const lignes = parserCsvMouvements(EXEMPLE);
    expect(totalParCompte(lignes, "706000")).toBe(200000);
  });
});
