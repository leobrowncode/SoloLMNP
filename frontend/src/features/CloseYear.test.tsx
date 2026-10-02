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
