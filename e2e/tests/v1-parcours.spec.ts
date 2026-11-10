import { expect, test } from "@playwright/test";

const SHOTS = process.env.SOLOLMNP_V1_SHOTS === "1";

test.describe("parcours v1 golden", () => {
  test("ouvre les cinq écrans sur un dossier de référence", async ({ page }) => {
    await page.goto("/v1/dossier");
    await expect(page.getByRole("heading", { name: "Saisie LMNP réel simplifié" })).toBeVisible();
    if (SHOTS) await page.screenshot({ path: "/opt/cursor/artifacts/v1-ecran-dossier.png", fullPage: true });

    await page.getByRole("button", { name: "Copier pour travailler" }).first().click();
    await expect(page.getByLabel("Nom du dossier")).not.toHaveValue("", { timeout: 15_000 });
    await page.getByLabel("SIRET").fill("12345678900015");

    await page.getByRole("button", { name: "Enregistrer et continuer" }).click();
    await expect(page.getByRole("heading", { name: /2\. Bien/ })).toBeVisible();
    if (SHOTS) await page.screenshot({ path: "/opt/cursor/artifacts/v1-ecran-bien.png", fullPage: true });
    await page.getByRole("button", { name: "Enregistrer et continuer" }).click();

    await expect(page.getByRole("heading", { name: /3\. Année/ })).toBeVisible({ timeout: 15_000 });
    if (SHOTS) await page.screenshot({ path: "/opt/cursor/artifacts/v1-ecran-annee.png", fullPage: true });
    await page.getByRole("button", { name: "Enregistrer et passer à la revue" }).click();

    await expect(page.getByRole("heading", { name: /4\. Revue fiscale/ })).toBeVisible({ timeout: 20_000 });
    if (SHOTS) await page.screenshot({ path: "/opt/cursor/artifacts/v1-ecran-revue.png", fullPage: true });
    await page.getByRole("checkbox", { name: "Notice relue" }).check();
    await page.getByRole("button", { name: "Valider et ouvrir les sorties" }).click();

    await expect(page.getByRole("heading", { name: /5\. Sorties/ })).toBeVisible({ timeout: 20_000 });
    if (SHOTS) await page.screenshot({ path: "/opt/cursor/artifacts/v1-ecran-sorties.png", fullPage: true });
    await expect(page.getByRole("button", { name: "Copier" }).first()).toBeVisible();
    await expect(page.getByText("2033-A").first()).toBeVisible();
  });
});
