import { test, expect } from "@playwright/test";

test.describe("Settings Persistence", () => {
  test.beforeEach(async ({ page }) => {
    // Login first
    await page.goto("/login");
    await page.getByLabel(/username/i).fill("admin");
    await page.getByLabel(/password/i).fill("admin");
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.waitForURL(/\/scoring/);
  });

  test("should display study settings page", async ({ page }) => {
    // Navigate to study settings directly
    await page.goto("/settings/study");
    await page.waitForLoadState("networkidle");

    // Should show settings page with key sections
    await expect(page.getByRole("heading", { name: /study settings/i })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("heading", { name: /sleep.*wake.*algorithm/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /sleep period detection/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /night hours/i })).toBeVisible();
  });

  test("should show save and reset buttons", async ({ page }) => {
    await page.goto("/settings/study");
    await page.waitForLoadState("networkidle");

    // Should have save and reset buttons
    await expect(page.getByRole("button", { name: /save/i })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("button", { name: /reset/i })).toBeVisible();
  });

  test("should track unsaved changes", async ({ page }) => {
    await page.goto("/settings/study");
    await page.waitForLoadState("networkidle");

    // Wait for page to be fully loaded
    await expect(page.getByRole("heading", { name: /study settings/i })).toBeVisible({ timeout: 10000 });

    // Initially no unsaved indicator
    await expect(page.getByText(/unsaved changes/i)).not.toBeVisible();

    // Change night start hour - clear first then type to trigger change
    const nightStartInput = page.locator("#night-start");
    await nightStartInput.click();
    await nightStartInput.fill("22:00");
    await nightStartInput.blur(); // Trigger change event

    // Should show unsaved indicator
    await expect(page.getByText(/unsaved changes/i)).toBeVisible({ timeout: 5000 });
  });

  test("should save settings to backend", async ({ page }) => {
    await page.goto("/settings/study");
    await page.waitForLoadState("networkidle");

    // Wait for page to be fully loaded
    await expect(page.getByRole("heading", { name: /study settings/i })).toBeVisible({ timeout: 10000 });

    // Change night start hour
    const nightStartInput = page.getByLabel(/night start/i);
    await nightStartInput.fill("22:00");

    // Should show unsaved changes
    await expect(page.getByText(/unsaved changes/i)).toBeVisible();

    // Click save
    await page.getByRole("button", { name: /save/i }).click();

    // Should clear unsaved indicator after save
    await expect(page.getByText(/unsaved changes/i)).not.toBeVisible({ timeout: 5000 });
  });

  test("should persist settings across page refresh", async ({ page }) => {
    await page.goto("/settings/study");
    await page.waitForLoadState("networkidle");

    // Wait for page to be fully loaded
    await expect(page.getByRole("heading", { name: /study settings/i })).toBeVisible({ timeout: 10000 });

    // Wait for settings to load from backend
    await page.waitForTimeout(1000);

    // Get original value first
    const nightStartInput = page.locator("#night-start");
    const originalValue = await nightStartInput.inputValue();

    // Use a unique test value based on current time to avoid collision with prior test runs
    const testValue = originalValue === "22:30" ? "23:00" : "22:30";

    // Change night start hour - use fill() for time inputs
    await nightStartInput.fill(testValue);
    await nightStartInput.blur(); // Trigger change event

    // Verify value was actually changed
    await expect(nightStartInput).toHaveValue(testValue);

    // Wait for unsaved indicator with longer timeout
    await expect(page.getByText(/unsaved changes/i)).toBeVisible({ timeout: 10000 });

    // Save
    await page.getByRole("button", { name: /save/i }).click();
    await expect(page.getByText(/unsaved changes/i)).not.toBeVisible({ timeout: 5000 });

    // Wait for save to complete on backend
    await page.waitForTimeout(500);

    // Refresh page
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Wait for settings to reload from backend
    await expect(page.getByRole("heading", { name: /study settings/i })).toBeVisible({ timeout: 10000 });
    await page.waitForTimeout(1000); // Wait for settings API call to complete

    // Should still show the saved value (testValue from before refresh)
    await expect(page.locator("#night-start")).toHaveValue(testValue, { timeout: 10000 });
  });

  test("should reset settings to defaults", async ({ page }) => {
    await page.goto("/settings/study");
    await page.waitForLoadState("networkidle");

    // Wait for page to be fully loaded
    await expect(page.getByRole("heading", { name: /study settings/i })).toBeVisible({ timeout: 10000 });

    // Accept the confirmation dialog
    page.on("dialog", (dialog) => dialog.accept());

    // Click reset
    await page.getByRole("button", { name: /reset/i }).click();

    // Wait and verify defaults
    await page.waitForTimeout(1000);

    // Should reset to defaults (21:00 is the default)
    await expect(page.getByLabel(/night start/i)).toHaveValue("21:00", { timeout: 5000 });
  });

  test("should have algorithm selection options", async ({ page }) => {
    await page.goto("/settings/study");
    await page.waitForLoadState("networkidle");

    // Wait for page to be fully loaded
    await expect(page.getByRole("heading", { name: /study settings/i })).toBeVisible({ timeout: 10000 });

    // Find algorithm select
    const algorithmSelect = page.locator("#algorithm");
    await expect(algorithmSelect).toBeVisible();

    // Should have expected options
    await expect(algorithmSelect.locator("option")).toHaveCount(4);
  });

  test("should have sleep detection rule options", async ({ page }) => {
    await page.goto("/settings/study");
    await page.waitForLoadState("networkidle");

    // Wait for page to be fully loaded
    await expect(page.getByRole("heading", { name: /study settings/i })).toBeVisible({ timeout: 10000 });

    // Find detection rule select
    const detectionSelect = page.locator("#sleep-detection");
    await expect(detectionSelect).toBeVisible();

    // Should have expected options
    await expect(detectionSelect.locator("option")).toHaveCount(3);
  });
});
