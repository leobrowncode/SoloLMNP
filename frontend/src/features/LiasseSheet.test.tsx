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

test("the declaration sheet explains amounts and blocks uncertain boxes", () => {
  render(
    <LiasseSheet
      worksheet={sheet({
        output_status: "recherche",
        output_label: "Recherche",
        declaration: {
          marker: "document de travail, à vérifier",
          status: "research_only",
          vintage: "2025",
          rules_version: "research-2",
          explanations: [
            {
              code: "accounting_result",
              label: "Résultat comptable",
              amount: "920.00",
              formula: "produits − charges",
              rules: [{ id: "RULE-RESULT-001", source: "CGI", source_url: "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006309312" }],
              entries: [{
                id: 7,
                accounting_date: "2025-06-01",
                journal_code: "VT",
                piece_reference: "L1",
                label: "Loyer juin",
                accounts: ["706000"],
              }],
            },
          ],
          efi_rows: [
            {
              code: "RENTS",
              form: "2033-B-SD",
              case: "217",
              case_status: "verified",
              label: "Loyers",
              amount: "1000.00",
              formula: "somme des comptes 70",
              rules: [],
              source_url: "https://www.impots.gouv.fr/formulaire/2033-sd/impot-sur-le-revenu",
              source_label: "Liasse 2033",
              entries: [],
            },
            {
              code: "LMNP",
              form: "2031-SD",
              case: null,
              case_status: "unnumbered",
              label: "BIC non professionnels",
              amount: "920.00",
              formula: "résultat fiscal",
              rules: [],
              entries: [],
            },
            {
              code: "FUTURE",
              form: "2033-B-SD",
              case: null,
              case_status: "blocked",
              block_reason: "Numéro non publié pour ce millésime.",
              label: "Case non publiée",
              amount: "1.00",
              formula: "bloquée",
              rules: [],
              entries: [],
            },
          ],
        },
        personal_return: {
          form: "2042-C-PRO",
          status: "verified",
          cerfa: "11222*28",
          form_millesime: "2026",
          lines: [
            { code: "benefit", case: "5NA", case_status: "verified", served: true, label: "Bénéfice", amount: "920.00" },
            { code: "deficit", case: "5NY", case_status: "verified", served: false, label: "Déficit", amount: "0.00" },
          ],
          deficit_usage: [{
            origin_year: 2024,
            opening: "150.00",
            used: "150.00",
            remaining_after: "0.00",
            case: "5GJ",
            case_status: "verified",
          }],
          blocked_cases: [{ case: "5NK", reason: "Micro-BIC, pas le réel." }, { case: "5NZ", reason: "Absente du formulaire." }],
          unfilled_cases: [{ case: "5OA", reason: "Déclarant 2 inconnu." }],
          source: { title: "2042-C-PRO", pdf_url: "https://www.impots.gouv.fr/sites/default/files/formulaires/2042/2026/2042_5474.pdf" },
        },
      })}
    />,
  );
  expect(screen.getByText("document de travail, à vérifier")).toBeInTheDocument();
  expect(screen.getByText(/Saisie et envoi manuels uniquement/)).toBeInTheDocument();
  expect(screen.getByText(/Pas de scraping, pas d’EDI, pas de télétransmission/)).toBeInTheDocument();
  expect(screen.getByText(/produits − charges/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "RULE-RESULT-001" })).toHaveAttribute("href", expect.stringContaining("legifrance"));
  expect(screen.getByText(/Loyer juin/)).toBeInTheDocument();
  expect(screen.getByText("217")).toBeInTheDocument();
  expect(screen.getByText("non numérotée")).toBeInTheDocument();
  expect(screen.getAllByText("bloquée").length).toBeGreaterThan(0);
  expect(screen.queryByText("370")).not.toBeInTheDocument();
  expect(screen.getByText("5NA")).toBeInTheDocument();
  expect(screen.getByText("non servie")).toBeInTheDocument();
  expect(screen.getByText(/Ne pas utiliser la case 5NK/)).toBeInTheDocument();
  expect(screen.getByText(/Ne pas utiliser la case 5NZ/)).toBeInTheDocument();
  expect(screen.getByText("5GJ")).toBeInTheDocument();
  expect(screen.getByText(/Case 5OA non remplie/)).toBeInTheDocument();
  const banner = screen.getByText("document de travail, à vérifier").closest("p");
  expect(banner).toHaveAttribute("data-declaration-status", "research_only");
});
