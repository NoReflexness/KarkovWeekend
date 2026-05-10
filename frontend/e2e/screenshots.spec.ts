import { test, expect } from "@playwright/test";

const ADMIN_EMAIL = process.env.ADMIN_EMAIL ?? "admin@karkov.example.com";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD ?? "change-me";

const viewports = [
  { name: "mobile", width: 390, height: 844 },
  { name: "tablet", width: 820, height: 1180 },
  { name: "desktop", width: 1440, height: 900 },
];

for (const vp of viewports) {
  test(`renders home on ${vp.name}`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto("/login");
    await page.getByLabel("Email").fill(ADMIN_EMAIL);
    await page.getByLabel("Adgangskode").fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: /Log ind/i }).click();
    await page.waitForURL(/\/$/);
    await expect(page.getByText(/Karkov Weekend/i)).toBeVisible();
    // Allow react-query to finish + images to settle.
    await page.waitForLoadState("networkidle");
    await page.screenshot({
      path: `./e2e/__screens__/home-${vp.name}.png`,
      fullPage: true,
    });

    await page.goto("/arrangementer");
    await page.waitForLoadState("networkidle");
    await page.screenshot({
      path: `./e2e/__screens__/events-${vp.name}.png`,
      fullPage: true,
    });
  });
}
