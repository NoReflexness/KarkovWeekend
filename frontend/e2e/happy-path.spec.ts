import { test, expect } from "@playwright/test";

const ADMIN_EMAIL = process.env.ADMIN_EMAIL ?? "admin@karkov.example.com";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD ?? "change-me";

test("admin can log in and reach the home", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.getByLabel("Adgangskode").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: /Log ind/i }).click();

  await expect(page).toHaveURL(/\/$|\/arrangementer/);
  await expect(page.getByText(/Karkov Weekend/i)).toBeVisible();
});

test("login form rejects empty submission", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: /Log ind/i }).click();
  await expect(page.getByText(/Påkrævet|Ugyldig email/i).first()).toBeVisible();
});
