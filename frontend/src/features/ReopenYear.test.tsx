import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import ReopenYear from "./ReopenYear";

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});

const validReason = "Correction d’une dotation comptabilisée par erreur sur l’exercice.";

test("lists both reopen prerequisites before anything is typed", () => {
  render(<ReopenYear year={1} />);
  const causes = document.getElementById("reopen-causes");
  expect(causes).toHaveTextContent("au moins 10 caractères");
  expect(causes).toHaveTextContent("exactement ROUVRIR");
});

test("blocks reopen with a wrong confirmation label", () => {
  vi.spyOn(globalThis, "fetch");
  render(<ReopenYear year={1} />);
  fireEvent.change(screen.getByLabelText(/Motif de la réouverture/), {
    target: { value: validReason },
  });
  fireEvent.change(screen.getByLabelText(/Confirmation/), {
    target: { value: "ROUVRIRX" },
  });
  const button = screen.getByRole("button", { name: "Réouvrir l’exercice" });
  expect(button).toBeDisabled();
  expect(button).toHaveAttribute("aria-describedby", "reopen-causes");
  expect(document.getElementById("reopen-causes")).toHaveTextContent("exactement ROUVRIR");
  expect(document.querySelector('a[href="/fiscalite#reopen-confirmation"]')).toBeTruthy();
});

test("blocks reopen when the reason is missing or too short", () => {
  vi.spyOn(globalThis, "fetch");
  render(<ReopenYear year={1} />);
  fireEvent.change(screen.getByLabelText(/Confirmation/), {
    target: { value: "ROUVRIR" },
  });
  expect(screen.getByRole("button", { name: "Réouvrir l’exercice" })).toBeDisabled();
  expect(document.getElementById("reopen-causes")).toHaveTextContent("au moins 10 caractères");
  expect(document.querySelector('a[href="/fiscalite#reopen-motif"]')).toBeTruthy();
  fireEvent.change(screen.getByLabelText(/Motif de la réouverture/), {
    target: { value: "   " },
  });
  expect(screen.getByRole("button", { name: "Réouvrir l’exercice" })).toBeDisabled();
  expect(document.getElementById("reopen-causes")).toHaveTextContent("au moins 10 caractères");
});

test("reopens a closed exercise and refreshes the parent view", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response({
    fiscal_year_id: 1,
    status: "OPEN",
  }));
  const onExerciseTransition = vi.fn();
  render(<ReopenYear year={1} onExerciseTransition={onExerciseTransition} />);
  fireEvent.change(screen.getByLabelText(/Motif de la réouverture/), {
    target: { value: validReason },
  });
  fireEvent.change(screen.getByLabelText(/Confirmation/), {
    target: { value: "ROUVRIR" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Réouvrir l’exercice" }));
  expect(await screen.findByText(/Exercice rouvert/)).toBeInTheDocument();
  const call = fetchMock.mock.calls.find((item) => String(item[0]).endsWith("/reopen"));
  expect(JSON.parse(String((call?.[1] as RequestInit | undefined)?.body))).toEqual({
    confirmation: "ROUVRIR",
    reason: validReason,
  });
  expect(onExerciseTransition).toHaveBeenCalledTimes(1);
});

test("lists invalidated artefacts and stays usable at a 390px viewport", () => {
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
  const { container } = render(
    <div style={{ width: "390px", overflow: "hidden" }}>
      <ReopenYear year={1} />
    </div>,
  );
  expect(screen.getByRole("heading", { name: "Réouvrir l’exercice" })).toBeInTheDocument();
  expect(screen.getByText(/calculs fiscaux enregistrés/i)).toBeInTheDocument();
  expect(screen.getByText(/SUPERSEDED/i)).toBeInTheDocument();
  expect(screen.getByText(/exports figés/i)).toBeInTheDocument();
  expect(container.scrollWidth).toBeLessThanOrEqual(390);
});

test("shows a closed exercise reopen block inside the closing section", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(response({
    blocking: false,
    year_status: "CLOSED",
    errors: [],
    warnings: [],
  }));
  const CloseYear = (await import("./CloseYear")).default;
  render(<CloseYear year={1} yearStatus="CLOSED" />);
  fireEvent.click(screen.getByRole("button", { name: "Lancer le pré-contrôle" }));
  expect(await screen.findByRole("heading", { name: "Réouvrir l’exercice" })).toBeInTheDocument();
});
