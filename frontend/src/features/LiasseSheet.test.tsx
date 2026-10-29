import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import LiasseSheet, { type Worksheet } from "./LiasseSheet";

function sheet(partial: Partial<Worksheet>): Worksheet {
  return {
    transmission: false,
    disclaimer: "Aucun envoi n’est effectué par SoloLMNP.",
    personal_return: { form: "2042-C-PRO", status: "case_not_verified" },
    liasse: { form: "2033-B", vintage: "2025", fields: [] },
    ...partial,
  };
}

test("a research sheet never says it is ready to copy", () => {
  render(
    <LiasseSheet
      yearId={1}
      worksheet={sheet({
        output_status: "recherche",
        output_label: "Recherche",
        declarable: true,
        disclaimer: "Sortie de recherche. Ne recopiez pas ces montants.",
      })}
    />,
  );
  const banner = screen.getByText("Recherche").closest("p");
  expect(banner).toHaveAttribute("data-output-status", "recherche");
  expect(screen.queryByText(/Prête à recopier/)).not.toBeInTheDocument();
  expect(screen.getByText(/ne les recopiez pas/)).toBeInTheDocument();
});

test("a provisional sheet stays short of ready to copy", () => {
  render(
    <LiasseSheet
      yearId={1}
      worksheet={sheet({
        output_status: "provisoire",
        output_label: "Provisoire",
        declarable: false,
      })}
    />,
  );
  expect(screen.getByText("Provisoire").closest("p")).toHaveAttribute("data-output-status", "provisoire");
  expect(screen.queryByText(/Prête à recopier/)).not.toBeInTheDocument();
});

test("only a declarable sheet says it is ready to copy", () => {
  render(
    <LiasseSheet
      yearId={1}
      worksheet={sheet({
        output_status: "declarable",
        output_label: "Déclarable",
        declarable: true,
        disclaimer: "Feuille prête à recopier dans votre espace professionnel.",
      })}
    />,
  );
  expect(screen.getByText(/Prête à recopier/)).toBeInTheDocument();
  expect(screen.getByText(/Déclarable/).closest("p")).toHaveAttribute("data-output-status", "declarable");
  expect(screen.getByText(/Recopiez ces montants/)).toBeInTheDocument();
});
