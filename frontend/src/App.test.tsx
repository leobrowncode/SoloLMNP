import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { isApplicationStatus } from "./api/status";
import { ledgerPath, operationsPath, ROUTES } from "./routing/paths";
import { createTestRouter } from "./routing/router";
import { renderAt } from "./routing/renderTestApp";

const ready = {
  application_version: "0.2.0", phase: "foundation",
  database: { status: "ready", schema_revision: "0001_foundation", expected_revision: "0001_foundation" },
  fiscal: { status: "research_only", available_vintages: [] },
};
function reply(body: unknown = ready, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function renderApp(path = ROUTES.home) {
  return renderAt(path);
}

describe("Foundation status", () => {
  it("shows loading while the service is pending", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
    renderApp();
    expect(screen.getByRole("button", { name: /Vérification/ })).toBeDisabled();
    expect(screen.getByText(/Connexion au service et vérification/)).toBeInTheDocument();
  });

  it("shows centralization before the fiscal calculation, precheck and closing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply()));
    renderApp();
    await screen.findByText(/Base prête/);
    const nav = screen.getByRole("navigation", { name: "Navigation principale" });
    const links = within(nav).getAllByRole("link");
    const statements = links.find((link) => /États comptables/.test(link.textContent ?? ""))!;
    const fiscal = links.find((link) => /Fiscalité LMNP/.test(link.textContent ?? ""))!;
    const statementsStep = within(screen.getByRole("list")).getByRole("link", { name: /États comptables/ });
    const fiscalStep = within(screen.getByRole("list")).getByRole("link", { name: /Fiscalité LMNP/ });
    expect(statementsStep).toHaveTextContent("Bilan, résultat, puis centralisation.");
    expect(fiscalStep).toHaveTextContent("Calcul fiscal, pré-contrôle, clôture, puis sorties figées.");
    expect(links.indexOf(statements)).toBeLessThan(links.indexOf(fiscal));
  });

  it("displays live readiness without claiming tax readiness", async () => {
    const request = vi.fn().mockResolvedValue(reply());
    vi.stubGlobal("fetch", request);
    renderApp();
    expect(await screen.findByText(/Base prête/)).toBeInTheDocument();
    expect(screen.getByText(/Aucun envoi n’est effectué/)).toBeInTheDocument();
    expect(within(screen.getByRole("navigation", { name: "Navigation principale" })).getByRole("link", { name: /Comptabilité/ })).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/api/status", expect.objectContaining({ cache: "no-store" }));
  });

  it("shows an unmigrated database as not ready on HTTP 503", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({
      ...ready, database: { ...ready.database, status: "not_ready", schema_revision: null },
    }, 503)));
    renderApp();
    expect(await screen.findByText("Le stockage nécessite une vérification")).toBeInTheDocument();
    expect(screen.queryByText(/Base prête/)).not.toBeInTheDocument();
  });

  it("allows retry after a network failure", async () => {
    const request = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(reply());
    vi.stubGlobal("fetch", request);
    renderApp();
    expect(await screen.findByRole("alert")).toHaveTextContent("Connexion au service indisponible");
    await userEvent.click(screen.getByRole("button", { name: /Actualiser/ }));
    expect(await screen.findByText(/Base prête/)).toBeInTheDocument();
    expect(request.mock.calls.filter(([url]) => url === "/api/status")).toHaveLength(2);
  });

  it("rejects malformed API output", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({ status: "ok" })));
    renderApp();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(isApplicationStatus(null)).toBe(false);
  });

  it("keeps the OneDrive alert visible on a ready database and after navigation", async () => {
    const warning = "La base est dans un dossier synchronisé (OneDrive). Copiez le projet hors de ce dossier : la synchro peut corrompre SQLite.";
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      if (url === "/api/status") return Promise.resolve(reply({ ...ready, storage_warning: warning }));
      if (url.endsWith("/setup")) return Promise.resolve(reply({ activity: null, years: [] }));
      if (url.endsWith("/accounts") || url.endsWith("/journals")) return Promise.resolve(reply([]));
      return Promise.resolve(reply({}));
    }));
    renderApp();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Stockage non sûr");
    expect(alert).toHaveTextContent("peut corrompre SQLite");
    expect(alert).toHaveTextContent("Copiez le projet hors de ce dossier");
    expect(alert).not.toHaveTextContent("Base prête");
    expect(screen.getByText(/Base prête/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "Comptabilité" }));
    expect(screen.getByRole("link", { name: "Comptabilité" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("alert")).toHaveTextContent(warning);
    expect(await screen.findByRole("heading", { name: "Votre comptabilité" })).toBeInTheDocument();
  });

  it("does not show a storage alert when a ready database has no warning", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({ ...ready, storage_warning: null })));
    renderApp();
    expect(await screen.findByText(/Base prête/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(/OneDrive|Stockage non sûr/)).not.toBeInTheDocument();
  });

  it("shows the OneDrive alert when the database is not ready", async () => {
    const warning = "La base est dans un dossier synchronisé (OneDrive). Copiez le projet hors de ce dossier : la synchro peut corrompre SQLite.";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({
      ...ready,
      storage_warning: warning,
      database: { ...ready.database, status: "not_ready", schema_revision: null },
    }, 503)));
    renderApp();
    expect(await screen.findByRole("alert")).toHaveTextContent("Stockage non sûr");
    expect(screen.getByRole("alert")).toHaveTextContent(warning);
    expect(screen.getByText("Le stockage nécessite une vérification")).toBeInTheDocument();
    expect(screen.queryByText(/Base prête/)).not.toBeInTheDocument();
  });

  it("aborts the pending request on unmount", async () => {
    const request = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      expect(init.signal?.aborted).toBe(false);
      return new Promise<Response>(() => undefined);
    });
    vi.stubGlobal("fetch", request);
    const router = createTestRouter([ROUTES.home]);
    const view = render(<RouterProvider router={router} />);
    await waitFor(() => expect(request).toHaveBeenCalledOnce());
    const init = request.mock.calls[0]?.[1] as RequestInit;
    view.unmount();
    expect(init.signal?.aborted).toBe(true);
  });
});

describe("Application routing", () => {
  it("opens the ledger from a direct URL", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      if (url === "/api/status") return Promise.resolve(reply());
      if (url.endsWith("/setup")) {
        return Promise.resolve(reply({ activity: { activity_name: "Test" }, years: [{ id: 1, year: 2026, start_date: "2026-01-01", end_date: "2026-12-31", status: "OPEN" }] }));
      }
      if (url.endsWith("/accounts")) return Promise.resolve(reply([]));
      if (url.endsWith("/journals")) return Promise.resolve(reply([]));
      if (url.includes("/entries?")) return Promise.resolve(reply({ entries: [], count: 0 }));
      return Promise.resolve(reply({}));
    }));
    renderAt(ledgerPath("Balance"));
    expect(await screen.findByRole("heading", { name: "Votre comptabilité" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Balance" })).toHaveAttribute("aria-pressed", "true");
  });

  it("restores the previous screen with the browser history", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      if (url === "/api/status") return Promise.resolve(reply());
      if (url.endsWith("/setup")) {
        return Promise.resolve(reply({ activity: { activity_name: "Test" }, years: [{ id: 1, year: 2026, start_date: "2026-01-01", end_date: "2026-12-31", status: "OPEN" }] }));
      }
      if (url.endsWith("/accounts") || url.endsWith("/journals")) return Promise.resolve(reply([]));
      if (url.endsWith("/properties")) return Promise.resolve(reply([]));
      if (url.endsWith("/banks") || url.endsWith("/loans") || url.includes("/api/operations?")) {
        return Promise.resolve(reply([]));
      }
      if (url.includes("/tenants")) return Promise.resolve(reply([]));
      if (url.includes("/entries?")) return Promise.resolve(reply({ entries: [], count: 0 }));
      return Promise.resolve(reply({}));
    }));
    const router = createTestRouter([ROUTES.home, ledgerPath("Journal"), operationsPath("Banque")], 0);
    render(<RouterProvider router={router} />);
    expect(await screen.findByRole("heading", { name: /De l’écriture à la liasse/ })).toBeInTheDocument();
    await router.navigate(ledgerPath("Journal"));
    expect(await screen.findByRole("heading", { name: "Votre comptabilité" })).toBeInTheDocument();
    await router.navigate(-1);
    expect(await screen.findByRole("heading", { name: /De l’écriture à la liasse/ })).toBeInTheDocument();
    await router.navigate(operationsPath("Banque"));
    expect(await screen.findByRole("heading", { name: "Opérations et banque" })).toBeInTheDocument();
  });

  it("asks before leaving a modified ledger draft", async () => {
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      if (url === "/api/status") return Promise.resolve(reply());
      if (url.endsWith("/setup")) {
        return Promise.resolve(reply({ activity: { activity_name: "Test" }, years: [{ id: 1, year: 2026, start_date: "2026-01-01", end_date: "2026-12-31", status: "OPEN" }] }));
      }
      if (url.endsWith("/accounts")) {
        return Promise.resolve(reply([{ number: "512000", label: "Banque", active: true, account_type: "ASSET" }]));
      }
      if (url.endsWith("/journals")) return Promise.resolve(reply([{ code: "OD", label: "Opérations", active: true }]));
      if (url.includes("/entries?")) return Promise.resolve(reply({ entries: [], count: 0 }));
      return Promise.resolve(reply({}));
    }));
    renderAt(ledgerPath("Brouillons"));
    await userEvent.click(await screen.findByRole("button", { name: "Nouvelle écriture" }));
    await userEvent.type(screen.getByLabelText("Libellé de l’écriture"), "Brouillon en cours");
    await userEvent.click(screen.getByRole("link", { name: "Vue d’ensemble" }));
    expect(await screen.findByRole("alertdialog")).toHaveTextContent("Quitter sans enregistrer");
    await userEvent.click(screen.getByRole("button", { name: "Rester sur la page" }));
    expect(screen.getByRole("heading", { name: "Votre comptabilité" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "Vue d’ensemble" }));
    await userEvent.click(screen.getByRole("button", { name: "Quitter sans enregistrer" }));
    expect(await screen.findByRole("heading", { name: /De l’écriture à la liasse/ })).toBeInTheDocument();
  });
});
