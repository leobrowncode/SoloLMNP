import { describe, expect, it } from "vitest";
import { parseApiErrorDetail, formFieldName, issuesForForm, importIssueLines } from "./errors";

describe("parseApiErrorDetail", () => {
  it("preserves business error metadata", () => {
    const detail = parseApiErrorDetail({
      code: "ACTIVITY_REQUIRED",
      message: "Initialisez l’activité.",
      action: { label: "Comptabilité", href: "/comptabilite" },
    });
    expect(detail.code).toBe("ACTIVITY_REQUIRED");
    expect(detail.action?.href).toBe("/comptabilite");
  });

  it("maps pydantic validation arrays to issues", () => {
    const detail = parseApiErrorDetail([
      { type: "missing", loc: ["body", "piece_reference"], msg: "Field required" },
    ]);
    expect(detail.code).toBe("VALIDATION_ERROR");
    expect(detail.issues?.[0]?.field).toBe("piece_reference");
  });

  it("keeps csv line numbers", () => {
    const detail = parseApiErrorDetail({
      code: "CSV_AMOUNT",
      message: "Montant invalide, ligne 3.",
      line: 3,
      location: "import",
    });
    expect(importIssueLines(detail)).toEqual([
      expect.objectContaining({ line: 3, message: "Montant invalide, ligne 3." }),
    ]);
  });

  it("maps nested API fields to form names", () => {
    expect(formFieldName("body.lines.0.account_number")).toBe("account_number");
    const issues = issuesForForm(
      [{ code: "missing", message: "Requis", field: "accounting_account" }],
      new Set(["accounting_account"]),
    );
    expect(issues).toHaveLength(1);
  });
});
