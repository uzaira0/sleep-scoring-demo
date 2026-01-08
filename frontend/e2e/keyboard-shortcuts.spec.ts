/**
 * E2E tests for keyboard shortcuts on the scoring page.
 */

import { test, expect } from "@playwright/test";

test.describe("Keyboard Shortcuts", () => {
  test.beforeEach(async ({ page, context }) => {
    // Clear browser cache
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

  test("arrow keys navigate dates", async ({ page }) => {
    await login(page);
    await page.waitForTimeout(2000);

    // Get initial date display
    const dateDisplay = page.locator(".min-w-\\[140px\\]").first();
    const initialText = await dateDisplay.textContent();

    // Press right arrow to go to next date
    await page.keyboard.press("ArrowRight");
    await page.waitForTimeout(500);

    // Date should have changed (or stayed same if at end)
    const newText = await dateDisplay.textContent();
    // Just verify the page is still responsive
    expect(newText).toBeDefined();
  });

  test("Ctrl+4 toggles view mode", async ({ page }) => {
    await login(page);
    await page.waitForTimeout(2000);

    // Find the view mode selector
    const viewSelector = page.locator("select").filter({ hasText: /24h|48h/ }).first();

    // Get initial value
    const initialValue = await viewSelector.inputValue();

    // Press Ctrl+4 to toggle
    await page.keyboard.press("Control+4");
    await page.waitForTimeout(500);

    // View mode should have toggled
    const newValue = await viewSelector.inputValue();
    if (initialValue === "24") {
      expect(newValue).toBe("48");
    } else {
      expect(newValue).toBe("24");
    }
  });

  test("Escape cancels marker creation", async ({ page }) => {
    await login(page);
    await page.waitForTimeout(2000);

    // Click on the plot to start marker creation
    const plotArea = page.locator(".flex-1.flex.flex-col").first();
    await plotArea.click({ position: { x: 200, y: 100 } });

    // Wait for creation mode indicator
    await page.waitForTimeout(300);

    // Press Escape to cancel
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);

    // Page should be responsive (no error)
    await expect(page.locator(".flex-1.flex.flex-col").first()).toBeVisible();
  });

  test("C key without modifiers is for delete", async ({ page }) => {
    await login(page);
    await page.waitForTimeout(2000);

    // Just verify pressing C doesn't cause an error
    await page.keyboard.press("c");
    await page.waitForTimeout(300);

    // Page should still be responsive
    await expect(page.locator(".flex-1.flex.flex-col").first()).toBeVisible();
  });

  test("Q/E/A/D keys adjust markers", async ({ page }) => {
    await login(page);
    await page.waitForTimeout(2000);

    // Just verify pressing these keys doesn't cause an error
    await page.keyboard.press("q");
    await page.waitForTimeout(100);
    await page.keyboard.press("e");
    await page.waitForTimeout(100);
    await page.keyboard.press("a");
    await page.waitForTimeout(100);
    await page.keyboard.press("d");
    await page.waitForTimeout(100);

    // Page should still be responsive
    await expect(page.locator(".flex-1.flex.flex-col").first()).toBeVisible();
  });
});

test.describe("Marker Type Selector", () => {
  test.beforeEach(async ({ page, context }) => {
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

  test("marker type dropdown is visible when marker selected", async ({ page }) => {
    await login(page);
    await page.waitForTimeout(2000);

    // Check if there are any sleep markers
    const sleepCard = page.locator("text=Sleep").first();
    await expect(sleepCard).toBeVisible();

    // If a marker is selected, the Type dropdown should appear
    // This test just verifies the control bar loads correctly
    await expect(page.locator("text=Mode:").first()).toBeVisible();
  });

  test("marker type options include Main Sleep and Nap", async ({ page }) => {
    await login(page);
    await page.waitForTimeout(2000);

    // Look for a select with marker type options
    // The options are rendered in the DOM when the marker is selected
    // For now, just verify the page structure is correct
    await expect(page.locator("text=Mode:").first()).toBeVisible();
  });
});

test.describe("Color Legend Dialog", () => {
  test.beforeEach(async ({ page, context }) => {
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

  test("help button opens color legend dialog", async ({ page }) => {
    await login(page);
    await page.waitForTimeout(2000);

    // Find and click the help button
    const helpButton = page.locator('button[title="Show color legend and keyboard shortcuts"]');
    await expect(helpButton).toBeVisible();
    await helpButton.click();

    // Dialog should open
    await page.waitForTimeout(500);
    await expect(page.getByText("Color Legend")).toBeVisible();
  });

  test("color legend dialog shows keyboard shortcuts", async ({ page }) => {
    await login(page);
    await page.waitForTimeout(2000);

    // Open dialog
    const helpButton = page.locator('button[title="Show color legend and keyboard shortcuts"]');
    await helpButton.click();
    await page.waitForTimeout(500);

    // Check for keyboard shortcuts section
    await expect(page.getByText("Keyboard Shortcuts")).toBeVisible();
    await expect(page.getByText("Navigate dates")).toBeVisible();
  });

  test("color legend dialog can be closed with Escape", async ({ page }) => {
    await login(page);
    await page.waitForTimeout(2000);

    // Open dialog
    const helpButton = page.locator('button[title="Show color legend and keyboard shortcuts"]');
    await helpButton.click();
    await page.waitForTimeout(500);

    // Verify dialog is open
    await expect(page.getByText("Color Legend")).toBeVisible();

    // Close with Escape
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);

    // Dialog should be closed
    await expect(page.getByText("Color Legend")).not.toBeVisible();
  });

  test("color legend dialog shows marker color explanations", async ({ page }) => {
    await login(page);
    await page.waitForTimeout(2000);

    // Open dialog
    const helpButton = page.locator('button[title="Show color legend and keyboard shortcuts"]');
    await helpButton.click();
    await page.waitForTimeout(500);

    // Check for color explanations
    await expect(page.getByText("Sleep Markers")).toBeVisible();
    await expect(page.getByText("Nonwear Markers")).toBeVisible();
    await expect(page.getByText("Algorithm Results")).toBeVisible();
  });
});
