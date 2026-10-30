import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { isDashboard } from "../api/dashboard";
import { dashboardFixture } from "./dashboardFixture";
import OverviewDashboard from "./OverviewDashboard";

function reply(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function renderBoard() {
  return render(
    <MemoryRouter>
      <OverviewDashboard />
    </MemoryRouter>,
  );
}

describe("overview dashboard", () => {
  it("shows a loading state and not a local checklist", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
    renderBoard();
    expect(screen.getByText("Chargement du dossier…")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Continuer" })).not.toBeInTheDocument();
    expect(screen.queryByText("À faire")).not.toBeInTheDocument();
  });

  it("shows the server error and retries", async () => {
    const request = vi.fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(reply(dashboardFixture("empty")));
    vi.stubGlobal("fetch", request);
    renderBoard();
    expect(await screen.findByRole("alert")).toHaveTextContent("offline");
    expect(screen.queryByRole("link", { name: "Continuer" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(await screen.findByRole("link", { name: "Continuer" })).toHaveAttribute(
      "href",
      "/comptabilite/brouillons#creer-activite",
    );
  });

  it("uses the empty screen when the server returns no steps", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(dashboardFixture("blank"))));
    renderBoard();
    expect(await screen.findByText("Aucun dossier à afficher.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Continuer" })).not.toBeInTheDocument();
  });

  it("shows an empty dossier as steps to start, not the menu", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(dashboardFixture("empty"))));
    renderBoard();
    expect(await screen.findByRole("link", { name: "Continuer" })).toHaveAttribute(
      "href",
      "/comptabilite/brouillons#creer-activite",
    );
    const steps = screen.getByRole("list", { name: "Étapes du dossier" });
    expect(steps).toHaveTextContent("Structure et SIREN");
    expect(steps).toHaveTextContent("À faire");
    expect(steps).not.toHaveTextContent("Comptabilité");
    expect(steps).not.toHaveTextContent("États comptables");
    expect(screen.getByRole("link", { name: "Créer l’activité" })).toHaveAttribute(
      "href",
      "/comptabilite/brouillons#creer-activite",
    );
    expect(screen.queryByText(/déclarable/i)).not.toBeInTheDocument();
  });

  it("shows a partial dossier with the missing SIREN and the last event", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(dashboardFixture("partial"))));
    renderBoard();
    expect((await screen.findAllByText("Le SIREN n’est pas renseigné.")).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Continuer" })).toHaveAttribute(
      "href",
      "/comptabilite/brouillons#identite-liasse",
    );
    expect(screen.getByText(/Exercice 2026 créé/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Renseigner le SIREN" })).toBeInTheDocument();
    expect(screen.getAllByText("En cours").length).toBeGreaterThan(0);
    expect(screen.getByText("Terminé")).toBeInTheDocument();
    expect(screen.getByText(/Premier exercice/)).toBeInTheDocument();
  });

  it("shows a blocked dossier in cents and keeps the research vintage", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(dashboardFixture("blocked"))));
    renderBoard();
    expect((await screen.findAllByText("Bloqué")).length).toBeGreaterThan(0);
    expect(screen.getByText(/Montant des opérations/)).toBeInTheDocument();
    expect(screen.getByText("123.45 €")).toBeInTheDocument();
    expect(screen.getByText("25.00 €")).toBeInTheDocument();
    expect(screen.getByText("0.00 €")).toBeInTheDocument();
    expect(screen.getByText(/Millésime en recherche/)).toBeInTheDocument();
    expect(screen.queryByText(/déclarable/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Continuer" })).toHaveAttribute(
      "href",
      "/comptabilite/brouillons#identite-liasse",
    );
  });

  it("opens the closing screen from a dossier ready to close", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(dashboardFixture("ready"))));
    renderBoard();
    expect(await screen.findByRole("link", { name: "Continuer" })).toHaveAttribute(
      "href",
      "/fiscalite#close-title",
    );
    expect(screen.getByText("Prochaine action : confirmer la clôture.")).toBeInTheDocument();
    expect(screen.getByText("Exercice prêt à clôturer.")).toBeInTheDocument();
    expect(screen.getByText(/Exercice passé en prêt à clôturer/)).toBeInTheDocument();
    expect(screen.getAllByText("Prête").length).toBeGreaterThan(0);
    expect(screen.queryByText(/déclarable/i)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Aide : Clôture" }));
    expect(screen.getByRole("tooltip")).toHaveTextContent("Gel de l’exercice");
  });

  it("moves a following year from a blocked opening to the posted balances", async () => {
    const request = vi.fn()
      .mockResolvedValueOnce(reply(dashboardFixture("followingBlocked")))
      .mockResolvedValueOnce(reply(dashboardFixture("followingOpen")))
      .mockResolvedValueOnce(reply(dashboardFixture("followingPosted")));
    vi.stubGlobal("fetch", request);
    const view = renderBoard();
    expect(await screen.findByText("Bloqué")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Clôturer l’exercice précédent" })).toHaveAttribute(
      "href",
      "/fiscalite#close-title",
    );
    expect(screen.getByRole("link", { name: "Continuer" })).toHaveAttribute("href", "/fiscalite#close-title");
    expect(screen.getAllByText("Terminé").length).toBeGreaterThan(0);
    view.unmount();

    const open = renderBoard();
    expect((await screen.findAllByText("Les à-nouveaux ne sont pas comptabilisés.")).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Prévisualiser les à-nouveaux" })).toHaveAttribute(
      "href",
      "/etats-comptables#opening-title",
    );
    expect(screen.getByRole("link", { name: "Continuer" })).toHaveAttribute(
      "href",
      "/etats-comptables#opening-title",
    );
    expect(screen.getByText("Prête")).toBeInTheDocument();
    open.unmount();

    renderBoard();
    expect(await screen.findByText("Les à-nouveaux sont comptabilisés.")).toBeInTheDocument();
    expect(screen.getByText("2500.50 €")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Continuer" })).toHaveAttribute("href", "/fiscalite#calcul-fiscal");
    expect(screen.queryByText(/déclarable/i)).not.toBeInTheDocument();
  });

  it("rejects a payload that calls the dossier declarable", () => {
    const ready = dashboardFixture("ready");
    expect(isDashboard(ready)).toBe(true);
    expect(isDashboard({ ...ready, steps: [] })).toBe(true);
    expect(isDashboard({
      ...ready,
      dossier: { ...ready.dossier, status: "declarable", label: "Déclarable", vintage_status: "declarable" },
    })).toBe(false);
    expect(isDashboard({
      ...ready,
      steps: ready.steps.map((item) => item.id === "filing"
        ? { ...item, summary: "Liasse Déclarable" }
        : item),
    })).toBe(false);
  });
});
