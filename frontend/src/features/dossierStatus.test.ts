import { describe, expect, it } from "vitest";
import { showsDossierIndicator, showsOperationalStorage } from "./dossierStatus";

const dossier = {
  status: "pret_a_verifier" as const,
  label: "Prêt à vérifier" as const,
  fiscal_year_id: 1,
  year: 2026,
  year_status: "OPEN" as const,
  vintage_status: "research_only" as const,
};

describe("dossier indicator", () => {
  it("shows the business status only after a successful load", () => {
    expect(showsDossierIndicator("loaded", true, dossier)).toBe(true);
    expect(showsDossierIndicator("loading", true, dossier)).toBe(false);
    expect(showsDossierIndicator("error", true, dossier)).toBe(false);
    expect(showsDossierIndicator("loaded", false, dossier)).toBe(false);
    expect(showsDossierIndicator("loaded", true, null)).toBe(false);
  });

  it("drops a stale green storage flag when the read is not current", () => {
    expect(showsOperationalStorage("loaded", true)).toBe(true);
    expect(showsOperationalStorage("error", true)).toBe(false);
    expect(showsOperationalStorage("loading", true)).toBe(false);
    expect(showsOperationalStorage("loaded", false)).toBe(false);
  });

  it("rejects a declarable dossier label", () => {
    expect(showsDossierIndicator("loaded", true, {
      ...dossier,
      status: "declarable",
      label: "Déclarable",
      vintage_status: "declarable",
    })).toBe(false);
  });
});
