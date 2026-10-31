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

const consoleProblems = new WeakMap<Page, string[]>();

function installConsoleGuard(page: Page) {
  const problems: string[] = [];
  consoleProblems.set(page, problems);
  page.on("console", (message) => {
    const text = message.text();
    if (/same key|Encountered two children with the same key/i.test(text)) problems.push(text);
  });
  page.on("pageerror", (error) => {
    if (/same key/i.test(error.message)) problems.push(error.message);
  });
  page.on("response", (response) => {
    if (response.status() !== 404) return;
    if (/favicon|apple-touch-icon/i.test(response.url())) return;
    problems.push(`404 ${response.url()}`);
  });
}

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
  test.beforeEach(async ({ page }) => {
    installConsoleGuard(page);
  });

  test.afterEach(async ({ page }) => {
    expect(consoleProblems.get(page) ?? []).toEqual([]);
  });

  test("vue d’ensemble compacte : une action, aides lisibles", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: "Vue d’ensemble" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Continuer" })).toHaveCount(1);
    await expect(page.locator(".topbar")).not.toContainText("Continuer");
    await expect(page.locator(".topbar")).not.toContainText("Progression");
    await expect(page.getByRole("region", { name: "Progression du dossier" })).toBeVisible();
    await expect(page.getByText("L’activité n’est pas créée.")).toHaveCount(1);
    await expect(page.getByText("Aucun événement utile pour l’instant.")).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Créer l’activité" })).toHaveCount(0);
    const labels = await page.locator("button.help-tip-btn").allTextContents();
    expect(labels.length).toBeGreaterThan(0);
    for (const label of labels) expect(label.trim()).not.toBe("?");
    await expect(page.getByRole("button", { name: "Aide : LMNP" })).toHaveText("LMNP");
    await expect(page.getByRole("button", { name: "Aide : Liasse" }).first()).toHaveText("Liasse");
    await expect(page.getByRole("button", { name: "Aide : FEC" }).first()).toHaveText("FEC");
    await page.screenshot({ path: test.info().outputPath("overview-1280.png") });

    await page.setViewportSize({ width: 390, height: 800 });
    const title = page.getByRole("heading", { level: 1, name: "Vue d’ensemble" });
    await expect(title).toBeVisible();
    const titleBox = await title.boundingBox();
    expect(titleBox).toBeTruthy();
    expect(titleBox!.y).toBeGreaterThanOrEqual(0);
    expect(titleBox!.y + titleBox!.height).toBeLessThanOrEqual(800);
    const welcome = page.getByRole("heading", { name: /De l’écriture/ });
    await expect(welcome).toBeVisible();
    const welcomeBox = await welcome.boundingBox();
    expect(welcomeBox).toBeTruthy();
    expect(welcomeBox!.y).toBeLessThan(800);
    const topbar = await page.locator(".topbar").boundingBox();
    expect(topbar).toBeTruthy();
    expect(topbar!.height).toBeLessThan(120);
    const fold = page.locator("details.dossier-fold");
    await expect(fold).toBeVisible();
    await expect(fold).not.toHaveAttribute("open");
    await expect(fold.locator("summary")).toHaveText("Statut et progression");
    await expect(page.getByRole("region", { name: "Progression du dossier" })).toBeHidden();
    await expect(page.getByRole("link", { name: "Continuer" })).toHaveCount(1);
    await page.screenshot({ path: test.info().outputPath("overview-390.png") });

    await page.goto("/comptabilite/brouillons");
    const ledgerTitle = page.getByRole("heading", { level: 1, name: "Comptabilité" });
    await expect(ledgerTitle).toBeVisible();
    await expect(page.getByRole("link", { name: "Continuer" })).toHaveCount(0);
    await expect(page.getByText("Statut dossier", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Progression du dossier" })).toHaveCount(0);
    const ledgerBox = await ledgerTitle.boundingBox();
    expect(ledgerBox).toBeTruthy();
    expect(ledgerBox!.y + ledgerBox!.height).toBeLessThanOrEqual(800);
    await page.screenshot({ path: test.info().outputPath("ledger-390.png") });

    await page.setViewportSize({ width: 1280, height: 800 });
  });

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
    await expect(page.locator(".date-placeholder").first()).toHaveText("JJ/MM/AAAA");
    await expect(page.getByLabel(/Prix constaté au m²/)).toHaveValue("");
    await page.getByLabel("Nom du bien").fill("Studio fictif");
    await page.getByLabel("Adresse").fill("1 rue des Scénarios");
    await page.getByLabel(/Date d’acquisition/).fill("2025-01-01");
    await page.getByLabel(/Début de location/).fill("2025-02-01");
    await fillMoney(page, /Prix d’acquisition/, "100000,00");
    await fillMoney(page, /Frais de notaire/, "0,00");
    await fillMoney(page, /Valeur du terrain/, "20000,00");
    await fillMoney(page, /Valeur du bâtiment/, "70000,00");
    await expect(page.getByText(/de moins que le prix d’acquisition/)).toBeVisible();
    await page.getByRole("button", { name: "Vérifier avant enregistrement" }).click();
    await expect(page.getByText("Vérifiez les informations avant de confirmer.")).toHaveCount(0);
    await fillMoney(page, /Valeur du bâtiment/, "80000,00");
    await expect(page.getByText(/de moins que le prix d’acquisition/)).toHaveCount(0);
    await confirmReview(page);
    await expect(page.getByRole("heading", { name: "Studio fictif" })).toBeVisible();

    await page.goto("/operations/transactions");
    await page.getByText("Importer depuis Google Sheets ou un CSV").click();
    await page.locator("#import-operations").fill(CSV);
    await expect(page.getByText("Choisissez le compte bancaire des lignes déjà payées.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Prévisualiser les justificatifs" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Comptabiliser les justificatifs" })).toHaveCount(0);

    await page.goto("/operations/banque");
    await page.getByRole("button", { name: "Ajouter un compte bancaire" }).click();
    await page.getByLabel("Nom du compte bancaire").fill("Compte fictif");
    await page.getByLabel(/Compte comptable dédié/).selectOption("512000");
    await confirmReview(page);
    await expect(page.getByRole("heading", { name: "Compte fictif" })).toBeVisible();

    await page.goto("/operations/transactions");
    await expect(page.getByLabel("Compte des lignes payées")).toBeVisible();
    await page.getByText("Importer depuis Google Sheets ou un CSV").click();
    const rejected = [
      "Nature;Date;Date de la pièce;Type;Tiers;Montant;Libellé;Référence de pièce;Justificatif;Déjà payée",
      "Recette;15/03/2025;15/03/2025;LOY;Dupont;800,00;Loyer mars fictif;LOY-2025-03;bail.pdf;oui",
      "Dépense;99/99/2025;99/99/2025;ASS;Assureur;100,00;Date impossible;ASS-BAD;pno.pdf;non",
    ].join("\n");
    await page.locator("#import-operations").fill(rejected);
    await page.getByRole("button", { name: "Prévisualiser les justificatifs" }).click();
    await expect(page.getByText("2 lignes : 1 valide, 1 rejet.")).toBeVisible();
    const rejects = page.getByRole("list", { name: "Lignes rejetées" });
    await expect(rejects).toContainText("Date");
    const post = page.getByRole("button", { name: "Comptabiliser les justificatifs" });
    await expect(post).toBeDisabled();
    const partial = page.getByRole("button", { name: "Importer uniquement la ligne valide" });
    await expect(partial).toBeDisabled();
    await page.getByRole("radio", { name: "Importer uniquement la ligne valide" }).check();
    await expect(partial).toBeEnabled();
    await expect(post).toBeDisabled();
    for (const width of [1280, 390]) {
      await page.setViewportSize({ width, height: 800 });
      const box = await rejects.boundingBox();
      expect(box).toBeTruthy();
      expect(box!.x).toBeGreaterThanOrEqual(0);
      expect(box!.x + box!.width).toBeLessThanOrEqual(width + 1);
      const panel = page.locator("#import-import-operations");
      const overflow = await panel.evaluate((node) => node.scrollWidth - node.clientWidth);
      expect(overflow).toBeLessThanOrEqual(1);
    }
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.locator("#import-operations").fill(CSV);
    await page.getByRole("button", { name: "Prévisualiser les justificatifs" }).click();
    await expect(page.getByText("2 lignes : 2 valides.")).toBeVisible();
    await page.getByRole("button", { name: "Comptabiliser les justificatifs" }).click();
    await expect(page.getByText("2 lignes comptabilisées.")).toBeVisible();
    await expect(page.getByRole("heading", { name: /Loyer mars fictif/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Assurance PNO fictive/ })).toBeVisible();

    await page.goto("/immobilisations");
    await page.getByRole("button", { name: "Prévisualiser l’amortissement du logement" }).click();
    await page.getByRole("button", { name: "Créer les immobilisations affichées" }).click();
    await expect(page.getByRole("heading", { name: /Construction — Studio fictif/ })).toBeVisible();
    const desktop = page.viewportSize();
    expect(desktop?.width).toBe(1280);
    await page.evaluate(() => window.scrollTo(0, 0));
    for (const name of [
      "Faire entrer le bien en comptabilité",
      "Calculer les périodes",
      "Comptabiliser toutes les dotations",
    ]) {
      const box = await page.getByRole("button", { name }).boundingBox();
      expect(box, name).toBeTruthy();
      expect(box!.y + box!.height, name).toBeLessThanOrEqual(desktop!.height);
    }
    const sharedDuration = "Durée d’usage proposée pour un logement en location longue durée, à confirmer selon l’état du bien et les travaux. Ce n’est pas un barème légal.";
    await expect(page.getByText(sharedDuration)).toHaveCount(1);
    await page.getByText("Détail et aides").click();
    await expect(page.getByText(sharedDuration)).toBeVisible();
    await page.setViewportSize({ width: 390, height: desktop!.height });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    await expect(page.getByText(sharedDuration)).toHaveCount(1);
    await page.setViewportSize({ width: desktop!.width, height: desktop!.height });
    await page.getByRole("button", { name: "Calculer les périodes" }).click();
    await expect(page.getByText(/période\(s\) calculée/)).toBeVisible();
    const postDotations = page.getByRole("button", { name: "Comptabiliser toutes les dotations" });
    await expect(postDotations).toBeDisabled();
    await expect(page.getByRole("link", { name: "Faire entrer le bien en comptabilité" })).toBeVisible();
    await page.getByRole("button", { name: "Faire entrer le bien en comptabilité" }).click();
    const entryForm = page.locator("section.property-entry");
    await entryForm.getByRole("button", { name: "Prévisualiser l’écriture" }).click();
    const bookEntry = entryForm.getByRole("button", { name: "Comptabiliser", exact: true });
    await expect(bookEntry).toBeEnabled();
    await bookEntry.click();
    await expect(page.getByText(/Bien entré en comptabilité/)).toBeVisible();
    await expect(postDotations).toBeEnabled();
    await postDotations.click();
    await expect(page.getByText(/dotations comptabilisées, total/)).toBeVisible();
    await expect(page.locator("#actions-dotations").getByRole("link", { name: "Voir le journal" })).toBeVisible();

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

  test("un emprunt non comptabilisé n’affiche pas un solde nul", async ({ page }) => {
    await page.goto("/operations/emprunts");
    await page.getByRole("button", { name: "Ajouter un emprunt" }).click();
    await page.getByLabel("Prêteur").fill("Crédit Habitat fictif");
    await page.getByLabel(/Début de l’emprunt/).fill("2026-01-01");
    await fillMoney(page, /Capital de cette ligne/, "10000,00");
    await fillMoney(page, /Taux annuel/, "3,50");
    await page.getByLabel(/Durée en mois/).fill("120");
    await confirmReview(page);

    const card = page.locator("#emprunts-saisie article").filter({ hasText: "Crédit Habitat fictif" });
    await expect(card).toContainText("Pas encore au bilan");
    await expect(card).toContainText("Capital emprunté (contrat)");
    await expect(card).not.toContainText("Solde comptable : 0,00");
    const notice = page.getByRole("status").filter({ hasText: "Crédit Habitat fictif" });
    await expect(notice).toContainText("compte 164");
    await expect(notice).not.toContainText("Saisir une échéance");
    await expect(page.getByRole("link", { name: "Enregistrer le déblocage" })).toBeVisible();
    await expect(page.getByText("Importer les échéances depuis Google Sheets ou un CSV")).toHaveCount(0);

    await page.getByRole("button", { name: "Saisir une échéance" }).click();
    await page.getByLabel("Date comptable").fill("2026-02-01");
    await page.getByLabel("Référence justificative").fill("ECH-FICTIF");
    await fillMoney(page, "Intérêts (€)", "10,00");
    await page.getByRole("button", { name: "Vérifier avant enregistrement" }).click();
    await expect(page.getByRole("button", { name: "Confirmer l’enregistrement" })).toBeDisabled();
    await expect(page.locator("form .ledger-error")).toContainText(
      "Aucun capital comptable à rembourser pour cet emprunt.",
    );
    await page.getByRole("button", { name: "Annuler" }).click();

    await page.getByRole("button", { name: "Enregistrer le déblocage" }).click();
    await page.getByLabel("Date comptable").fill("2026-02-01");
    await page.getByLabel("Référence justificative").fill("DEBLOC-FICTIF");
    await confirmReview(page);
    await expect(card).toContainText("Solde comptable");
    await expect(card).not.toContainText("Pas encore au bilan");
    await expect(page.getByText("Importer les échéances depuis Google Sheets ou un CSV")).toBeVisible();
    await page.getByRole("button", { name: "Saisir une échéance" }).click();
    await page.getByLabel("Date comptable").fill("2026-03-01");
    await page.getByLabel("Référence justificative").fill("ECH-FICTIF-2");
    await page.getByRole("button", { name: "Vérifier avant enregistrement" }).click();
    await expect(page.getByRole("button", { name: "Confirmer l’enregistrement" })).toBeEnabled();
  });
});
