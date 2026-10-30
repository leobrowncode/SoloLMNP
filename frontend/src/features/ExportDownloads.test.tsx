import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import ExportDownloads from "./ExportDownloads";
import type { ExportStatus } from "./exportStatus";

afterEach(() => vi.restoreAllMocks());

function slot(posture: "provisoire" | "bloquee" | "finale") {
  const label = posture === "finale" ? "Finale" : posture === "provisoire" ? "Provisoire" : "Bloquée";
  return { posture, label, download: posture !== "bloquee" };
}

function status(options: {
  liasse: "provisoire" | "bloquee" | "finale";
  fec: "provisoire" | "bloquee" | "finale";
  prerequisites?: ExportStatus["prerequisites"];
}): ExportStatus {
  const liasse = slot(options.liasse);
  const fec = slot(options.fec);
  return {
    exports: { liasse, pdf: liasse, fec, archive: fec },
    prerequisites: options.prerequisites ?? [],
  };
}

function renderExports(value: ExportStatus) {
  return render(
    <MemoryRouter>
      <ExportDownloads yearId={1} status={value} />
    </MemoryRouter>,
  );
}

test("before calculation every output is blocked and lists what is missing", () => {
  renderExports(status({
    liasse: "bloquee",
    fec: "bloquee",
    prerequisites: [
      {
        code: "FISCAL_NOT_COMPUTED",
        message: "Calculez le résultat fiscal avant de télécharger la liasse ou le PDF.",
        export: "liasse",
        action: { label: "Calculer la fiscalité", href: "/fiscalite#calcul-fiscal" },
      },
      {
        code: "YEAR_NOT_CLOSED",
        message: "Le FEC final et le dossier de contrôle exigent un exercice clôturé.",
        export: "fec",
        action: { label: "Clôturer l’exercice", href: "/fiscalite#close-title" },
      },
    ],
  }));
  for (const kind of ["liasse", "pdf", "fec", "archive"]) {
    expect(document.querySelector(`[data-export="${kind}"]`)).toHaveAttribute("data-posture", "bloquee");
  }
  expect(screen.getAllByText("Bloquée").length).toBe(4);
  expect(screen.getByRole("button", { name: "Télécharger le PDF de recopie" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Télécharger le FEC" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Télécharger le dossier de contrôle" })).toBeDisabled();
  expect(screen.getAllByText(/Calculez le résultat fiscal/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/exigent un exercice clôturé/).length).toBeGreaterThan(0);
  expect(screen.getAllByRole("link", { name: "Calculer la fiscalité" })[0]).toHaveAttribute(
    "href",
    "/fiscalite#calcul-fiscal",
  );
  expect(document.querySelector('a[href*="/api/filing"]')).toBeNull();
});

test("before closure the liasse stays provisional and the final FEC stays blocked", () => {
  renderExports(status({
    liasse: "provisoire",
    fec: "bloquee",
    prerequisites: [{
      code: "YEAR_NOT_CLOSED",
      message: "Le FEC final et le dossier de contrôle exigent un exercice clôturé.",
      export: "fec",
      action: { label: "Clôturer l’exercice", href: "/fiscalite#close-title" },
    }],
  }));
  expect(document.querySelector('[data-export="pdf"]')).toHaveAttribute("data-posture", "provisoire");
  expect(screen.getAllByText("Provisoire").length).toBeGreaterThan(0);
  expect(screen.getAllByText(/pas une sortie finale/).length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: "Télécharger le PDF de recopie" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Télécharger le FEC" })).toBeDisabled();
  expect(document.querySelector('[data-export="archive"]')).toHaveAttribute("data-posture", "bloquee");
});

test("a blocked liasse shows the missing prerequisite instead of a file link", () => {
  renderExports(status({
    liasse: "bloquee",
    fec: "bloquee",
    prerequisites: [
      {
        code: "SIREN_MANQUANT",
        message: "Indiquez le SIREN de l’activité.",
        export: "liasse",
        action: { label: "Renseigner le SIREN", href: "/comptabilite/brouillons#identite-liasse" },
      },
      {
        code: "YEAR_NOT_CLOSED",
        message: "Le FEC final et le dossier de contrôle exigent un exercice clôturé.",
        export: "fec",
        action: { label: "Clôturer l’exercice", href: "/fiscalite#close-title" },
      },
    ],
  }));
  expect(screen.getAllByText("Indiquez le SIREN de l’activité.").length).toBeGreaterThan(0);
  expect(screen.getAllByRole("link", { name: "Renseigner le SIREN" })[0]).toHaveAttribute(
    "href",
    "/comptabilite/brouillons#identite-liasse",
  );
  expect(screen.getByRole("button", { name: "Télécharger le PDF de recopie" })).toBeDisabled();
});

test("a final FEC and control file can be downloaded, and a refusal stays on the page", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/fec")) {
      return new Response(JSON.stringify({
        detail: {
          code: "YEAR_NOT_CLOSED",
          message: "Le FEC final et le dossier de contrôle exigent un exercice clôturé.",
          action: { label: "Clôturer l’exercice", href: "/fiscalite#close-title" },
          issues: [
            { code: "YEAR_NOT_CLOSED", message: "Exercice encore ouvert." },
            { code: "FEC_INVALID", message: "En-tête FEC absent." },
          ],
        },
      }), { status: 409, headers: { "Content-Type": "application/json" } });
    }
    return new Response(new Uint8Array([1, 2, 3]), {
      status: 200,
      headers: { "Content-Disposition": 'attachment; filename="liasse-2025.pdf"' },
    });
  });
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn(() => "blob:liasse"),
    revokeObjectURL: vi.fn(),
  });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

  renderExports(status({ liasse: "finale", fec: "finale" }));
  expect(document.querySelector('[data-export="fec"]')).toHaveAttribute("data-posture", "finale");
  expect(document.querySelector('[data-export="archive"]')).toHaveAttribute("data-posture", "finale");
  expect(screen.getAllByText("Finale").length).toBe(4);
  expect(screen.getByRole("button", { name: "Télécharger le FEC" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Télécharger le dossier de contrôle" })).toBeEnabled();

  fireEvent.click(screen.getByRole("button", { name: "Télécharger le PDF de recopie" }));
  await waitFor(() => expect(click).toHaveBeenCalled());
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/filing/years/1/efi.pdf",
    expect.objectContaining({ method: "GET" }),
  );

  fireEvent.click(screen.getByRole("button", { name: "Télécharger le FEC" }));
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("exigent un exercice clôturé");
  expect(alert).toHaveTextContent("Exercice encore ouvert.");
  expect(alert).toHaveTextContent("En-tête FEC absent.");
  expect(screen.getByRole("link", { name: "Clôturer l’exercice" })).toHaveAttribute(
    "href",
    "/fiscalite#close-title",
  );
  expect(document.querySelector('a[href="/api/filing/years/1/fec"]')).toBeNull();
});
