import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
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
    expect(screen.getByText("90071992547409.91")).toBeInTheDocument();
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
    expect(screen.getByText(/Total de l’échéance/)).toHaveTextContent("125.50");
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
});
