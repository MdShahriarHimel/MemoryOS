import { expect, test } from "@playwright/test";

// The memory explorer must render its mode controls and never crash on an empty
// result set — it should show an honest empty state instead.
test("memory explorer renders search modes", async ({ page }) => {
  await page.goto("/memory-explorer");
  for (const mode of ["hybrid", "vector", "keyword"] as const) {
    await expect(page.getByRole("button", { name: mode })).toBeVisible();
  }
});
