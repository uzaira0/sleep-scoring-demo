import { test, expect } from "@playwright/test";

test.describe("Authentication", () => {
  test.beforeEach(async ({ page }) => {
    // Start fresh - clear any stored auth
    await page.goto("/login");
  });

  test("should display login page for unauthenticated users", async ({
    page,
  }) => {
    await page.goto("/");

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/);

    // Should show login form (heading is "Sleep Scoring")
    await expect(page.getByRole("heading", { name: /sleep scoring/i })).toBeVisible();
    await expect(page.getByLabel(/username/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
  });

  test("should show error for invalid credentials", async ({ page }) => {
    await page.goto("/login");

    // Fill in invalid credentials
    await page.getByLabel(/username/i).fill("invaliduser");
    await page.getByLabel(/password/i).fill("wrongpassword");
    await page.getByRole("button", { name: /sign in/i }).click();

    // Should show error message
    await expect(page.getByText(/invalid|incorrect|failed/i)).toBeVisible();
  });

  test("should login successfully with valid credentials", async ({ page }) => {
    await page.goto("/login");

    // Fill in valid credentials (default admin user)
    await page.getByLabel(/username/i).fill("admin");
    await page.getByLabel(/password/i).fill("admin");
    await page.getByRole("button", { name: /sign in/i }).click();

    // Should redirect to scoring page after login
    await expect(page).toHaveURL(/\/scoring/);
  });

  test("should persist login across page refresh", async ({ page }) => {
    // Login first
    await page.goto("/login");
    await page.getByLabel(/username/i).fill("admin");
    await page.getByLabel(/password/i).fill("admin");
    await page.getByRole("button", { name: /sign in/i }).click();

    // Wait for redirect
    await expect(page).toHaveURL(/\/scoring/);

    // Refresh the page
    await page.reload();

    // Should still be on scoring page (not redirected to login)
    await expect(page).toHaveURL(/\/scoring/);
  });

  test("should logout successfully", async ({ page }) => {
    // Login first
    await page.goto("/login");
    await page.getByLabel(/username/i).fill("admin");
    await page.getByLabel(/password/i).fill("admin");
    await page.getByRole("button", { name: /sign in/i }).click();

    // Wait for redirect
    await expect(page).toHaveURL(/\/scoring/);

    // Find and click logout button (in sidebar)
    const logoutButton = page.getByRole("button", { name: /logout/i });
    await expect(logoutButton).toBeVisible();
    await logoutButton.click();

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/);
  });
});
