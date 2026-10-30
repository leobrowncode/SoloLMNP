import { describe, expect, it } from "vitest";
import { errorSummary, helpForError, parseApiErrorDetail, formFieldName, issuesForForm, importIssueLines } from "./errors";

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

  it("shows a model-level validation message instead of the generic refusal", () => {
    const detail = parseApiErrorDetail({
      code: "VALIDATION_ERROR",
      message: "Les données envoyées sont invalides.",
      issues: [{
        code: "value_error",
        message: "La date de fin doit être postérieure ou égale à la date de début.",
        location: "body",
      }],
    });
    expect(errorSummary(detail)).toBe(
      "La date de fin doit être postérieure ou égale à la date de début.",
    );
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

  it("keeps a known help id and drops an unknown one", () => {
    const kept = parseApiErrorDetail({
      code: "EXPORT_BLOCKED",
      message: "Téléchargement refusé.",
      help: "liasse",
      issues: [{ code: "FEC_INVALID", message: "En-tête FEC absent.", help: "pas-une-entree" }],
    });
    expect(kept.help).toBe("liasse");
    expect(kept.issues?.[0]?.help).toBeUndefined();
  });

  it("points a code at the glossary when help is omitted, and lets an explicit id win", () => {
    expect(helpForError(parseApiErrorDetail({
      code: "FEC_INVALID",
      message: "Le FEC contient des erreurs.",
    }))).toBe("fec");
    expect(helpForError(parseApiErrorDetail({
      code: "FEC_INVALID",
      message: "Le FEC contient des erreurs.",
      help: "extourne",
    }))).toBe("extourne");
    expect(helpForError(parseApiErrorDetail({
      code: "ACTIVITY_REQUIRED",
      message: "Créez l’activité.",
      help: "inconnu",
    }))).toBeNull();
  });
});
