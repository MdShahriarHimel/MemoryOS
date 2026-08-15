import { test, expect } from "@playwright/test";
import { seedMemory, waitForApi } from "./helpers";

test.describe("Memory flow", () => {
  test.beforeAll(async ({ request }) => {
    await waitForApi(request);
    await seedMemory(request, "E2E user prefers tea over coffee");
  });

  test("search returns seeded memory", async ({ page }) => {
    await page.goto("/memory-explorer");
    await page.getByLabel("Search query").fill("tea coffee");
    await page.getByRole("button", { name: "Search" }).click();

    await expect(page.getByText("E2E user prefers tea over coffee").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Retrieval trace")).toBeVisible();
  });
});

test.describe("Context builder", () => {
  test("builds context for a query", async ({ page, request }) => {
    await waitForApi(request);
    await page.goto("/context-builder");
    await page.getByPlaceholder(/what context does the agent need/i).fill("user drink preferences");
    await page.getByRole("button", { name: "Build" }).click();

    await expect(page.getByText("Memories (")).toBeVisible({ timeout: 15_000 });
  });
});
