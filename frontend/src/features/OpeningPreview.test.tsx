import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import OpeningPreview, { type Opening } from "./OpeningPreview";
import StatementsPage from "./StatementsPage";

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const preview: Opening = {
  source_end_date: "2025-12-31", opening_date: "2026-01-01", excluded_draft_count: 1,
  lines: [{ account_number: "401000", label: "Fournisseurs", debit: "0.00", credit: "10.01" }],
  result_line: { account_number: null, label: "Résultat précédent", debit: "10.01", credit: "0.00" },
  total_debit: "10.01", total_credit: "10.01",
  warnings: [{ code: "SOURCE_NOT_CLOSED", message: "L’exercice précédent n’est pas clôturé." }],
};
afterEach(() => vi.restoreAllMocks());

test("loads on demand, shows loss and warnings, clears totals on failure", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(preview));
  render(<OpeningPreview year={2} />);
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button"));
  expect(await screen.findByRole("table")).toHaveTextContent("À déterminer");
  expect(screen.getByText("L’exercice précédent n’est pas clôturé.")).toBeInTheDocument();
  expect(fetch.mock.calls[0]?.[0]).toBe("/api/ledger/years/2/opening-preview");
  fetch.mockResolvedValue(response({ detail: { message: "Exercice précédent absent" } }, 409));
  fireEvent.click(screen.getByRole("button"));
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(await screen.findByRole("alert")).toHaveTextContent("Exercice précédent absent");
});

test.each([false, true])("year change discards late preview (error=%s)", async (failed) => {
  let finish!: (value: Response) => void;
  const pending = new Promise<Response>((resolve) => { finish = resolve; });
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    if (String(input).endsWith("/setup")) return response({ activity: {}, years: [{ id: 2, year: 2026 }, { id: 3, year: 2027 }] });
    if (String(input).endsWith("/opening-preview")) return pending;
    return response({ detail: { message: "États indisponibles pour ce test" } }, 409);
  });
  render(<StatementsPage />);
  const select = await screen.findByLabelText("Exercice");
  fireEvent.click(screen.getByRole("button", { name: "Prévisualiser les à-nouveaux" }));
  fireEvent.change(select, { target: { value: "3" } });
  await act(async () => {
    finish(failed ? response({ detail: { message: "Ancienne erreur" } }, 409) : response(preview));
    await pending;
  });
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByText("Ancienne erreur")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Prévisualiser les à-nouveaux" })).toBeEnabled();
});

test("refreshing statements also clears the opening preview", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    if (String(input).endsWith("/setup")) return response({ activity: {}, years: [{ id: 2, year: 2026 }] });
    if (String(input).endsWith("/opening-preview")) return response(preview);
    return response({ detail: { message: "États indisponibles pour ce test" } }, 409);
  });
  render(<StatementsPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Prévisualiser les à-nouveaux" }));
  expect(await screen.findByRole("table")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Actualiser les états" }));
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});
