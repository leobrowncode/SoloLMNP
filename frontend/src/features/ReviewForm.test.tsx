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
});
