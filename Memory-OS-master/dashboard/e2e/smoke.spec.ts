import { test, expect } from "@playwright/test";

const PAGES: { path: string; title: string | RegExp }[] = [
  { path: "/dashboard", title: /memory infrastructure/i },
  { path: "/memory-explorer", title: "Memory Explorer" },
  { path: "/context-builder", title: "Context Builder" },
  { path: "/sessions", title: "Sessions" },
  { path: "/system-health", title: "System Health" },
  { path: "/reflection", title: "Reflection" },
  { path: "/analytics", title: "Analytics" },
  { path: "/developer", title: "Developer Portal" },
];

test.describe("Smoke — page loads", () => {
  for (const { path, title } of PAGES) {
    test(`${path} renders`, async ({ page }) => {
      await page.goto(path);
      const heading = page.getByRole("heading", { level: 1 });
      if (title instanceof RegExp) {
        await expect(heading).toHaveText(title, { timeout: 15_000 });
      } else {
        await expect(heading).toContainText(title, { timeout: 15_000 });
      }
    });
  }

  test("login page renders", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
    await page.getByRole("button", { name: /^register$/i }).click();
    await expect(page.getByRole("button", { name: /create account/i })).toBeVisible();
  });
});

test.describe("Smoke — sidebar navigation", () => {
  test("navigate from dashboard to memory explorer", async ({ page }) => {
    await page.goto("/dashboard");
    await page.getByRole("link", { name: "Memory Explorer" }).click();
    await expect(page).toHaveURL(/memory-explorer/);
    await expect(page.getByRole("heading", { name: "Memory Explorer" })).toBeVisible();
  });
});
