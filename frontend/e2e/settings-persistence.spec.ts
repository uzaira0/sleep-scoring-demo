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

    // Wait for settings to load from backend
    await page.waitForTimeout(1000);

    // Initially no unsaved indicator
    await expect(page.getByText(/unsaved changes/i)).not.toBeVisible();

    // Change algorithm dropdown instead of time input (more reliable)
    const algorithmSelect = page.locator("#algorithm");
    const currentValue = await algorithmSelect.inputValue();
    const newValue = currentValue === "sadeh_1994_actilife" ? "cole_kripke_1992_actilife" : "sadeh_1994_actilife";
    await algorithmSelect.selectOption(newValue);

    // Should show unsaved indicator
    await expect(page.getByText(/unsaved changes/i)).toBeVisible({ timeout: 5000 });
  });

  test("should save settings to backend", async ({ page }) => {
    await page.goto("/settings/study");
    await page.waitForLoadState("networkidle");

    // Wait for page to be fully loaded
    await expect(page.getByRole("heading", { name: /study settings/i })).toBeVisible({ timeout: 10000 });

    // Wait for settings to load from backend
    await page.waitForTimeout(1000);

    // Change algorithm dropdown (more reliable than time input)
    const algorithmSelect = page.locator("#algorithm");
    const currentValue = await algorithmSelect.inputValue();
    const newValue = currentValue === "sadeh_1994_actilife" ? "cole_kripke_1992_actilife" : "sadeh_1994_actilife";
    await algorithmSelect.selectOption(newValue);

    // Should show unsaved changes
    await expect(page.getByText(/unsaved changes/i)).toBeVisible({ timeout: 5000 });

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

    // Wait for settings to load from backend - settings API must complete
    await page.waitForTimeout(2000);

    // Get original algorithm value
    const algorithmSelect = page.locator("#algorithm");
    const originalValue = await algorithmSelect.inputValue();
    console.log("Original algorithm:", originalValue);

    // Use a different algorithm value
    const testValue = originalValue === "sadeh_1994_actilife" ? "cole_kripke_1992_actilife" : "sadeh_1994_actilife";
    console.log("Test algorithm:", testValue);

    // Change algorithm dropdown
    await algorithmSelect.selectOption(testValue);

    // Verify value was actually changed
    await expect(algorithmSelect).toHaveValue(testValue);

    // Wait for unsaved indicator with longer timeout
    await expect(page.getByText(/unsaved changes/i)).toBeVisible({ timeout: 10000 });

    // Save and wait for the request to complete
    const saveButton = page.getByRole("button", { name: /save/i });
    await Promise.all([
      page.waitForResponse((response) => response.url().includes("/api/settings") && response.request().method() === "PUT"),
      saveButton.click(),
    ]);

    // Verify unsaved indicator is cleared (indicates save completed)
    await expect(page.getByText(/unsaved changes/i)).not.toBeVisible({ timeout: 5000 });

    // Wait a bit more for backend to fully process
    await page.waitForTimeout(1000);

    // Set up response listener BEFORE reload (response happens during reload)
    const responsePromise = page.waitForResponse(
      (response) => response.url().includes("/api/settings") && response.request().method() === "GET"
    );

    // Refresh page
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Wait for settings page to be ready
    await expect(page.getByRole("heading", { name: /study settings/i })).toBeVisible({ timeout: 10000 });

    // Wait for settings API response to complete
    await responsePromise;
    await page.waitForTimeout(500); // Allow state to update

    // Check the value - it should be the saved testValue
    const valueAfterReload = await page.locator("#algorithm").inputValue();
    console.log("Algorithm after reload:", valueAfterReload);

    // Should still show the saved value (testValue from before refresh)
    await expect(page.locator("#algorithm")).toHaveValue(testValue, { timeout: 10000 });
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
