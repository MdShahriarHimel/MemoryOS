import { expect, test } from "@playwright/test";

// API-key creation reveals the secret exactly once.
test("creating an API key reveals a one-time secret", async ({ page }) => {
  await page.goto("/api-keys");
  await page.getByPlaceholder("e.g. production-agent").fill("e2e-key");
  await Promise.all([
    page.waitForResponse((r) => r.url().includes("/v1/api-keys") && r.request().method() === "POST"),
    page.getByRole("button", { name: "Create key" }).click(),
  ]);
  await expect(page.getByText(/shown again/i)).toBeVisible({ timeout: 15_000 });
});
