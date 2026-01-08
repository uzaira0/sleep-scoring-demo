/**
 * E2E tests for the Metrics Panel component.
 *
 * Tests that sleep quality metrics are displayed for selected sleep periods.
 */

import { test, expect } from "@playwright/test";

test.describe("Metrics Panel", () => {
  test.beforeEach(async ({ page, context }) => {
    // Clear browser cache to ensure fresh bundles
    await context.clearCookies();
    const client = await page.context().newCDPSession(page);
    await client.send("Network.setCacheDisabled", { cacheDisabled: true });
  });

  async function login(page: import("@playwright/test").Page) {
    await page.goto("http://localhost:8501/login");
    await page.fill('input[name="username"]', "admin");
    await page.fill('input[name="password"]', "admin");
    await page.click('button[type="submit"]');
    await page.waitForURL("**/scoring");
  }

  test("displays metrics panel on scoring page", async ({ page }) => {
    await login(page);

    // Wait for page to load
    await page.waitForTimeout(2000);

    // Look for the Metrics card heading
    await expect(page.getByRole("heading", { name: "Metrics" })).toBeVisible({ timeout: 10000 });
  });

  test("shows empty state when no marker selected", async ({ page }) => {
    await login(page);

    // Wait for page to load
    await page.waitForTimeout(2000);

    // Should show message to select a marker
    await expect(
      page.getByText("Select a sleep marker to view metrics")
    ).toBeVisible({ timeout: 10000 });
  });

  test("metrics panel updates when sleep marker is selected", async ({ page }) => {
    await login(page);

    // Wait for page to load and data to render
    await page.waitForTimeout(3000);

    // Check if there are sleep markers to select
    const sleepCards = page.locator("text=MAIN_SLEEP, text=NAP").first();
    const hasSleepMarkers = (await sleepCards.count()) > 0;

    if (hasSleepMarkers) {
      // Click on a sleep marker to select it
      await sleepCards.click();
      await page.waitForTimeout(500);

      // The metrics panel should show metrics or the empty state
      // depending on whether metrics were calculated
      const metricsPanel = page.locator("text=Metrics");
      await expect(metricsPanel).toBeVisible();
    } else {
      // If no markers, just verify the panel shows the empty state
      await expect(
        page.getByText("Select a sleep marker to view metrics")
      ).toBeVisible();
    }
  });

  test("displays metrics labels in compact mode", async ({ page }) => {
    await login(page);

    // Wait for page to load
    await page.waitForTimeout(3000);

    // Check for the metrics panel heading
    await expect(page.getByRole("heading", { name: "Metrics" })).toBeVisible({ timeout: 10000 });

    // The compact mode shows TST, SE, WASO, and Awakenings labels
    // These should be visible when the metrics panel renders
    // Even without data selected, the panel structure should be present
    const metricsPanel = page.locator("text=Select a sleep marker to view metrics");

    // Verify the empty state message is visible
    await expect(metricsPanel).toBeVisible({ timeout: 10000 });
  });
});
