import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import InventoryForm from "./InventoryForm";

const year = { id: 1, year: 2025, start_date: "2025-01-01", end_date: "2025-12-31", status: "OPEN" };
const accounts = [
  { number: "512000", label: "Banque", active: true, account_type: "ASSET" },
  { number: "706000", label: "Produit", active: true, account_type: "INCOME" },
  { number: "401000", label: "Inactif", active: false, account_type: "LIABILITY" },
];
const journals = [
  { code: "OD", label: "Divers", active: true, journal_type: "GENERAL" },
  { code: "BQ", label: "Banque", active: true, journal_type: "BANK" },
  { code: "XX", label: "Inactif", active: false, journal_type: "GENERAL" },
];
const props = { year, accounts, journals, onPosted: vi.fn() };
const response = () => new Response(JSON.stringify({ id: 10, entry_number: "2025-000010", label: "Inventaire test" }), { status: 200 });
async function fill(credit = "123.45") {
  fireEvent.change(screen.getByLabelText("Référence de la pièce"), { target: { value: "INV-1" } });
  fireEvent.change(screen.getByLabelText("Libellé de l’écriture"), { target: { value: "Inventaire test" } });
  fireEvent.change(screen.getByLabelText("Justification et calcul"), { target: { value: "Calcul justifié dans la pièce INV-1." } });
  fireEvent.change(screen.getAllByLabelText("Compte")[0]!, { target: { value: "512000" } });
  fireEvent.change(screen.getAllByLabelText("Compte")[1]!, { target: { value: "706000" } });
  screen.getAllByLabelText("Libellé").forEach((input) => fireEvent.change(input, { target: { value: "Test" } }));
  fireEvent.change(screen.getAllByLabelText("Débit (€)")[0]!, { target: { value: "123,45" } });
  fireEvent.change(screen.getAllByLabelText("Crédit (€)")[1]!, { target: { value: credit } });
  await userEvent.click(screen.getByRole("button", { name: "Vérifier l’inventaire" }));
}
beforeEach(() => { sessionStorage.clear(); vi.clearAllMocks(); });
describe("manual inventory", () => {
  it("reviews exact amounts before posting and shows the validated receipt", async () => {
    const fetcher = vi.fn().mockResolvedValue(response()); vi.stubGlobal("fetch", fetcher);
    render(<InventoryForm {...props} />);
    expect(screen.queryByRole("option", { name: "BQ · Banque" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "401000 · Inactif" })).not.toBeInTheDocument();
    await fill();
    expect(fetcher).not.toHaveBeenCalled();
    expect(screen.getByRole("table")).toHaveTextContent("123.45");
    await userEvent.click(screen.getByRole("button", { name: "Confirmer la comptabilisation" }));
    expect(await screen.findByRole("status")).toHaveTextContent("2025-000010");
    const [url, init] = fetcher.mock.calls[0]!;
    expect(url).toBe("/api/ledger/inventory");
    expect(JSON.parse(init.body)).toMatchObject({ fiscal_year_id: 1, journal_code: "OD", justification: "Calcul justifié dans la pièce INV-1.", lines: [{ debit: "123.45" }, { credit: "123.45" }] });
    expect(sessionStorage.length).toBe(0); expect(props.onPosted).toHaveBeenCalledOnce();
  });
  it("refuses imbalance and double-sided lines without sending anything", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher); render(<InventoryForm {...props} />);
    await fill("123.44"); expect(screen.getByRole("alert")).toHaveTextContent("équilibrés au centime");
    fireEvent.change(screen.getAllByLabelText("Crédit (€)")[0]!, { target: { value: "1" } });
    await userEvent.click(screen.getByRole("button", { name: "Vérifier l’inventaire" }));
    expect(screen.getByRole("alert")).toHaveTextContent("exactement un côté positif"); expect(fetcher).not.toHaveBeenCalled();
  });
  it("recovers a lost response after remount and retries the identical request even on a closed year", async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new Error("Réponse perdue")).mockResolvedValueOnce(response()); vi.stubGlobal("fetch", fetcher);
    const view = render(<InventoryForm {...props} />); await fill();
    await userEvent.click(screen.getByRole("button", { name: "Confirmer la comptabilisation" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Réponse perdue");
    expect(screen.queryByRole("button", { name: "Corriger la saisie" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Abandonner après vérification" })).toBeDisabled();
    view.unmount(); render(<InventoryForm {...props} year={{ ...year, status: "CLOSED" }} />);
    expect(fetcher).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Réessayer la même demande" }));
    expect(await screen.findByRole("status")).toHaveTextContent("2025-000010");
    expect(fetcher.mock.calls[0]![1].body).toBe(fetcher.mock.calls[1]![1].body);
  });
  it("blocks a second submission while the first is pending", async () => {
    let resolve!: (value: Response) => void;
    const fetcher = vi.fn(() => new Promise<Response>((done) => { resolve = done; })); vi.stubGlobal("fetch", fetcher);
    render(<InventoryForm {...props} />); await fill();
    const button = screen.getByRole("button", { name: "Confirmer la comptabilisation" });
    fireEvent.submit(button.closest("form")!); fireEvent.submit(button.closest("form")!);
    expect(fetcher).toHaveBeenCalledOnce();
    await act(async () => { resolve(response()); });
  });
  it("does not post when pending-request storage cannot be written", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher); render(<InventoryForm {...props} />); await fill();
    const storage = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Stockage indisponible"); });
    await userEvent.click(screen.getByRole("button", { name: "Confirmer la comptabilisation" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Stockage indisponible"));
    expect(fetcher).not.toHaveBeenCalled(); storage.mockRestore();
  });
  it("requires an open year and an active general journal for a new entry", () => {
    render(<InventoryForm {...props} year={{ ...year, status: "CLOSED" }} journals={[]} />);
    expect(screen.getByRole("button", { name: "Vérifier l’inventaire" })).toBeDisabled();
    expect(screen.getByText("Aucun journal actif d’opérations diverses disponible.")).toBeInTheDocument();
  });
  it.each(["{", "{}", JSON.stringify({ fiscal_year_id: 2 })])("fails closed for corrupt saved data: %s", (saved) => {
    sessionStorage.setItem("sololmnp.inventory.pending.1", saved);
    render(<InventoryForm {...props} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Impossible de lire la demande conservée");
    expect(screen.getByRole("button", { name: "Vérifier l’inventaire" })).toBeDisabled();
    expect(sessionStorage.getItem("sololmnp.inventory.pending.1")).toBe(saved);
  });
  it("isolates saved requests by exercise", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Réponse perdue")));
    const view = render(<InventoryForm {...props} />); await fill();
    await userEvent.click(screen.getByRole("button", { name: "Confirmer la comptabilisation" }));
    await screen.findByRole("alert"); view.unmount();
    render(<InventoryForm {...props} year={{ ...year, id: 2, year: 2026 }} />);
    expect(screen.getByRole("button", { name: "Vérifier l’inventaire" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Réessayer la même demande" })).not.toBeInTheDocument();
    expect(sessionStorage.getItem("sololmnp.inventory.pending.1")).not.toBeNull();
  });
});
