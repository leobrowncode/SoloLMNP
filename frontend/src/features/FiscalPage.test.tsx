import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import FiscalPage from "./FiscalPage";

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});

test("states that the EFI worksheet is not transmitted", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/vintages")) {
      return response({ vintages: [{ vintage: "2025", status: "research_only", blocked: ["RULE-LMNP-BIC-001"], executable: [] }] });
    }
    if (url.endsWith("/setup")) return response({ years: [{ id: 1, year: 2025 }] });
    return response({
      transmission: false,
      disclaimer: "Feuille de recopie uniquement. Aucun envoi n’est effectué.",
      personal_return: { form: "2042-C-PRO", official_case: null, status: "case_not_verified", amount: "0.00" },
    });
  });
  render(<FiscalPage />);
  expect(await screen.findByText(/Millésime 2025/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Afficher la feuille EFI" }));
  expect(await screen.findByText(/Aucun envoi n’est effectué/)).toBeInTheDocument();
  expect(screen.getByText(/Télétransmission : non/)).toBeInTheDocument();
  expect(screen.getByText(/non vérifiée/)).toBeInTheDocument();
});
