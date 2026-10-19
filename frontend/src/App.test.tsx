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

  it("displays live readiness without claiming tax readiness", async () => {
    const request = vi.fn().mockResolvedValue(reply());
    vi.stubGlobal("fetch", request);
    render(<App />);
    expect(await screen.findByText("Le socle technique répond correctement")).toBeInTheDocument();
    expect(screen.getByText("En recherche")).toBeInTheDocument();
    expect(screen.getByText(/Aucun montant déclarable/)).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/api/status", expect.objectContaining({ cache: "no-store" }));
  });

  it("shows an unmigrated database as not ready on HTTP 503", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({
      ...ready, database: { ...ready.database, status: "not_ready", schema_revision: null },
    }, 503)));
    render(<App />);
    expect(await screen.findByText("Le stockage nécessite une vérification")).toBeInTheDocument();
    expect(screen.queryByText("Le socle technique répond correctement")).not.toBeInTheDocument();
  });

  it("allows retry after a network failure", async () => {
    const request = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(reply());
    vi.stubGlobal("fetch", request);
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Connexion au service indisponible");
    await userEvent.click(screen.getByRole("button", { name: /Actualiser/ }));
    expect(await screen.findByText("Le socle technique répond correctement")).toBeInTheDocument();
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("rejects malformed API output", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply({ status: "ok" })));
    render(<App />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(isApplicationStatus(null)).toBe(false);
  });

  it("opens provisional statements and describes the delivered scope", async () => {
    const assetsReady = {
      ...ready,
      application_version: "0.5.0",
      phase: "assets" as const,
      database: { status: "ready", schema_revision: "0005_opening", expected_revision: "0005_opening" },
    };
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      const path = String(url);
      if (path.endsWith("/api/status")) return Promise.resolve(reply(assetsReady));
      if (path.endsWith("/api/ledger/setup")) {
        return Promise.resolve(reply({ activity: null, years: [] }));
      }
      return Promise.resolve(reply({ detail: { message: "unused" } }, 404));
    }));
    render(<App />);
    expect(await screen.findByText("Phase 5 · États provisoires")).toBeInTheDocument();
    expect(screen.getByText(/inventaire manuel justifié/)).toBeInTheDocument();
    expect(screen.getByText(/Aucun montant déclarable/)).toBeInTheDocument();
    expect(screen.queryByText(/L’inventaire, la continuité, le moteur fiscal/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Comptabilité" })).toHaveAttribute("aria-current", "page");
    await userEvent.click(screen.getByRole("link", { name: "États comptables" }));
    expect(await screen.findByRole("heading", { name: "États comptables provisoires" })).toBeInTheDocument();
    expect(screen.getByText(/Créez un exercice dans Comptabilité/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "États comptables" })).toHaveAttribute("aria-current", "page");
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
