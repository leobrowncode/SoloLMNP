import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import App from "./App";
import { isApplicationStatus } from "./api/status";

const ready = {
  application_version: "0.2.0", phase: "foundation",
  database: { status: "ready", schema_revision: "0001_foundation", expected_revision: "0001_foundation" },
  fiscal: { status: "research_only", available_vintages: [] },
};
function reply(body: unknown = ready, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("Foundation status", () => {
  it("shows loading while the service is pending", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
    render(<App />);
    expect(screen.getByRole("button", { name: /Vérification/ })).toBeDisabled();
    expect(screen.getByText(/Connexion au service et vérification/)).toBeInTheDocument();
  });

  it("shows centralization before the fiscal calculation, precheck and closing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply()));
    render(<App />);
    const statements = await screen.findByRole("button", { name: /États comptables/ });
    const fiscal = screen.getByRole("button", { name: /Fiscalité LMNP/ });
    expect(statements).toHaveTextContent("Bilan, résultat, puis centralisation.");
    expect(fiscal).toHaveTextContent("Calcul fiscal, pré-contrôle, clôture, puis sorties figées.");
    expect(statements.compareDocumentPosition(fiscal) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("displays live readiness without claiming tax readiness", async () => {
    const request = vi.fn().mockResolvedValue(reply());
    vi.stubGlobal("fetch", request);
    render(<App />);
    expect(await screen.findByText(/Base prête/)).toBeInTheDocument();
    expect(screen.getByText(/Aucun envoi n’est effectué/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Comptabilité/ })).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/api/status", expect.objectContaining({ cache: "no-store" }));
  });

  it("shows an unmigrated database as not ready on HTTP 503", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({
      ...ready, database: { ...ready.database, status: "not_ready", schema_revision: null },
    }, 503)));
    render(<App />);
    expect(await screen.findByText("Le stockage nécessite une vérification")).toBeInTheDocument();
    expect(screen.queryByText(/Base prête/)).not.toBeInTheDocument();
  });

  it("allows retry after a network failure", async () => {
    const request = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(reply());
    vi.stubGlobal("fetch", request);
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Connexion au service indisponible");
    await userEvent.click(screen.getByRole("button", { name: /Actualiser/ }));
    expect(await screen.findByText(/Base prête/)).toBeInTheDocument();
    expect(request.mock.calls.filter(([url]) => url === "/api/status")).toHaveLength(2);
  });

  it("rejects malformed API output", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({ status: "ok" })));
    render(<App />);
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
    render(<App />);
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
    render(<App />);
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
    render(<App />);
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
    const view = render(<App />);
    await waitFor(() => expect(request).toHaveBeenCalledOnce());
    const init = request.mock.calls[0]?.[1] as RequestInit;
    view.unmount();
    expect(init.signal?.aborted).toBe(true);
  });
});
