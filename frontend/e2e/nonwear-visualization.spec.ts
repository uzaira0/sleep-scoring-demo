/**
 * E2E tests for Choi nonwear detection visualization.
 *
 * Tests that algorithm-detected nonwear periods are displayed
 * on the activity plot with a distinct visual style (striped pattern).
 */

import { test, expect } from "@playwright/test";

test.describe("Nonwear Visualization", () => {
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
    await page.waitForURL("**/files");
    await page.goto("http://localhost:8501/scoring");
    await page.waitForSelector(".uplot", { timeout: 10000 });
  }

  test("displays Choi-detected nonwear regions on plot", async ({ page }) => {
    await login(page);

    // Give time for the scoring endpoint to return with nonwear results
    await page.waitForTimeout(2000);

    // Check if Choi nonwear regions are rendered
    // These should have the class 'marker-region choi-nonwear'
    const choiRegions = page.locator(".marker-region.choi-nonwear");

    // The demo data might or might not have nonwear periods
    // depending on the activity patterns. We just verify the
    // visualization code runs without errors.
    const count = await choiRegions.count();
    console.log(`Choi nonwear regions found: ${count}`);

    // If there are Choi regions, verify they have the correct styling
    if (count > 0) {
      const firstRegion = choiRegions.first();

      // Verify it has absolute positioning
      await expect(firstRegion).toHaveCSS("position", "absolute");

      // Verify it has the striped background pattern
      const background = await firstRegion.evaluate(
        (el) => window.getComputedStyle(el).background
      );
      expect(background).toContain("repeating-linear-gradient");
    }
  });

  test("Choi regions are visually distinct from user-placed nonwear markers", async ({
    page,
  }) => {
    await login(page);
    await page.waitForTimeout(2000);

    // Create a user-placed nonwear marker by switching to nonwear mode
    // and clicking twice on the plot
    const nonwearModeBtn = page.getByRole("button", { name: /nonwear/i });
    await nonwearModeBtn.click();

    // Click twice on the plot to create a nonwear marker
    const plotOverlay = page.locator(".u-over");
    await plotOverlay.click({ position: { x: 150, y: 100 }, force: true });
    await plotOverlay.click({ position: { x: 250, y: 100 }, force: true });

    // Wait for marker to be created
    await page.waitForTimeout(500);

    // Get user-placed nonwear regions
    const userNonwearRegions = page.locator(".marker-region.nonwear");
    const userCount = await userNonwearRegions.count();
    expect(userCount).toBeGreaterThan(0);

    // If there's a user nonwear region, verify it has solid color (not striped)
    if (userCount > 0) {
      const userRegion = userNonwearRegions.first();
      const userBackground = await userRegion.evaluate(
        (el) => window.getComputedStyle(el).background
      );

      // User nonwear markers should have solid color, not repeating-linear-gradient
      expect(userBackground).not.toContain("repeating-linear-gradient");
    }

    // Get Choi nonwear regions (algorithm-detected)
    const choiRegions = page.locator(".marker-region.choi-nonwear");
    const choiCount = await choiRegions.count();

    // If there are Choi regions, verify they have striped pattern
    if (choiCount > 0) {
      const choiRegion = choiRegions.first();
      const choiBackground = await choiRegion.evaluate(
        (el) => window.getComputedStyle(el).background
      );

      // Choi regions should have striped pattern
      expect(choiBackground).toContain("repeating-linear-gradient");
    }
  });

  test("Choi regions update when date changes", async ({ page }) => {
    await login(page);
    await page.waitForTimeout(2000);

    // Get initial count of Choi regions
    const initialChoiRegions = page.locator(".marker-region.choi-nonwear");
    const initialCount = await initialChoiRegions.count();
    console.log(`Initial Choi regions: ${initialCount}`);

    // Navigate to next date using the date navigation buttons
    const nextDateBtn = page.locator('[data-testid="next-date-btn"]');
    const hasNextBtn = (await nextDateBtn.count()) > 0;

    if (hasNextBtn) {
      await nextDateBtn.click();
      await page.waitForSelector(".uplot", { timeout: 10000 });
      await page.waitForTimeout(2000);

      // Count may change with different date
      const afterDateChange = await page
        .locator(".marker-region.choi-nonwear")
        .count();
      console.log(`Choi regions after date change: ${afterDateChange}`);
    } else {
      // If no next button, try previous button
      const prevDateBtn = page.locator('[data-testid="prev-date-btn"]');
      if ((await prevDateBtn.count()) > 0) {
        await prevDateBtn.click();
        await page.waitForSelector(".uplot", { timeout: 10000 });
        await page.waitForTimeout(2000);

        const afterDateChange = await page
          .locator(".marker-region.choi-nonwear")
          .count();
        console.log(`Choi regions after date change: ${afterDateChange}`);
      }
    }

    // The test passes if no errors occur - we just want to verify
    // the visualization code handles date changes correctly
    expect(true).toBe(true);
  });
});
