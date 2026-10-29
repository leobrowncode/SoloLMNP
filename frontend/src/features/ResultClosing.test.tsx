import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import ResultClosing from "./ResultClosing";

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});
const benefit = {
  number: "120000", label: "Résultat de l’exercice (bénéfice)", account_type: "EQUITY",
};
const deficit = {
  number: "129000", label: "Résultat de l’exercice (déficit)", account_type: "EQUITY",
};
const journals = [{ code: "OD", label: "Opérations diverses", journal_type: "GENERAL", active: true }];
const exploitant = { number: "108000", label: "Exploitant", account_type: "EQUITY", active: true };

function preview(partial: Record<string, unknown> = {}) {
  return {
    result: "50.00", result_account_prefix: "120", excluded_draft_count: 0,
    lines: [
      { account_number: "706000", label: "Centralisation", debit: "50.00", credit: "0.00" },
      { account_number: "", label: "Résultat — compte à confirmer", debit: "0.00", credit: "50.00" },
    ],
    already_posted: false, year_status: "OPEN", proposed_accounts: [benefit],
    ...partial,
  };
}

beforeEach(() => sessionStorage.clear());
afterEach(() => { sessionStorage.clear(); vi.restoreAllMocks(); });

function install(
  accounts: unknown[],
  central: ReturnType<typeof preview> = preview(),
  post?: () => Promise<Response>,
) {
  const calls: { method: string; url: string; body?: unknown }[] = [];
  let confirmed = false;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) as unknown : undefined;
    calls.push({ method, url, body });
    if (url.endsWith("/centralization-preview")) {
      return response(confirmed ? { ...central, already_posted: true, proposed_accounts: [] } : central);
    }
    if (url.endsWith("/appropriation-preview")) {
      return response({ centralization_posted: true, proposals: [], already_posted: false });
    }
    if (url.endsWith("/accounts")) return response(accounts);
    if (url.endsWith("/journals")) return response(journals);
    if (url.endsWith("/centralization") && method === "POST" && post) {
      confirmed = true;
      return post();
    }
    throw new Error(`Unexpected ${method} ${url}`);
  });
  return calls;
}

function fill() {
  fireEvent.change(screen.getByLabelText("Référence de pièce"), { target: { value: "CENT-1" } });
  fireEvent.change(screen.getByLabelText("Justification"), {
    target: { value: "Centralisation confirmée après contrôle." },
  });
}

test("preview lists a missing account and leaves the chart unchanged until confirmation", async () => {
  let finish!: (value: Response) => void;
  const pending = new Promise<Response>((resolve) => { finish = resolve; });
  const calls = install([exploitant], preview(), () => pending);
  render(<ResultClosing year={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Préparer la centralisation" }));
  expect(await screen.findByText(`${benefit.number} · ${benefit.label}`)).toBeInTheDocument();
  expect(screen.getByRole("option", { name: /sera créé/ })).toBeInTheDocument();
  expect(calls.every((call) => call.method === "GET")).toBe(true);
  fill();
  fireEvent.click(screen.getByRole("button", { name: "Vérifier la centralisation" }));
  expect(await screen.findByText(/La confirmation crée 120000/)).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "120000" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Corriger" }));
  expect(calls.every((call) => call.method === "GET")).toBe(true);
  fill();
  fireEvent.click(screen.getByRole("button", { name: "Vérifier la centralisation" }));
  const confirm = screen.getByRole("button", { name: "Confirmer la centralisation" });
  fireEvent.click(confirm);
  fireEvent.click(confirm);
  const posts = () => calls.filter((call) => call.method === "POST");
  expect(posts()).toHaveLength(1);
  expect(posts()[0]).toMatchObject({
    url: "/api/ledger/years/1/centralization",
    body: {
      journal_code: "OD", piece_reference: "CENT-1", result_account: "120000",
      expected_result: "50.00", create_accounts: [benefit],
    },
  });
  expect(calls.some((call) => call.method === "POST" && call.url.endsWith("/accounts"))).toBe(false);
  finish(response({ created: true, entry: { entry_number: "2025-000009" } }));
  expect(await screen.findByRole("status")).toHaveTextContent("2025-000009 validée");
  expect(await screen.findByText(/déjà comptabilisée/)).toBeInTheDocument();
  expect(screen.queryByText(/création proposée/)).not.toBeInTheDocument();
  expect(screen.queryByText(/sera créé/)).not.toBeInTheDocument();
  expect(posts()).toHaveLength(1);
});

test("confirmation does not create an account that is already in the chart", async () => {
  const calls = install(
    [{ ...benefit, active: true }, exploitant],
    preview({ proposed_accounts: [] }),
    async () => response({ created: true, entry: { entry_number: "2025-000010" } }),
  );
  render(<ResultClosing year={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Préparer la centralisation" }));
  expect(await screen.findByRole("option", { name: "120000 · Résultat de l’exercice (bénéfice)" })).toBeInTheDocument();
  expect(screen.queryByText(/création proposée/)).not.toBeInTheDocument();
  expect(calls.every((call) => call.method === "GET")).toBe(true);
  fill();
  fireEvent.click(screen.getByRole("button", { name: "Vérifier la centralisation" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirmer la centralisation" }));
  expect(await screen.findByRole("status")).toHaveTextContent("2025-000010 validée");
  const post = calls.find((call) => call.method === "POST");
  expect(post?.body).toMatchObject({ result_account: "120000", create_accounts: [] });
  expect(calls.filter((call) => call.method === "POST")).toHaveLength(1);
});

test("a loss preview proposes only 129000 and still does not post", async () => {
  const calls = install([exploitant], preview({
    result: "-10.01", result_account_prefix: "129", proposed_accounts: [deficit],
    lines: [
      { account_number: "615000", label: "Centralisation", debit: "0.00", credit: "10.01" },
      { account_number: "", label: "Résultat — compte à confirmer", debit: "10.01", credit: "0.00" },
    ],
  }));
  render(<ResultClosing year={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Préparer la centralisation" }));
  expect(await screen.findByText(`${deficit.number} · ${deficit.label}`)).toBeInTheDocument();
  expect(screen.queryByText(/120000/)).not.toBeInTheDocument();
  expect(calls.every((call) => call.method === "GET")).toBe(true);
});

test("an unusable result account blocks confirmation without writing", async () => {
  const calls = install(
    [{ ...benefit, active: false }],
    preview({ proposed_accounts: [] }),
  );
  render(<ResultClosing year={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Préparer la centralisation" }));
  expect(await screen.findByText(/Aucun compte actif 120/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Vérifier la centralisation" })).toBeDisabled();
  expect(calls.every((call) => call.method === "GET")).toBe(true);
});

test("a zero result confirms without a result account", async () => {
  const calls = install([exploitant], preview({
    result: "0.00", result_account_prefix: null, proposed_accounts: [],
    lines: [
      { account_number: "706000", label: "Centralisation", debit: "40.00", credit: "0.00" },
      { account_number: "615000", label: "Centralisation", debit: "0.00", credit: "40.00" },
    ],
  }), async () => response({ created: true, entry: { entry_number: "2025-000011" } }));
  render(<ResultClosing year={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Préparer la centralisation" }));
  expect(await screen.findByText(/Résultat à centraliser : 0.00/)).toBeInTheDocument();
  expect(screen.queryByLabelText("Compte de résultat")).not.toBeInTheDocument();
  expect(calls.every((call) => call.method === "GET")).toBe(true);
  fill();
  fireEvent.click(screen.getByRole("button", { name: "Vérifier la centralisation" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirmer la centralisation" }));
  expect(await screen.findByRole("status")).toHaveTextContent("2025-000011 validée");
  expect(calls.find((call) => call.method === "POST")?.body).toMatchObject({
    result_account: null, create_accounts: [], expected_result: "0.00",
  });
});
