import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { dashboardFixture } from "./dashboardFixture";
import DossierProgress from "./DossierProgress";

function renderProgress(kind: Parameters<typeof dashboardFixture>[0]) {
  return render(<DossierProgress progression={dashboardFixture(kind).progression} />);
}

describe("dossier progression", () => {
  it("shows the short progress line and not the step sentence", () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    renderProgress("empty");
    const region = screen.getByRole("region", { name: "Progression du dossier" });
    expect(region).toHaveTextContent("0/6");
    expect(region).toHaveTextContent("À faire");
    expect(region).not.toHaveTextContent("L’activité n’est pas créée.");
    expect(screen.queryByRole("link", { name: "Continuer" })).not.toBeInTheDocument();
    expect(setItem).not.toHaveBeenCalled();
  });

  it("follows a partial dossier without repeating the missing SIREN", () => {
    renderProgress("partial");
    const region = screen.getByRole("region", { name: "Progression du dossier" });
    expect(region).toHaveTextContent("1/6");
    expect(region).toHaveTextContent("En cours");
    expect(region).not.toHaveTextContent("Le SIREN n’est pas renseigné.");
  });

  it("names a blocked step without the export detail", () => {
    renderProgress("blocked");
    const region = screen.getByRole("region", { name: "Progression du dossier" });
    expect(region).toHaveTextContent("Structure et SIREN");
    expect(region).not.toHaveTextContent("Liasse");
    expect(region).not.toHaveTextContent("FEC");
  });

  it("shows a following year that still needs the fiscal result", () => {
    renderProgress("followingPosted");
    const region = screen.getByRole("region", { name: "Progression du dossier" });
    expect(region).toHaveTextContent("4/6");
    expect(region).toHaveTextContent("En cours");
    expect(screen.queryByText(/déclarable/i)).not.toBeInTheDocument();
  });

  it("renders nothing when the server has no steps", () => {
    const { container } = renderProgress("blank");
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByRole("region", { name: "Progression du dossier" })).not.toBeInTheDocument();
  });
});
