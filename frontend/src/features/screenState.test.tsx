import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import ScreenStatus from "./ScreenStatus";
import {
  beginLoad, emptyView, failLoad, finishLoad, idleView, showsData, showsLoading, STALE_NOTICE, toApiError,
  type ScreenView,
} from "./screenState";

describe("screen state", () => {
  it("starts idle and never stays loading after an initial error", () => {
    let state = idleView<string>();
    expect(state.phase).toBe("idle");
    state = beginLoad(state, false);
    expect(state.phase).toBe("loading");
    expect(showsLoading(state)).toBe(true);
    expect(showsData(state)).toBe(false);
    state = failLoad(state, toApiError(new Error("Hors ligne")), false);
    expect(state.phase).toBe("error");
    expect(state.stale).toBe(false);
    expect(state.data).toBeNull();
    expect(showsLoading(state)).toBe(false);
    expect(state.error?.message).toBe("Hors ligne");
  });

  it("keeps the previous payload when a refresh fails and it is safe", () => {
    let state = finishLoad("bilan");
    state = beginLoad(state, true);
    expect(showsData(state)).toBe(true);
    expect(state.phase).toBe("loading");
    state = failLoad(state, { code: "HTTP_ERROR", message: "Coupure" }, true);
    expect(state.phase).toBe("error");
    expect(state.stale).toBe(true);
    expect(state.data).toBe("bilan");
    expect(showsLoading(state)).toBe(false);
  });

  it("drops unsafe totals on refresh and recovers to loaded or empty", () => {
    let state = finishLoad("10.01");
    state = beginLoad(state, false);
    expect(state.data).toBeNull();
    state = failLoad(state, { code: "HTTP_ERROR", message: "Refus" }, false);
    expect(state.data).toBeNull();
    expect(state.stale).toBe(false);
    const dropped = beginLoad(state, false);
    expect(dropped.data).toBeNull();
    expect(dropped.phase).toBe("loading");
    state = finishLoad("ok");
    expect(state.phase).toBe("loaded");
    expect(state.data).toBe("ok");
    expect(emptyView().phase).toBe("empty");
    expect(finishLoad([], (rows: string[]) => rows.length === 0).phase).toBe("empty");
  });
});

function Probe() {
  const [state, setState] = useState<ScreenView<string>>(idleView());
  const [script, setScript] = useState<Array<"error" | "data">>(["error", "data", "error", "data"]);
  function load(keep: boolean) {
    const step = script[0] ?? "data";
    setScript((rows) => rows.slice(1));
    setState((current) => {
      const started = beginLoad(current, keep && current.data !== null);
      if (step === "error") {
        return failLoad(started, { code: "HTTP_ERROR", message: "Lecture impossible" }, started.data !== null);
      }
      return finishLoad(started.data ? "dossier à jour" : "dossier");
    });
  }
  const data = showsData(state) ? state.data : null;
  return (
    <section>
      <button type="button" onClick={() => load(Boolean(data))}>Charger</button>
      <ScreenStatus state={state} onRetry={() => load(true)} loading={<p>Chargement…</p>} empty={<p>Aucun dossier.</p>} />
      {data && <p>{data}</p>}
    </section>
  );
}

describe("ScreenStatus", () => {
  it("covers an initial error, a failed refresh and a recovery", () => {
    render(<Probe />);
    fireEvent.click(screen.getByRole("button", { name: "Charger" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Lecture impossible");
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
    expect(screen.queryByText("Chargement…")).not.toBeInTheDocument();
    expect(screen.queryByText("Aucun dossier.")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(screen.getByText("dossier")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Charger" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Lecture impossible");
    expect(screen.getByText("dossier")).toBeInTheDocument();
    expect(screen.getByText(STALE_NOTICE)).toBeInTheDocument();
    expect(screen.queryByText("Chargement…")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(screen.getByText("dossier à jour")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(STALE_NOTICE)).not.toBeInTheDocument();
  });
});
