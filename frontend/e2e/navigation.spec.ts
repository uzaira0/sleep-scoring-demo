import { test, expect } from "@playwright/test";

/**
 * Navigation tests - Tests sidebar navigation functionality
 */
test.describe("Navigation", () => {
  // Login before each test
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/username/i).fill("admin");
    await page.getByLabel(/password/i).fill("admin");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/scoring/);
  });

  test("should display scoring page after login", async ({ page }) => {
    await expect(page).toHaveURL(/\/scoring/);

    // Should show activity plot
    const uplotElement = page.locator(".uplot");
    await expect(uplotElement).toBeVisible({ timeout: 10000 });
  });

  test("should navigate to study settings page", async ({ page }) => {
    // Find and click study settings link in sidebar
    const studySettingsLink = page.getByRole("link", { name: /study settings/i });
    await expect(studySettingsLink).toBeVisible();
    await studySettingsLink.click();

    await expect(page).toHaveURL(/\/settings\/study/);
    await expect(page.getByRole("heading", { name: /study settings/i })).toBeVisible();
  });

  test("should navigate to data settings page", async ({ page }) => {
    // Find and click data settings link in sidebar
    const dataSettingsLink = page.getByRole("link", { name: /data settings/i });
    await expect(dataSettingsLink).toBeVisible();
    await dataSettingsLink.click();

    await expect(page).toHaveURL(/\/settings\/data/);
    await expect(page.getByRole("heading", { name: /data settings/i })).toBeVisible();
  });

  test("should navigate to export page", async ({ page }) => {
    // Find and click export link in sidebar
    const exportLink = page.getByRole("link", { name: /export/i });
    await expect(exportLink).toBeVisible();
    await exportLink.click();

    await expect(page).toHaveURL(/\/export/);
  });

  test("should navigate back to scoring page", async ({ page }) => {
    // Navigate to settings first
    await page.getByRole("link", { name: /study settings/i }).click();
    await expect(page).toHaveURL(/\/settings\/study/);

    // Navigate back to scoring
    const scoringLink = page.getByRole("link", { name: /scoring/i });
    await expect(scoringLink).toBeVisible();
    await scoringLink.click();

    await expect(page).toHaveURL(/\/scoring/);
  });

  test("should redirect unknown routes to scoring", async ({ page }) => {
    await page.goto("/unknown-route");

    // Should redirect to scoring (via catch-all redirect to / which redirects to /scoring)
    await expect(page).toHaveURL(/\/scoring/);
  });

  test("should show sidebar navigation items", async ({ page }) => {
    // Verify all expected navigation links are visible
    await expect(page.getByRole("link", { name: /study settings/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /data settings/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /scoring/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /export/i })).toBeVisible();
  });

  test("should highlight active navigation item", async ({ page }) => {
    // On scoring page, the Scoring link should be active (has bg-primary class)
    const scoringLink = page.getByRole("link", { name: /scoring/i });
    await expect(scoringLink).toHaveClass(/bg-primary/);

    // Navigate to settings
    await page.getByRole("link", { name: /study settings/i }).click();
    await expect(page).toHaveURL(/\/settings\/study/);

    // Now Study Settings should be active
    const studySettingsLink = page.getByRole("link", { name: /study settings/i });
    await expect(studySettingsLink).toHaveClass(/bg-primary/);
  });
});
