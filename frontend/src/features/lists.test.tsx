import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { enumChoices } from "../lib/format";
import { BrowsableList } from "./BrowsableList";
import ScreenStatus from "./ScreenStatus";
import { emptyView, failLoad, idleView, beginLoad } from "./screenState";

interface Sample {
  label: string;
  status: "CALCULATED" | "POSTED";
  category: "FURNITURE" | "LAND" | "EQUIPMENT";
}

const items: Sample[] = [
  { label: "Canapé", status: "CALCULATED", category: "FURNITURE" },
  { label: "Parcelle", status: "POSTED", category: "LAND" },
  { label: "Four", status: "CALCULATED", category: "EQUIPMENT" },
];

function SampleList({ rows }: { rows: readonly Sample[] }) {
  return (
    <BrowsableList
      items={rows}
      searchLabel="Rechercher une immobilisation"
      text={(row) => row.label}
      statusOf={(row) => row.status}
      categoryOf={(row) => row.category}
      statusChoices={enumChoices("periodStatus")}
      categoryChoices={enumChoices("assetCategory")}
      emptyTitle="Aucune immobilisation."
      emptyReason="Le registre est vide tant qu’un bien n’est pas inscrit."
      emptyAction={{ label: "Inscrire une immobilisation", href: "#nouvelle-immobilisation" }}
      noResultsReason="Aucune immobilisation ne correspond à la recherche ou aux filtres."
      groupBy={(row) => row.category}
      groupTitle={(key) => enumChoices("assetCategory").find(([code]) => code === key)?.[1] ?? key}
    >
      {(rows) => (
        <ul aria-label="Registre filtré">
          {rows.map((row) => <li key={row.label}>{row.label}</li>)}
        </ul>
      )}
    </BrowsableList>
  );
}

describe("list empty, search and filters", () => {
  it("explains an empty list and offers the next action, never while loading or on error", () => {
    const { rerender } = render(
      <ScreenStatus
        state={beginLoad(idleView<Sample[]>(), false)}
        loading={<p>Chargement…</p>}
        empty={<SampleList rows={[]} />}
      />,
    );
    expect(screen.getByText("Chargement…")).toBeInTheDocument();
    expect(screen.queryByText("Aucune immobilisation.")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Inscrire une immobilisation" })).not.toBeInTheDocument();

    rerender(
      <ScreenStatus
        state={failLoad(idleView<Sample[]>(), { code: "HTTP_ERROR", message: "Lecture impossible" }, false)}
        onRetry={() => undefined}
        empty={<SampleList rows={[]} />}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Lecture impossible");
    expect(screen.queryByText("Aucune immobilisation.")).not.toBeInTheDocument();
    expect(screen.queryByText("Aucun résultat")).not.toBeInTheDocument();

    rerender(<ScreenStatus state={emptyView<Sample[]>()} empty={<SampleList rows={[]} />} />);
    expect(screen.getByText("Aucune immobilisation.")).toBeInTheDocument();
    expect(screen.getByText(/Le registre est vide/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Inscrire une immobilisation" })).toHaveAttribute("href", "#nouvelle-immobilisation");
    expect(screen.queryByLabelText("Rechercher une immobilisation")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Réinitialiser les filtres" })).not.toBeInTheDocument();
  });

  it("shows no results for a search miss and restores the list when filters reset", async () => {
    const user = userEvent.setup();
    render(<SampleList rows={items} />);
    expect(screen.getByText("Canapé")).toBeInTheDocument();
    expect(document.querySelector(".list-group-title")).toHaveTextContent("Mobilier");

    await user.type(screen.getByLabelText("Rechercher une immobilisation"), "zzz");
    expect(screen.getByText("Aucun résultat")).toBeInTheDocument();
    expect(screen.getByText("Aucune immobilisation ne correspond à la recherche ou aux filtres.")).toBeInTheDocument();
    expect(screen.queryByText("Aucune immobilisation.")).not.toBeInTheDocument();
    expect(screen.queryByText("Canapé")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Réinitialiser les filtres" }));
    expect(screen.getByText("Canapé")).toBeInTheDocument();
    expect(screen.getByText("Parcelle")).toBeInTheDocument();
    expect(screen.queryByText("Aucun résultat")).not.toBeInTheDocument();
  });

  it("filters by status and category from the shared labels", async () => {
    const user = userEvent.setup();
    render(<SampleList rows={items} />);
    await user.selectOptions(screen.getByRole("combobox", { name: "Filtrer par statut" }), "POSTED");
    expect(screen.getByText("Parcelle")).toBeInTheDocument();
    expect(screen.queryByText("Canapé")).not.toBeInTheDocument();
    expect(screen.queryByText("Four")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByRole("combobox", { name: "Filtrer par catégorie" }), "FURNITURE");
    expect(screen.getByText("Aucun résultat")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Réinitialiser les filtres" }));
    expect(screen.getByText("Four")).toBeInTheDocument();

    await user.selectOptions(screen.getByRole("combobox", { name: "Filtrer par catégorie" }), "EQUIPMENT");
    expect(screen.getByText("Four")).toBeInTheDocument();
    expect(screen.queryByText("Parcelle")).not.toBeInTheDocument();
  });
});
