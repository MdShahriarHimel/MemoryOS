import { test, expect } from "@playwright/test";
import { API_URL, createSession, waitForApi } from "./helpers";

test.describe("Sessions and replay", () => {
  let sessionId: string;

  test.beforeAll(async ({ request }) => {
    await waitForApi(request);
    const session = await createSession(request);
    sessionId = session.id;

    const event = await request.post(`${API_URL}/v1/sessions/${sessionId}/events`, {
      data: {
        event_type: "request",
        detail: "E2E replay test event",
        latency_ms: 5,
      },
    });
    expect(event.ok()).toBeTruthy();
  });

  test("sessions list shows session with replay link", async ({ page }) => {
    await page.goto("/sessions");
    const row = page.locator("li").filter({ has: page.locator(".mono", { hasText: sessionId }) });
    await expect(row).toBeVisible({ timeout: 15_000 });
    await expect(row.getByText("1 events")).toBeVisible();

    await row.getByRole("link", { name: "Replay" }).click();
    await expect(page).toHaveURL(new RegExp(`/replay\\?session=${sessionId}`), { timeout: 10_000 });
    await expect(page.getByText("E2E replay test event")).toBeVisible({ timeout: 15_000 });
  });
});

test.describe("System health", () => {
  test("shows component status from API", async ({ page, request }) => {
    await waitForApi(request);
    await page.goto("/system-health");
    await expect(page.getByRole("heading", { name: "System Health" })).toBeVisible();
    await expect(page.getByText("Database")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("operational").first()).toBeVisible();
  });
});

test.describe("Reflection", () => {
  test("scan produces action summary", async ({ page, request }) => {
    await waitForApi(request);
    await page.goto("/reflection");
    await page.getByRole("button", { name: "Scan" }).click();
    await expect(page.getByText(/Planned actions|No consolidation actions/)).toBeVisible({
      timeout: 15_000,
    });
  });
});
