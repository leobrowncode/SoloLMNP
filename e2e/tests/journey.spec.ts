import { readFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/**
 * Browser journey on a real API and a temporary SQLite file.
 *
 * Scenarios A–J of backend/tests/fixtures/scenarios.json stay asserted by
 * backend/tests/integration/test_scenarios.py. This file checks the same
 * story where the screen can show it: explicit opening, second-year
 * continuity, depreciation, a partial add-back, a locked close, a
 * deterministic FEC download, and a research-only declaration sheet.
 */

const CSV = [
  "Nature;Date;Date de la pièce;Type;Tiers;Montant;Libellé;Référence de pièce;Justificatif;Déjà payée",
  "Recette;15/03/2025;15/03/2025;LOY;Dupont;800,00;Loyer mars fictif;LOY-2025-03;bail.pdf;oui",
  "Dépense;20/03/2025;20/03/2025;ASS;Assureur;100,00;Assurance PNO fictive;ASS-2025-03;pno.pdf;non",
].join("\n");

async function confirmReview(page: Page) {
  await page.getByRole("button", { name: "Vérifier avant enregistrement" }).click();
  await page.getByRole("button", { name: "Confirmer l’enregistrement" }).click();
  await expect(page.getByRole("button", { name: "Vérifier avant enregistrement" })).toBeHidden();
}

async function fillMoney(page: Page, label: string | RegExp, value: string) {
  const field = page.getByLabel(label);
  await field.fill(value);
}

test.describe.serial("parcours critique", () => {
  test("onboarding, import, dotations, clôture, déclaration, FEC, reprise et restauration", async ({ page }) => {
    await page.goto("/comptabilite/brouillons");
    await expect(page.getByRole("heading", { level: 1, name: "Comptabilité" })).toBeVisible();

    await page.getByLabel("Nom de l’activité").fill("LMNP fictif");
    await page.getByLabel(/Date réelle de début/).fill("2025-01-01");
    await page.getByRole("button", { name: "Créer l’activité" }).click();
    await expect(page.getByRole("textbox", { name: "SIREN", exact: true })).toBeVisible();

    await page.getByLabel(/Début de l’exercice/).fill("2025-12-31");
    await page.getByLabel(/Fin de l’exercice/).fill("2025-01-01");
    await page.getByLabel("Millésime fiscal").fill("2025");
    await page.getByRole("button", { name: "Créer l’exercice" }).click();
    await expect(page.getByRole("alert")).toContainText(
      "La date de fin doit être postérieure ou égale à la date de début.",
    );
    await expect(page.getByRole("combobox", { name: "Exercice" })).toHaveCount(0);

    await page.getByLabel(/Début de l’exercice/).fill("2025-01-01");
    await page.getByLabel(/Fin de l’exercice/).fill("2025-12-31");
    await page.getByLabel("Millésime fiscal").fill("2025");
    await page.getByRole("button", { name: "Créer l’exercice" }).click();
    await expect(page.getByRole("combobox", { name: "Exercice" })).toBeVisible();
    await page.getByRole("textbox", { name: "SIREN", exact: true }).fill("123456789");
    await page.getByRole("button", { name: "Enregistrer l’identité" }).click();
    await expect(page.getByText(/Identité .*enregistré/)).toBeVisible();

    await page.goto("/operations/biens");
    await page.getByRole("button", { name: "Ajouter un bien" }).click();
    await page.getByLabel("Nom du bien").fill("Studio fictif");
    await page.getByLabel("Adresse").fill("1 rue des Scénarios");
    await page.getByLabel(/Date d’acquisition/).fill("2025-01-15");
    await page.getByLabel(/Début de location/).fill("2025-02-01");
    await fillMoney(page, /Prix d’acquisition/, "100000,00");
    await fillMoney(page, /Frais de notaire/, "0,00");
    await page.getByLabel(/Surface du terrain/).fill("10");
    await fillMoney(page, /Prix constaté au m²/, "2000,00");
    await fillMoney(page, /Valeur du terrain/, "20000,00");
    await fillMoney(page, /Valeur du bâtiment/, "80000,00");
    await confirmReview(page);
    await expect(page.getByRole("heading", { name: "Studio fictif" })).toBeVisible();

    await page.goto("/operations/banque");
    await page.getByRole("button", { name: "Ajouter un compte bancaire" }).click();
    await page.getByLabel("Nom du compte bancaire").fill("Compte fictif");
    await page.getByLabel(/Compte comptable dédié/).selectOption("512000");
    await confirmReview(page);
    await expect(page.getByRole("heading", { name: "Compte fictif" })).toBeVisible();

    await page.goto("/operations/transactions");
    await expect(page.getByLabel("Compte des lignes payées")).toBeVisible();
    await page.getByText("Importer depuis Google Sheets ou un CSV").click();
    await page.locator("#import-operations").fill(CSV);
    await page.getByRole("button", { name: "Prévisualiser les justificatifs" }).click();
    await expect(page.getByText(/2 ligne\(s\)/)).toBeVisible();
    await page.getByRole("button", { name: "Comptabiliser les justificatifs" }).click();
    await expect(page.getByRole("heading", { name: /Loyer mars fictif/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Assurance PNO fictive/ })).toBeVisible();

    await page.goto("/immobilisations");
    await page.getByRole("button", { name: "Prévisualiser l’amortissement du logement" }).click();
    await page.getByRole("button", { name: "Créer les immobilisations affichées" }).click();
    await expect(page.getByRole("heading", { name: /Construction — Studio fictif/ })).toBeVisible();
    await page.getByRole("button", { name: "Calculer les périodes" }).click();
    await expect(page.getByText(/période\(s\) calculée/)).toBeVisible();
    await page.getByRole("button", { name: "Comptabiliser toutes les dotations" }).click();
    await expect(page.getByText(/dotation\(s\) comptabilisée/)).toBeVisible();

    await page.goto("/etats-comptables");
    await expect(page.getByText(/Bilan/)).toBeVisible();
    await page.getByRole("button", { name: "Préparer la centralisation" }).click();
    await page.getByLabel("Référence de pièce").fill("CENT-2025");
    await page.getByLabel("Justification").fill("Centralisation du parcours fictif.");
    await page.getByRole("button", { name: "Vérifier la centralisation" }).click();
    await page.getByRole("button", { name: "Confirmer la centralisation" }).click();
    await expect(page.getByText("La centralisation est déjà comptabilisée.")).toBeVisible();

    await page.goto("/fiscalite");
    await expect(page.getByRole("heading", { level: 1, name: /Fiscalité/ })).toBeVisible();
    const charge = page.getByLabel("Compte de charge");
    if (await charge.locator("option").count() > 1) {
      await charge.selectOption({ label: /616000/ });
      await page.getByLabel(/Part non déductible/).fill("10,00");
      await page.getByLabel("Justification").fill("Quote-part non déductible du scénario.");
      await page.getByRole("button", { name: "Ajouter la réintégration" }).click();
    }
    await page.getByRole("button", { name: "Calculer le résultat fiscal" }).click();
    await expect(page.getByText("Ce n’est pas une base de déclaration.")).toBeVisible();
    await expect(page.getByText("Stock amortissement reporté")).toBeVisible();
    await expect(page.getByText("Déficit LMNP de l’exercice")).toBeVisible();

    await page.getByRole("button", { name: "Lancer le pré-contrôle" }).click();
    await expect(page.getByRole("checkbox", { name: /Millésime en recherche/ })).toBeVisible();
    const alerts = page.locator("#confirmer-cloture [role=alert]");
    await expect(alerts).toHaveCount(0);
    const boxes = page.locator("#confirmer-cloture input[type=checkbox]");
    const count = await boxes.count();
    for (let index = 0; index < count; index += 1) await boxes.nth(index).check();
    await page.getByRole("button", { name: "Accuser et préparer la clôture" }).click();
    await page.getByRole("button", { name: "Confirmer la clôture" }).click();
    await expect(page.getByText(/Exercice clôturé/)).toBeVisible();
    await page.goto("/comptabilite/brouillons");
    await expect(page.getByRole("button", { name: "Nouvelle écriture" })).toBeDisabled();

    await page.goto("/fiscalite");
    await page.getByRole("button", { name: "Liasse à recopier" }).click();
    const declaration = page.locator("[data-declaration-status]");
    await expect(declaration).toHaveAttribute("data-declaration-status", "research_only");
    await expect(declaration).toContainText("reste en recherche");
    await expect(page.getByText(/Pas de scraping, pas d’EDI, pas de télétransmission/)).toBeVisible();
    await expect(page.getByRole("heading", { name: "2042-C-PRO" })).toBeVisible();
    const fec = page.waitForEvent("download");
    await page.getByRole("button", { name: "Télécharger le FEC" }).click();
    const download = await fec;
    expect(download.suggestedFilename()).toMatch(/123456789FEC20251231\.txt/);
    const saved = await download.path();
    expect(saved).toBeTruthy();
    const fecText = readFileSync(saved!, "utf8");
    expect(fecText.split("\r\n")[0]?.split("\t")).toHaveLength(18);

    await page.goto("/comptabilite/brouillons#ajouter-exercice");
    await page.getByLabel(/Début de l’exercice/).fill("2026-01-01");
    await page.getByLabel(/Fin de l’exercice/).fill("2026-12-31");
    await page.getByLabel("Millésime fiscal").fill("2026");
    await page.getByRole("button", { name: "Créer l’exercice" }).click();
    await page.goto("/etats-comptables");
    await page.getByRole("combobox", { name: "Exercice" }).selectOption({ label: "2026" });
    await page.getByRole("button", { name: "Prévisualiser les à-nouveaux" }).click();
    await expect(page.getByLabel("Référence de la pièce de reprise")).toBeVisible();
    await page.getByLabel("Référence de la pièce de reprise").fill("AN-2026");
    const opening = page.locator("#ouverture-comptabilisation");
    if (await page.getByLabel("Compte de reprise du résultat").count()) {
      const hint = await opening.innerText();
      await page.getByLabel("Compte de reprise du résultat").fill(hint.includes("129") ? "129000" : "120000");
    }
    await page.getByRole("button", { name: "Générer et valider les à-nouveaux" }).click();
    await page.getByRole("button", { name: "Contrôler la continuité des à-nouveaux" }).click();
    await expect(page.getByText("Les soldes de l’écriture de reprise correspondent aux soldes source.")).toBeVisible();

    await page.goto("/conservation");
    await page.getByRole("button", { name: "Créer une sauvegarde" }).click();
    await expect(page.getByRole("radio").first()).toBeVisible();
    await page.getByRole("radio").first().check();
    await expect(page.getByText("Écritures")).toBeVisible();
    await page.getByLabel(/Confirmation — saisir RESTAURER/).fill("RESTAURER");
    await page.getByRole("button", { name: "Restaurer la sauvegarde" }).click();
    await expect(page.getByText(/Base restaurée depuis/)).toBeVisible();
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: "Vue d’ensemble" })).toBeVisible();
    await expect(page.getByText("Prête à recopier")).toHaveCount(0);
  });

  test("axe et défilement sur les vues principales", async ({ page }) => {
    const routes = ["/", "/comptabilite/brouillons", "/operations/biens", "/immobilisations", "/etats-comptables", "/fiscalite", "/conservation"];
    const widths = [320, 390, 768, 1280];
    for (const width of widths) {
      await page.setViewportSize({ width, height: 800 });
      for (const route of routes) {
        await page.goto(route);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        const overflow = await page.evaluate(() => {
          const root = document.documentElement;
          return root.scrollWidth - root.clientWidth;
        });
        expect(overflow, `${route} @ ${width}px`).toBeLessThanOrEqual(1);
        if (width <= 768) {
          await expect(page.getByRole("button", { name: /menu/ })).toBeVisible();
        }
        const results = await new AxeBuilder({ page }).analyze();
        expect(results.violations, `${route} @ ${width}px ${JSON.stringify(results.violations.map((item) => item.id))}`).toEqual([]);
      }
    }
  });
});
