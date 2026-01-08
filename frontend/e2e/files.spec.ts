import { test, expect } from "@playwright/test";

/**
 * File management tests - Tests file selection functionality on the scoring page
 * Note: This app doesn't have a separate files page. File selection is on /scoring
 */
test.describe("File Selection", () => {
  // Login before each test
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/username/i).fill("admin");
    await page.getByLabel(/password/i).fill("admin");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/scoring/);
  });

  test("should display scoring page with file selector", async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState("networkidle");

    // Should show file dropdown (first select element)
    const fileSelect = page.locator("select").first();
    await expect(fileSelect).toBeVisible({ timeout: 10000 });
  });

  test("should have files in the dropdown", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // Get file dropdown
    const fileSelect = page.locator("select").first();
    await expect(fileSelect).toBeVisible({ timeout: 10000 });

    // Should have at least one option (files should be auto-loaded)
    const options = await fileSelect.locator("option").count();
    expect(options).toBeGreaterThan(0);
  });

  test("should auto-select first file on page load", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Get file dropdown
    const fileSelect = page.locator("select").first();
    await expect(fileSelect).toBeVisible({ timeout: 10000 });

    // Should have a value selected (not empty)
    const selectedValue = await fileSelect.inputValue();
    expect(selectedValue).not.toBe("");
  });

  test("should be able to switch files", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    const fileSelect = page.locator("select").first();
    await expect(fileSelect).toBeVisible({ timeout: 10000 });

    // Get all options
    const options = await fileSelect.locator("option").all();

    // If there are multiple files, try switching
    if (options.length > 1) {
      const firstValue = await fileSelect.inputValue();
      const secondOptionValue = await options[1].getAttribute("value");

      if (secondOptionValue && secondOptionValue !== firstValue) {
        await fileSelect.selectOption(secondOptionValue);
        await page.waitForTimeout(1000);

        // Verify the selection changed
        const newValue = await fileSelect.inputValue();
        expect(newValue).toBe(secondOptionValue);
      }
    }
  });

  test("should load activity data when file is selected", async ({ page }) => {
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Verify activity plot is visible with data
    const uplotElement = page.locator(".uplot");
    await expect(uplotElement).toBeVisible({ timeout: 10000 });

    // Verify canvas has proper dimensions
    const canvas = page.locator(".uplot canvas").first();
    await expect(canvas).toBeVisible();
    const box = await canvas.boundingBox();
    expect(box).toBeTruthy();
    expect(box!.width).toBeGreaterThan(100);
    expect(box!.height).toBeGreaterThan(100);
  });
});
