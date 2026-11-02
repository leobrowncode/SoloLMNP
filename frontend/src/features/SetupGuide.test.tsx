import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { Setup } from "../api/ledger";
import { guideNoteFrom } from "./declarationSetup";
import SetupGuide from "./SetupGuide";

function ok() {
  return Promise.resolve(new Response("{}", { status: 200 }));
}

function installFetch() {
  const fetcher = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    void input;
    void init;
    return ok();
  });
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}

function renderGuide(setup: Setup) {
  const show = vi.fn();
  const onReload = vi.fn();
  const router = createMemoryRouter(
    [{ path: "/", element: <SetupGuide setup={setup} hash="" onReload={onReload} show={show} /> }],
    { initialEntries: ["/"] },
  );
  render(<RouterProvider router={router} />);
  return { router, show, onReload };
}

describe("SetupGuide", () => {
  it("derives the SIREN from the SIRET and creates the activity in one step", async () => {
    const fetcher = installFetch();
    const { show, onReload, router } = renderGuide({ activity: null, years: [] });
    expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("SIRET");
    fireEvent.change(screen.getByLabelText("SIRET"), { target: { value: "123 456 789 00019" } });
    const siren = screen.getByLabelText("SIREN");
    expect(siren).toHaveValue("123456789");
    expect(siren).toHaveAttribute("readonly");
    fireEvent.change(screen.getByLabelText("Nom de l’activité"), { target: { value: "LMNP fictif" } });
    fireEvent.change(screen.getByLabelText(/Date réelle de début/), { target: { value: "2026-04-06" } });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer et continuer" }));
    await waitFor(() => expect(onReload).toHaveBeenCalled());
    const call = fetcher.mock.calls.find((item) => String(item[0]).endsWith("/activity"));
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      activity_name: "LMNP fictif",
      activity_start_date: "2026-04-06",
      siren: "123456789",
      siret: "12345678900019",
    });
    expect(show).toHaveBeenCalled();
    expect(router.state.location.pathname).toBe("/");
  });

  it("keeps a partial SIRET on the identity step", () => {
    const fetcher = installFetch();
    renderGuide({ activity: null, years: [] });
    fireEvent.change(screen.getByLabelText("SIRET"), { target: { value: "123456789000" } });
    fireEvent.change(screen.getByLabelText("Nom de l’activité"), { target: { value: "LMNP fictif" } });
    fireEvent.change(screen.getByLabelText(/Date réelle de début/), { target: { value: "2026-04-06" } });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer et continuer" }));
    expect(screen.getByRole("alert")).toHaveTextContent("14 chiffres");
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("proposes the exercise, then opens the property form", async () => {
    const fetcher = installFetch();
    const { router, onReload } = renderGuide({
      activity: {
        activity_name: "LMNP fictif",
        activity_start_date: "2026-04-06",
        siren: "123456789",
        siret: "12345678900019",
      },
      years: [],
    });
    expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("Exercice");
    expect(screen.getByLabelText(/Début de l’exercice/)).toHaveValue("2026-04-06");
    expect(screen.getByLabelText(/Fin de l’exercice/)).toHaveValue("2026-12-31");
    expect(screen.getByLabelText("Millésime fiscal")).toHaveValue("2026");
    fireEvent.click(screen.getByRole("button", { name: "Créer l’exercice" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/operations/biens"));
    expect(router.state.location.hash).toBe("#ajouter-bien");
    expect(guideNoteFrom(router.state.location.state)).toMatch(/Indiquez le logement/);
    expect(onReload).not.toHaveBeenCalled();
    const call = fetcher.mock.calls.find((item) => String(item[0]).endsWith("/years"));
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
      start_date: "2026-04-06",
      end_date: "2026-12-31",
      fiscal_vintage: "2026",
      year: 2026,
    });
  });

  it("opens the property form when the SIREN arrives after the exercise", async () => {
    installFetch();
    const { router } = renderGuide({
      activity: { activity_name: "LMNP fictif", siren: null, siret: null },
      years: [{ id: 1, year: 2026, start_date: "2026-01-01", end_date: "2026-12-31", status: "OPEN" }],
    });
    fireEvent.change(screen.getByLabelText("SIREN", { exact: true }), { target: { value: "123456789" } });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer l’identité" }));
    await waitFor(() => expect(router.state.location.hash).toBe("#ajouter-bien"));
  });
});
