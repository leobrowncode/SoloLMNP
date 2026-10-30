import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { dashboardFixture } from "./dashboardFixture";
import DossierProgress from "./DossierProgress";

function reply(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function renderProgress() {
  return render(
    <MemoryRouter>
      <DossierProgress />
    </MemoryRouter>,
  );
}

describe("dossier progression", () => {
  it("follows the server from a first year to a following year and ignores localStorage", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const payloads = [
      dashboardFixture("empty"),
      dashboardFixture("partial"),
      dashboardFixture("followingBlocked"),
      dashboardFixture("followingPosted"),
    ];
    let index = 0;
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(reply(payloads[index]))));

    const first = renderProgress();
    expect(await screen.findByRole("region", { name: "Progression du dossier" })).toHaveTextContent("0/6");
    expect(screen.getByRole("region", { name: "Progression du dossier" })).toHaveTextContent("À faire");
    expect(screen.getByRole("link", { name: "Continuer" })).toHaveAttribute(
      "href",
      "/comptabilite/brouillons#creer-activite",
    );
    first.unmount();

    index = 1;
    const second = renderProgress();
    const partial = await screen.findByRole("region", { name: "Progression du dossier" });
    expect(partial).toHaveTextContent("1/6");
    expect(partial).toHaveTextContent("En cours");
    expect(partial).toHaveTextContent("Le SIREN n’est pas renseigné.");
    expect(screen.getByRole("link", { name: "Continuer" })).toHaveAttribute(
      "href",
      "/comptabilite/brouillons#identite-liasse",
    );
    second.unmount();

    index = 2;
    const third = renderProgress();
    const blocked = await screen.findByRole("region", { name: "Progression du dossier" });
    expect(blocked).toHaveTextContent("Bloqué");
    expect(screen.getByRole("link", { name: "Continuer" })).toHaveAttribute("href", "/fiscalite#close-title");
    third.unmount();

    index = 3;
    renderProgress();
    const posted = await screen.findByRole("region", { name: "Progression du dossier" });
    expect(posted).toHaveTextContent("4/6");
    expect(posted).toHaveTextContent("En cours");
    expect(screen.getByRole("link", { name: "Continuer" })).toHaveAttribute("href", "/fiscalite#calcul-fiscal");
    expect(screen.queryByText(/déclarable/i)).not.toBeInTheDocument();
    expect(setItem).not.toHaveBeenCalled();
  });

  it("retries a failed read without dropping a separate dossier status", async () => {
    const request = vi.fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(reply(dashboardFixture("partial")));
    vi.stubGlobal("fetch", request);
    renderProgress();
    expect(await screen.findByText("Progression indisponible.")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Progression du dossier" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Réessayer la progression" }));
    expect(await screen.findByRole("region", { name: "Progression du dossier" })).toHaveTextContent("1/6");
  });
});
