import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import LocalFeedbackView, { SaveNoticeHost } from "./LocalFeedback";
import { SAVE_NOTICE_MS, saveFeedbackText, useSaveNotice, type SaveNotice } from "./localFeedback";

const at = new Date(2026, 9, 30, 15, 42);

function notice(overrides: Partial<SaveNotice> = {}): SaveNotice {
  return {
    id: "notice-1",
    text: saveFeedbackText({ kind: "Immobilisation", name: "Appartement Lyon", action: "créée", at }),
    targetId: "asset-lyon",
    detail: "Calculez ensuite les périodes.",
    next: { label: "Calculer les périodes", href: "/immobilisations#calculer-periodes" },
    ...overrides,
  };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("save acknowledgement", () => {
  test("names the object, the action and the time", () => {
    expect(saveFeedbackText({
      kind: "Immobilisation",
      name: "Appartement Lyon",
      action: "créée",
      at,
    })).toBe("Immobilisation “Appartement Lyon” créée à 15:42");
  });

  test("announces beside the control without taking focus", () => {
    const onDismiss = vi.fn();
    render(
      <>
        <button type="button">Enregistrer</button>
        <article id="asset-lyon">
          <h3>Appartement Lyon</h3>
          <LocalFeedbackView notice={notice()} containerId="asset-lyon" onDismiss={onDismiss} />
        </article>
      </>,
    );
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent("Immobilisation “Appartement Lyon” créée à 15:42");
    expect(status).toHaveTextContent("Calculez ensuite les périodes.");
    expect(status).not.toHaveFocus();
    expect(document.getElementById("asset-lyon")).toHaveClass("save-highlight");
    expect(screen.getByRole("link", { name: "Calculer les périodes" })).toHaveAttribute(
      "href",
      "/immobilisations#calculer-periodes",
    );
    fireEvent.click(screen.getByRole("button", { name: "Fermer le message" }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  test("focuses the target only when asked, never the live region", () => {
    const button = document.createElement("button");
    button.textContent = "Déjà là";
    document.body.append(button);
    button.focus();
    render(
      <article id="asset-lyon" tabIndex={-1}>
        <LocalFeedbackView notice={notice({ focus: true })} containerId="asset-lyon" onDismiss={vi.fn()} />
      </article>,
    );
    expect(document.getElementById("asset-lyon")).toHaveFocus();
    expect(screen.getByRole("status")).not.toHaveFocus();
    button.remove();
  });

  test("closes on its own, and waits while the pointer is over the message", () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();
    render(
      <article id="asset-lyon">
        <LocalFeedbackView notice={notice()} containerId="asset-lyon" onDismiss={onDismiss} />
      </article>,
    );
    const message = screen.getByRole("status").parentElement as HTMLElement;
    fireEvent.pointerEnter(message);
    act(() => { vi.advanceTimersByTime(SAVE_NOTICE_MS + 1000); });
    expect(onDismiss).not.toHaveBeenCalled();
    fireEvent.pointerLeave(message);
    act(() => { vi.advanceTimersByTime(SAVE_NOTICE_MS); });
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  test("moves from the triggering control onto the created row", async () => {
    function Harness({ withRow }: { withRow: boolean }) {
      const { notice, show, dismiss } = useSaveNotice();
      const [opened, setOpened] = useState(withRow);
      return (
        <>
          <button
            type="button"
            onClick={() => show({
              kind: "Compte",
              name: "164100 Second emprunt",
              action: "créé",
              at,
              targetId: "ajouter-compte",
              highlightId: "compte-164100",
              next: { label: "Saisir une écriture", href: "/comptabilite/brouillons#nouvelle-ecriture" },
            })}
          >
            Ajouter le compte
          </button>
          <form id="ajouter-compte">
            <SaveNoticeHost place="ajouter-compte" notice={notice} onDismiss={dismiss} />
          </form>
          {opened && <article id="compte-164100">164100 Second emprunt</article>}
          <button type="button" onClick={() => setOpened(true)}>Afficher la ligne</button>
        </>
      );
    }
    const view = render(<Harness withRow={false} />);
    fireEvent.click(screen.getByRole("button", { name: "Ajouter le compte" }));
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("Compte “164100 Second emprunt” créé à 15:42");
    expect(document.getElementById("ajouter-compte")).toContainElement(status);
    fireEvent.click(screen.getByRole("button", { name: "Afficher la ligne" }));
    await waitFor(() => {
      expect(document.getElementById("compte-164100")).toContainElement(screen.getByRole("status"));
    });
    expect(document.getElementById("compte-164100")).toHaveClass("save-highlight");
    view.unmount();
  });
});
