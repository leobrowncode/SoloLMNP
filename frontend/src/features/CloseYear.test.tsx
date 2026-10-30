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

test("links a missing or stale fiscal computation to the calculation", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response({
    blocking: true,
    errors: [
      { code: "FISCAL_NOT_COMPUTED", message: "Aucun calcul fiscal n’est enregistré pour cet exercice." },
      { code: "FISCAL_STALE", message: "Le calcul fiscal ne correspond plus au ledger." },
    ],
    warnings: [],
  }));
  render(<CloseYear year={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  const links = await screen.findAllByRole("link", { name: "Calculer le résultat fiscal" });
  expect(links.length).toBeGreaterThanOrEqual(2);
  for (const link of links) expect(link).toHaveAttribute("href", "/fiscalite#calcul-fiscal");
  const prepare = screen.getByRole("button", { name: "Accuser et préparer la clôture" });
  expect(prepare).toHaveAttribute("aria-describedby", "close-prepare-causes");
  const causes = document.getElementById("close-prepare-causes");
  expect(causes).toHaveTextContent("Aucun calcul fiscal n’est enregistré pour cet exercice.");
  expect(causes).toHaveTextContent("Le calcul fiscal ne correspond plus au ledger.");
  expect(screen.getByRole("button", { name: "Accuser et préparer la clôture" })).toBeDisabled();
});

test("exposes warning acknowledgements as named checkboxes", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response({
    blocking: false,
    errors: [],
    warnings: [{ code: "FISCAL_RESEARCH", message: "Le calcul fiscal reste en recherche." }],
  }));
  render(<CloseYear year={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  const box = await screen.findByRole("checkbox", { name: "Le calcul fiscal reste en recherche." });
  expect(screen.getByRole("button", { name: "Accuser et préparer la clôture" })).toBeDisabled();
  fireEvent.click(box);
  expect(screen.getByRole("button", { name: "Accuser et préparer la clôture" })).toBeEnabled();
});

test("a new precheck replaces acknowledgements and closing reports a server refusal", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(response({
      blocking: false,
      errors: [],
      warnings: [
        { code: "OLD", message: "Ancien avertissement." },
        { code: "KEEP", message: "Avertissement commun." },
      ],
    }))
    .mockResolvedValueOnce(response({
      blocking: false,
      errors: [],
      warnings: [{ code: "NEW", message: "Nouvel avertissement." }],
    }))
    .mockResolvedValueOnce(response({
      blocking: false,
      year_status: "READY_TO_CLOSE",
      errors: [],
      warnings: [{ code: "NEW", message: "Nouvel avertissement." }],
    }));
  const onExerciseTransition = vi.fn();
  render(<CloseYear year={1} onExerciseTransition={onExerciseTransition} />);

  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  const oldBox = await screen.findByRole("checkbox", { name: "Ancien avertissement." });
  fireEvent.click(oldBox);
  fireEvent.click(screen.getByRole("checkbox", { name: "Avertissement commun." }));
  expect(screen.getByRole("button", { name: "Accuser et préparer la clôture" })).toBeEnabled();

  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  const nextBox = await screen.findByRole("checkbox", { name: "Nouvel avertissement." });
  expect(screen.queryByRole("checkbox", { name: "Ancien avertissement." })).not.toBeInTheDocument();
  expect(nextBox).not.toBeChecked();
  expect(screen.getByRole("button", { name: "Accuser et préparer la clôture" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Confirmer la clôture" })).toBeDisabled();

  fireEvent.click(nextBox);
  fireEvent.click(screen.getByRole("button", { name: "Accuser et préparer la clôture" }));
  expect(await screen.findByText(/prêt à clôturer/)).toBeInTheDocument();
  const readyCall = fetchMock.mock.calls.find((call) => String(call[0]).endsWith("/ready"));
  expect(JSON.parse(String((readyCall?.[1] as RequestInit | undefined)?.body))).toEqual({
    acknowledged: ["NEW"],
  });
  expect(onExerciseTransition).toHaveBeenCalledTimes(1);

  fetchMock.mockResolvedValueOnce(response({ detail: { message: "Clôture refusée." } }, 409));
  fireEvent.click(screen.getByRole("button", { name: "Confirmer la clôture" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Clôture refusée.");
  expect(screen.queryByText(/Exercice clôturé/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Confirmer la clôture" })).toBeEnabled();
  expect(onExerciseTransition).toHaveBeenCalledTimes(1);

  fetchMock.mockResolvedValueOnce(response({ fiscal_year_id: 1, status: "CLOSED", generation: 1 }));
  fireEvent.click(screen.getByRole("button", { name: "Confirmer la clôture" }));
  expect(await screen.findByText(/Exercice clôturé/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Confirmer la clôture" })).toBeDisabled();
  expect(onExerciseTransition).toHaveBeenCalledTimes(2);
});

test("returning the exercise to open clears the previous closing ceremony", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response({
    blocking: false,
    year_status: "CLOSED",
    errors: [],
    warnings: [{ code: "OLD", message: "Ancien avertissement." }],
  }));
  const { rerender } = render(<CloseYear year={1} yearStatus="CLOSED" />);
  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  expect(await screen.findByRole("checkbox", { name: "Ancien avertissement." })).toBeInTheDocument();
  rerender(<CloseYear year={1} yearStatus="OPEN" />);
  expect(screen.queryByRole("checkbox", { name: "Ancien avertissement." })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Confirmer la clôture" })).not.toBeInTheDocument();
});

test("a failed precheck keeps the acknowledgements already on screen", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(response({
      blocking: false,
      errors: [],
      warnings: [{ code: "A", message: "Avertissement stable." }],
    }))
    .mockResolvedValueOnce(response({ detail: { message: "Pré-contrôle indisponible." } }, 503));
  render(<CloseYear year={1} />);
  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  fireEvent.click(await screen.findByRole("checkbox", { name: "Avertissement stable." }));
  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Pré-contrôle indisponible.");
  expect(screen.getByRole("checkbox", { name: "Avertissement stable." })).toBeChecked();
  expect(screen.getByRole("button", { name: "Accuser et préparer la clôture" })).toBeEnabled();
});
