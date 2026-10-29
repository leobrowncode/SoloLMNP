import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import CloseYear from "./CloseYear";

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});

test("focuses the precheck error and names each warning", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response({
    detail: { message: "Exercice verrouillé" },
  }, 409));
  render(<CloseYear year={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Exercice verrouillé");
  expect(alert).toHaveFocus();
});

test("links to the fiscal calculation when it is missing", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response({
    blocking: true,
    errors: [{ code: "FISCAL_NOT_COMPUTED", message: "Aucun calcul fiscal n’est enregistré pour cet exercice." }],
    warnings: [],
  }));
  render(<CloseYear year={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  const link = await screen.findByRole("link", { name: "Calculer le résultat fiscal" });
  expect(link).toHaveAttribute("href", "#calcul-fiscal");
});

test("links to the fiscal calculation when it is stale", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response({
    blocking: true,
    errors: [{ code: "FISCAL_STALE", message: "Le calcul fiscal ne correspond plus au ledger." }],
    warnings: [],
  }));
  render(<CloseYear year={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  expect(await screen.findByRole("link", { name: "Calculer le résultat fiscal" })).toHaveAttribute("href", "#calcul-fiscal");
});

test("does not offer the fiscal calculation link for another error", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response({
    blocking: true,
    errors: [{ code: "YEAR_DRAFTS", message: "Des brouillons sont encore ouverts." }],
    warnings: [],
  }));
  render(<CloseYear year={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Des brouillons sont encore ouverts.");
  expect(screen.queryByRole("link", { name: "Calculer le résultat fiscal" })).not.toBeInTheDocument();
});

test("exposes warning acknowledgements as named checkboxes", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response({
    blocking: false,
    errors: [],
    warnings: [{ code: "FISCAL_RESEARCH", message: "Le calcul fiscal reste en recherche." }],
  }));
  render(<CloseYear year={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  expect(await screen.findByRole("checkbox", { name: "Le calcul fiscal reste en recherche." })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Accuser et préparer la clôture" })).toBeEnabled();
});
