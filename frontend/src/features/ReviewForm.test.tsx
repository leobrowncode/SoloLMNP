import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RequestError } from "../api/ledger";
import ReviewForm from "./ReviewForm";

describe("ReviewForm", () => {
  it("keeps exact money strings and requires a review step", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    render(<ReviewForm title="Dépense fictive" fields={[
      { name: "amount", label: "Montant", money: true },
      { name: "kind", label: "Type", choices: [["EXPENSE", "Dépense"]] },
    ]} onSave={save} onCancel={() => undefined} retryId />);
    const input = screen.getByLabelText("Montant");
    await userEvent.clear(input);
    await userEvent.type(input, "90071992547409,91");
    await userEvent.click(screen.getByRole("button", { name: "Vérifier avant enregistrement" }));
    expect(save).not.toHaveBeenCalled();
    expect(screen.getByText("90 071 992 547 409,91 €")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Confirmer l’enregistrement" }));
    expect(save).toHaveBeenCalledOnce();
    expect(save.mock.calls[0]?.[0]).toEqual(expect.objectContaining({
      amount: "90071992547409.91",
      kind: "EXPENSE",
      request_id: expect.any(String),
    }));
  });

  it("lets the user return to the input before saving", async () => {
    const save = vi.fn();
    render(<ReviewForm title="Test" fields={[
      { name: "label", label: "Libellé" },
    ]} onSave={save} onCancel={() => undefined} />);
    await userEvent.type(screen.getByLabelText("Libellé"), "Premier");
    await userEvent.click(screen.getByRole("button", { name: "Vérifier avant enregistrement" }));
    await userEvent.click(screen.getByRole("button", { name: "Corriger la saisie" }));
    expect(screen.getByLabelText("Libellé")).toHaveValue("Premier");
    expect(save).not.toHaveBeenCalled();
  });

  it("computes the loan payment total from ventilation lines", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    render(<ReviewForm
      title="Échéance"
      help="Le total est calculé automatiquement."
      sumInto={{ target: "amount", sources: ["principal", "interest", "insurance", "other_costs"] }}
      fields={[
        { name: "principal", label: "Capital remboursé (€)", money: true, group: "Ventilation" },
        { name: "interest", label: "Intérêts (€)", money: true, group: "Ventilation" },
        { name: "insurance", label: "Assurance (€)", money: true, group: "Ventilation" },
        { name: "other_costs", label: "Autres frais (€)", money: true, group: "Ventilation" },
      ]}
      onSave={save}
      onCancel={() => undefined}
      retryId
    />);
    await userEvent.clear(screen.getByLabelText(/Capital remboursé/));
    await userEvent.type(screen.getByLabelText(/Capital remboursé/), "100.00");
    await userEvent.clear(screen.getByLabelText(/Intérêts/));
    await userEvent.type(screen.getByLabelText(/Intérêts/), "25.50");
    expect(screen.getByText(/Total de l’échéance/)).toHaveTextContent("125,50 €");
    await userEvent.click(screen.getByRole("button", { name: "Vérifier avant enregistrement" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmer l’enregistrement" }));
    expect(save).toHaveBeenCalledOnce();
    expect(save.mock.calls[0]?.[0]).toEqual(expect.objectContaining({
      principal: "100.00",
      interest: "25.50",
      insurance: "0.00",
      other_costs: "0.00",
      amount: "125.50",
    }));
  });

  it("derives piece_reference and account from operation type, without overwriting manual edits", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    render(<ReviewForm
      title="Recette"
      fields={[
        {
          name: "operation_type", label: "Type d’opération", local: true,
          choices: [["LOY", "Loyer"], ["TROP", "Trop-perçu"]],
          value: "LOY",
        },
        { name: "date", label: "Date comptable", type: "date", value: "2026-03-01" },
        { name: "piece_reference", label: "Référence justificative", value: "LOY-2026-03-SANSNOM" },
        { name: "counterparty", label: "Locataire / client" },
        {
          name: "accounting_account", label: "Compte", value: "706000",
          choices: [["706000", "706000 · Prestations"], ["706100", "706100 · Autre"]],
        },
      ]}
      derive={(draft) => ({
        accounting_account: draft.operation_type === "TROP" ? "706100" : "706000",
        piece_reference: `${draft.operation_type}-${(draft.date ?? "").slice(0, 7)}-${draft.counterparty || "SANSNOM"}`,
      })}
      onSave={save}
      onCancel={() => undefined}
    />);

    await userEvent.type(screen.getByLabelText("Locataire / client"), "Dupont");
    expect(screen.getByLabelText("Référence justificative")).toHaveValue("LOY-2026-03-Dupont");

    await userEvent.selectOptions(screen.getByLabelText("Type d’opération"), "TROP");
    expect(screen.getByLabelText("Référence justificative")).toHaveValue("TROP-2026-03-Dupont");
    expect(screen.getByLabelText("Compte")).toHaveValue("706100");

    const reference = screen.getByLabelText("Référence justificative");
    await userEvent.clear(reference);
    await userEvent.type(reference, "MANUEL-001");
    await userEvent.clear(screen.getByLabelText("Locataire / client"));
    await userEvent.type(screen.getByLabelText("Locataire / client"), "Martin");
    expect(screen.getByLabelText("Référence justificative")).toHaveValue("MANUEL-001");

    await userEvent.click(screen.getByRole("button", { name: "Vérifier avant enregistrement" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmer l’enregistrement" }));
    expect(save.mock.calls[0]?.[0]).toEqual(expect.objectContaining({
      date: "2026-03-01",
      piece_reference: "MANUEL-001",
      counterparty: "Martin",
      accounting_account: "706100",
    }));
    expect(save.mock.calls[0]?.[0]).not.toHaveProperty("operation_type");
  });

  it("refreshes dependent choices when another field changes", async () => {
    render(<ReviewForm
      title="Comptes"
      fields={[
        {
          name: "category", label: "Catégorie",
          choices: [["BUILDING", "Construction"], ["FURNITURE", "Mobilier"]],
        },
        {
          name: "asset_account", label: "Compte", value: "213000",
          choicesFor: (draft) => draft.category === "FURNITURE"
            ? [["218400", "218400 · Mobilier"]]
            : [["213000", "213000 · Constructions"], ["211000", "211000 · Terrains"]],
        },
      ]}
      derive={(draft, changed) => (
        changed === "category" && draft.category === "FURNITURE" ? { asset_account: "218400" } : {}
      )}
      onSave={vi.fn()}
      onCancel={() => undefined}
    />);
    expect(screen.getByLabelText("Compte")).toHaveValue("213000");
    expect(screen.getByRole("option", { name: "211000 · Terrains" })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Catégorie"), "FURNITURE");
    expect(screen.getByLabelText("Compte")).toHaveValue("218400");
    expect(screen.queryByRole("option", { name: "211000 · Terrains" })).not.toBeInTheDocument();
  });

  it("shows a field validation message under the control", async () => {
    const save = vi.fn().mockRejectedValue(new RequestError({
      code: "VALIDATION_ERROR",
      message: "Les données envoyées sont invalides.",
      issues: [{ code: "missing", message: "Le libellé est requis.", field: "label" }],
    }, 422));
    render(<ReviewForm title="Test" fields={[
      { name: "label", label: "Libellé" },
    ]} onSave={save} onCancel={() => undefined} />);
    await userEvent.type(screen.getByLabelText("Libellé"), "Test");
    await userEvent.click(screen.getByRole("button", { name: "Vérifier avant enregistrement" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmer l’enregistrement" }));
    expect(await screen.findByText("Le libellé est requis.")).toBeInTheDocument();
    expect(screen.getByLabelText("Libellé")).toHaveAttribute("aria-describedby", expect.stringContaining("-error"));
  });

  it("leaves an optional amount empty and shows JJ/MM/AAAA on an empty date", async () => {
    render(<ReviewForm title="Bien" fields={[
      { name: "acquisition_date", label: "Date d’acquisition", type: "date" },
      { name: "price_m2", label: "Prix constaté au m² (€)", money: true, optional: true, local: true },
      { name: "acquisition_price", label: "Prix d’acquisition (€)", money: true },
    ]} onSave={vi.fn()} onCancel={() => undefined} />);
    expect(screen.getByText("JJ/MM/AAAA")).toBeInTheDocument();
    expect(screen.getByLabelText("Date d’acquisition")).toHaveAttribute("lang", "fr");
    expect(screen.getByLabelText("Date d’acquisition")).toHaveAttribute("type", "date");
    expect(screen.getByText("Format JJ/MM/AAAA.")).toBeInTheDocument();
    expect(screen.getByLabelText(/Prix constaté au m²/)).toHaveValue("");
    expect(screen.getByLabelText(/Prix constaté au m²/)).not.toBeRequired();
    expect(screen.getByLabelText("Prix d’acquisition (€)")).toHaveValue("0.00");
    fireEvent.change(screen.getByLabelText("Date d’acquisition"), { target: { value: "2025-01-09" } });
    expect(screen.queryByText("JJ/MM/AAAA")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Date d’acquisition")).toHaveValue("2025-01-09");
  });

  it("blocks review when land and building do not equal the price", async () => {
    const save = vi.fn();
    render(<ReviewForm
      title="Bien"
      validate={(draft) => (
        draft.land_value === draft.acquisition_price ? "" : "Le terrain et le bâtiment ne totalisent pas le prix."
      )}
      fields={[
        { name: "acquisition_price", label: "Prix", money: true, value: "100.00" },
        { name: "land_value", label: "Terrain", money: true, value: "40.00" },
      ]}
      onSave={save}
      onCancel={() => undefined}
    />);
    expect(screen.getByRole("alert")).toHaveTextContent("ne totalisent pas le prix");
    await userEvent.click(screen.getByRole("button", { name: "Vérifier avant enregistrement" }));
    expect(screen.queryByText(/Vérifiez les informations/)).not.toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Terrain"), { target: { value: "100.00" } });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Vérifier avant enregistrement" }));
    expect(screen.getByText(/Vérifiez les informations/)).toBeInTheDocument();
  });
});
