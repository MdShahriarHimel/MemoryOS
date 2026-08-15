import { expect, test } from "@playwright/test";

// Registration + login flow. Uses a unique email per run so it is idempotent.
test("user can register and reach the dashboard", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;

  await page.goto("/login");
  await page.getByRole("button", { name: "register" }).click();
  await page.getByPlaceholder("Acme Inc.").fill("E2E Org");
  await page.getByPlaceholder("you@company.com").fill(email);
  await page.getByPlaceholder("••••••••").fill("password123");

  await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes("/api/auth/register") && r.status() === 200,
      { timeout: 30_000 },
    ),
    page.getByRole("button", { name: "Create account" }).click(),
  ]);

  await expect(page).toHaveURL(/\/dashboard/, { timeout: 30_000 });
});

test("login form validates empty submit", async ({ page }) => {
  await page.goto("/login");
  const email = page.getByPlaceholder("you@company.com");
  await expect(email).toHaveAttribute("required", "");
});
