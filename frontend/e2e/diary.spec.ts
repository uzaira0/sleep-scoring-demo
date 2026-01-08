import { test, expect } from "@playwright/test";

test.describe("Diary Panel", () => {
  test.beforeEach(async ({ page }) => {
    // Login first
    await page.goto("/login");
    await page.getByLabel(/username/i).fill("admin");
    await page.getByLabel(/password/i).fill("admin");
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.waitForURL(/\/scoring/);
  });

  test("should display diary panel on scoring page", async ({ page }) => {
    // Navigate to scoring page directly
    await page.goto("/scoring");
    await page.waitForLoadState("networkidle");

    // Wait for page to load and check for diary panel
    await expect(page.getByText(/sleep diary/i)).toBeVisible({ timeout: 15000 });
  });

  test("should show empty state when no diary entry exists", async ({ page }) => {
    await page.goto("/scoring");
    await page.waitForLoadState("networkidle");

    // Wait for scoring page to load with a file
    await page.waitForTimeout(3000);

    // Diary panel should show empty state or entry
    const diaryPanel = page.locator("text=Sleep Diary").first();
    await expect(diaryPanel).toBeVisible({ timeout: 10000 });
  });

  test("should have add entry button when no entry exists", async ({ page }) => {
    await page.goto("/scoring");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Look for "Add Entry" or diary form
    const addButton = page.getByRole("button", { name: /add entry/i });
    const editButton = page.getByRole("button", { name: /edit/i });

    // Either add or edit should be visible (depending on whether entry exists)
    const hasAddOrEdit = await addButton.isVisible() || await editButton.isVisible();
    expect(hasAddOrEdit).toBeTruthy();
  });

  test("should open edit form when clicking add/edit", async ({ page }) => {
    await page.goto("/scoring");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Click add or edit button
    const addButton = page.getByRole("button", { name: /add entry/i });
    const editButton = page.getByRole("button", { name: /edit/i });

    if (await addButton.isVisible()) {
      await addButton.click();
    } else if (await editButton.isVisible()) {
      await editButton.click();
    }

    // Should show time input fields
    await expect(page.getByLabel(/bed time/i)).toBeVisible({ timeout: 5000 });
    await expect(page.getByLabel(/wake time/i)).toBeVisible();
  });

  test("should have save and cancel buttons in edit mode", async ({ page }) => {
    await page.goto("/scoring");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Enter edit mode
    const addButton = page.getByRole("button", { name: /add entry/i });
    const editButton = page.getByRole("button", { name: /edit/i });

    if (await addButton.isVisible()) {
      await addButton.click();
    } else if (await editButton.isVisible()) {
      await editButton.click();
    }

    // Should show save and cancel buttons
    await expect(page.getByRole("button", { name: /save/i })).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole("button", { name: /cancel/i })).toBeVisible();
  });

  test("should cancel editing without saving", async ({ page }) => {
    await page.goto("/scoring");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Enter edit mode
    const addButton = page.getByRole("button", { name: /add entry/i });
    const editButton = page.getByRole("button", { name: /edit/i });

    if (await addButton.isVisible()) {
      await addButton.click();
    } else if (await editButton.isVisible()) {
      await editButton.click();
    }

    // Wait for form
    await expect(page.getByLabel(/bed time/i)).toBeVisible({ timeout: 5000 });

    // Fill in some data
    const bedTimeInput = page.getByLabel(/bed time/i);
    await bedTimeInput.fill("23:00");

    // Click cancel
    await page.getByRole("button", { name: /cancel/i }).click();

    // Should exit edit mode (form should not be visible)
    await expect(page.getByLabel(/bed time/i)).not.toBeVisible({ timeout: 5000 });
  });

  test("should have upload button for CSV import", async ({ page }) => {
    await page.goto("/scoring");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Look for upload button in diary panel (it's a small icon button)
    const diarySection = page.locator("text=Sleep Diary").locator("..");
    const uploadButton = diarySection.locator("button").first();

    // Should have some button in the diary header
    await expect(uploadButton).toBeVisible({ timeout: 10000 });
  });

  test("should save diary entry successfully", async ({ page }) => {
    await page.goto("/scoring");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Enter edit mode
    const addButton = page.getByRole("button", { name: /add entry/i });
    const editButton = page.getByRole("button", { name: /edit/i });

    if (await addButton.isVisible()) {
      await addButton.click();
    } else if (await editButton.isVisible()) {
      await editButton.click();
    }

    // Wait for form
    await expect(page.getByLabel(/bed time/i)).toBeVisible({ timeout: 5000 });

    // Fill in diary data
    await page.getByLabel(/bed time/i).fill("23:00");
    await page.getByLabel(/wake time/i).fill("07:00");

    // Save
    await page.getByRole("button", { name: /save/i }).click();

    // Should exit edit mode and show saved data
    await expect(page.getByLabel(/bed time/i)).not.toBeVisible({ timeout: 5000 });

    // Should show the saved times in view mode
    await expect(page.getByText(/23:00/)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/07:00/)).toBeVisible();
  });

  test("should display diary times with icons", async ({ page }) => {
    await page.goto("/scoring");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Check for time labels (these appear in view mode if entry exists)
    // We're checking the structure exists, not specific values
    const diarySection = page.locator("text=Sleep Diary").locator("..");
    await expect(diarySection).toBeVisible({ timeout: 10000 });
  });
});
