import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import OpeningPosting from "./OpeningPosting";
import type { Opening } from "./OpeningPreview";

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const preview: Opening = {
  preview_token: "a".repeat(64), source_end_date: "2025-12-31", opening_date: "2026-01-01",
  excluded_draft_count: 0, warnings: [], lines: [], total_debit: "10.01", total_credit: "10.01",
  result_line: { account_number: null, label: "Résultat", debit: "0.00", credit: "10.01" },
};
afterEach(() => vi.restoreAllMocks());

function fill() {
  fireEvent.change(screen.getByLabelText("Référence de la pièce de reprise"), { target: { value: "AN-2026" } });
  fireEvent.change(screen.getByLabelText(/Compte de reprise du résultat/), { target: { value: "120000" } });
}

test("posts explicit account and preview token once, shows persisted receipt", async () => {
  let finish!: (value: Response) => void;
  const pending = new Promise<Response>((resolve) => { finish = resolve; });
  const fetch = vi.spyOn(globalThis, "fetch").mockReturnValue(pending);
  render(<OpeningPosting year={2} preview={preview} />);
  fill();
  const button = screen.getByRole("button", { name: "Générer et valider les à-nouveaux" });
  fireEvent.click(button); fireEvent.click(button);
  expect(fetch).toHaveBeenCalledTimes(1);
  const [url, init] = fetch.mock.calls[0]!;
  expect(url).toBe("/api/ledger/years/2/opening");
  expect(init?.method).toBe("POST");
  expect(JSON.parse(String(init?.body))).toEqual({ preview_token: preview.preview_token, journal_code: "AN", piece_reference: "AN-2026", result_account: "120000" });
  await act(async () => { finish(response({ created: true, entry: { entry_number: "2026-000001" } })); await pending; });
  expect(await screen.findByRole("status")).toHaveTextContent("2026-000001 créée et validée");
  expect(screen.queryByRole("button", { name: "Générer et valider les à-nouveaux" })).not.toBeInTheDocument();
});

test.each(["SOURCE_NOT_CLOSED", "SOURCE_DRAFTS", "TARGET_NOT_OPEN", "TARGET_HAS_ENTRIES", "INACTIVE_ACCOUNTS"])("blocks generation for %s", (code) => {
  render(<OpeningPosting year={2} preview={{ ...preview, warnings: [{ code, message: "Blocage" }] }} />);
  expect(screen.getByRole("button", { name: "Générer et valider les à-nouveaux" })).toBeDisabled();
});

test("failed generation shows error and permits an idempotent retry", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(response({ detail: { message: "Base occupée" } }, 503))
    .mockResolvedValueOnce(response({ created: false, entry: { entry_number: "2026-000001" } }));
  render(<OpeningPosting year={2} preview={preview} />);
  fill();
  fireEvent.click(screen.getByRole("button", { name: "Générer et valider les à-nouveaux" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Base occupée");
  fireEvent.click(screen.getByRole("button", { name: "Générer et valider les à-nouveaux" }));
  expect(await screen.findByText(/2026-000001 déjà enregistrée/)).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(2);
});

test("shows account differences and removes stale control on failure", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(response({
    opening_entry_id: 3, balances_match: false, source_closed: false, source_unchanged: false,
    differences: [{ account_number: "512000", expected_balance: "10.02", opening_balance: "10.01", difference: "-0.01" }],
  }));
  render(<OpeningPosting year={2} preview={null} />);
  fireEvent.click(screen.getByRole("button"));
  expect(await screen.findByRole("table")).toHaveTextContent("-0.01");
  expect(screen.getByRole("alert")).toHaveTextContent("La source a changé");
  fetch.mockResolvedValue(response({ detail: { message: "Source indisponible" } }, 409));
  fireEvent.click(screen.getByRole("button"));
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(await screen.findByRole("alert")).toHaveTextContent("Source indisponible");
});

test.each([false, true])("ignores late posting response after changing year (failure=%s)", async (failed) => {
  let finish!: (value: Response) => void;
  const pending = new Promise<Response>((resolve) => { finish = resolve; });
  vi.spyOn(globalThis, "fetch").mockReturnValue(pending);
  const { rerender } = render(<OpeningPosting key="2" year={2} preview={preview} />);
  fill(); fireEvent.click(screen.getByRole("button", { name: "Générer et valider les à-nouveaux" }));
  rerender(<OpeningPosting key="3" year={3} preview={null} />);
  await act(async () => {
    finish(failed ? response({ detail: { message: "Ancienne erreur" } }, 409) : response({ created: true, entry: { entry_number: "2026-000001" } }));
    await pending;
  });
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
