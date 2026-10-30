import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import MutationStatus from "./MutationStatus";
import { useMutation } from "./useMutation";

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((finish) => { resolve = finish; });
  return { promise, resolve };
}

function Harness({ onRun }: { onRun: () => Promise<void> }) {
  const { busy, step, run } = useMutation();
  return (
    <>
      <button
        type="button"
        disabled={busy}
        aria-busy={busy || undefined}
        onClick={() => { void run(() => onRun(), "Étape en cours…"); }}
      >
        Lancer
      </button>
      <MutationStatus step={step} />
    </>
  );
}

test("a second click while the action is running does not start it again", async () => {
  const gate = deferred();
  let calls = 0;
  render(<Harness onRun={() => { calls += 1; return gate.promise; }} />);
  const button = screen.getByRole("button", { name: "Lancer" });
  fireEvent.click(button);
  expect(await screen.findByText("Étape en cours…")).toBeInTheDocument();
  expect(button).toBeDisabled();
  expect(button).toHaveAttribute("aria-busy", "true");
  fireEvent.click(button);
  expect(calls).toBe(1);
  await act(async () => { gate.resolve(); });
  expect(button).toBeEnabled();
  expect(screen.queryByText("Étape en cours…")).not.toBeInTheDocument();
});
