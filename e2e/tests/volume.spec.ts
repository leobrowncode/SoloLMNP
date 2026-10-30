import { expect, test } from "@playwright/test";

/**
 * Page timings against a database seeded by scripts/bench_volume.py.
 * Excluded from the default Playwright run. The bench script sets
 * SOLOLMNP_VOLUME=1 and SOLOLMNP_E2E_DATABASE.
 */

const routes = [
  "/",
  "/comptabilite/journal",
  "/comptabilite/balance",
  "/operations/biens",
  "/immobilisations",
  "/etats-comptables",
  "/fiscalite",
];

test("temps d’affichage sur un volume réaliste", async ({ page }) => {
  test.setTimeout(180_000);
  for (const route of routes) {
    const started = Date.now();
    await page.goto(route);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const elapsed = Date.now() - started;
    console.log(`PAGE ${route} ${elapsed}`);
  }
});
