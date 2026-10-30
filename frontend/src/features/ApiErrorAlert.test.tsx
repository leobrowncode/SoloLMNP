import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, test } from "vitest";
import ApiErrorAlert from "./ApiErrorAlert";
import { GLOSSARY } from "./glossary";

function renderAlert(detail: Parameters<typeof ApiErrorAlert>[0]["detail"]) {
  return render(
    <MemoryRouter>
      <ApiErrorAlert detail={detail} />
    </MemoryRouter>,
  );
}

describe("error to help links", () => {
  test("opens the glossary entry mapped from the error code", async () => {
    const user = userEvent.setup();
    renderAlert({ code: "FEC_INVALID", message: "Le FEC contient des erreurs et n’est pas exportable." });
    expect(screen.getByRole("alert")).toHaveTextContent("Le FEC contient des erreurs");
    await user.click(screen.getByRole("button", { name: "Aide : FEC" }));
    expect(screen.getByRole("tooltip")).toHaveTextContent(GLOSSARY.fec.what);
  });

  test("uses an explicit help id instead of the code map", async () => {
    const user = userEvent.setup();
    renderAlert({
      code: "FEC_INVALID",
      message: "Passez par l’opération.",
      help: "extourne",
    });
    await user.click(screen.getByRole("button", { name: "Aide : Extourne" }));
    expect(screen.getByRole("tooltip")).toHaveTextContent(GLOSSARY.extourne.what);
    expect(screen.queryByRole("button", { name: "Aide : FEC" })).not.toBeInTheDocument();
  });

  test("stays quiet when the code has no glossary entry", () => {
    renderAlert({ code: "ACTIVITY_REQUIRED", message: "Créez l’activité." });
    expect(screen.queryByRole("button", { name: /^Aide :/ })).not.toBeInTheDocument();
  });

  test("names the row, column, value and expected correction of an import rejection", () => {
    renderAlert({
      code: "CSV_INVALID",
      message: "Un rejet est à corriger.",
      help: "import-csv",
      location: "import",
      issues: [{
        code: "CSV_AMOUNT",
        message: "Montant illisible.",
        line: 4,
        column: "Montant",
        value: "abc",
        correction: "Écrivez un montant au centime, par exemple 800,00.",
        help: "import-csv",
        location: "import",
      }],
    });
    expect(screen.getByRole("listitem")).toHaveTextContent(
      "Ligne 4, colonne Montant : Montant illisible. Valeur « abc ». Correction attendue : Écrivez un montant au centime, par exemple 800,00.",
    );
    expect(screen.getAllByRole("button", { name: "Aide : Import CSV" }).length).toBeGreaterThan(0);
  });

  test("shows a different help id on an issue line", async () => {
    const user = userEvent.setup();
    renderAlert({
      code: "EXPORT_BLOCKED",
      message: "Sortie bloquée.",
      help: "liasse",
      issues: [
        { code: "SIREN_MANQUANT", message: "SIREN absent.", help: "siren" },
        { code: "YEAR_NOT_CLOSED", message: "Exercice ouvert.", help: "cloture" },
      ],
    });
    expect(screen.getByRole("button", { name: "Aide : Liasse" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Aide : SIREN" }));
    expect(screen.getByRole("tooltip")).toHaveTextContent(GLOSSARY.siren.what);
  });
});
