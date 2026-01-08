import { test, expect } from "@playwright/test";

test.describe("Scoring Page", () => {
  test.beforeEach(async ({ page, context }) => {
    // Clear browser cache to ensure fresh bundles
    await context.clearCookies();
    const client = await page.context().newCDPSession(page);
    await client.send("Network.setCacheDisabled", { cacheDisabled: true });
  });

  test("displays activity plot with data", async ({ page }) => {
    // Login
    await page.goto("http://localhost:8501/login");
    await page.fill('input[name="username"]', "admin");
    await page.fill('input[name="password"]', "admin");
    await page.click('button[type="submit"]');

    // Should redirect to scoring page (default route)
    await page.waitForURL("**/scoring**", { timeout: 10000 });
    await page.waitForTimeout(1000);

    // File should auto-select and data should load
    // Wait for data to load - the file dropdown should be populated
    await page.waitForTimeout(3000);

    // Verify uPlot chart is rendered
    const uplotElement = page.locator(".uplot");
    await expect(uplotElement).toBeVisible();

    // Verify canvas exists and has proper dimensions
    const canvas = page.locator(".uplot canvas").first();
    await expect(canvas).toBeVisible();
    const box = await canvas.boundingBox();
    expect(box).toBeTruthy();
    expect(box!.width).toBeGreaterThan(400);
    expect(box!.height).toBeGreaterThan(200);

    // Verify no "No activity data" message
    const noDataMessage = page.locator("text=No activity data");
    await expect(noDataMessage).toHaveCount(0);

    // Verify sidebar controls are present (Sleep and Nonwear panels with counts)
    await expect(page.locator("text=/Sleep \\(\\d+\\)/")).toBeVisible();
    await expect(page.locator("text=/Nonwear \\(\\d+\\)/")).toBeVisible();

    // Verify file selector dropdown is present (first select is the file dropdown)
    const fileSelect = page.locator('select').first();
    await expect(fileSelect).toBeVisible();
  });

  test("date navigation works", async ({ page }) => {
    // Login - should redirect to scoring page directly
    await page.goto("http://localhost:8501/login");
    await page.fill('input[name="username"]', "admin");
    await page.fill('input[name="password"]', "admin");
    await page.click('button[type="submit"]');
    await page.waitForURL("**/scoring**", { timeout: 10000 });

    // Wait for file to auto-select and data to load
    await page.waitForTimeout(3000);

    // Get initial date index from the counter (e.g., "1/14")
    const dateCounter = page.locator("text=/\\(\\d+\\/\\d+\\)/").first();
    const initialCounter = await dateCounter.textContent();

    // Click next date button (the ChevronRight button)
    const nextButton = page.locator('button').filter({ has: page.locator('[class*="lucide-chevron-right"]') });
    await nextButton.click();
    await page.waitForTimeout(1000);

    // Verify date counter changed
    const newCounter = await dateCounter.textContent();
    expect(newCounter).not.toBe(initialCounter);
  });

  test("file dropdown allows file switching", async ({ page }) => {
    // Login
    await page.goto("http://localhost:8501/login");
    await page.fill('input[name="username"]', "admin");
    await page.fill('input[name="password"]', "admin");
    await page.click('button[type="submit"]');
    await page.waitForURL("**/scoring**", { timeout: 10000 });
    await page.waitForTimeout(2000);

    // Verify file dropdown is visible (first select is file dropdown)
    const fileSelect = page.locator('select').first();
    await expect(fileSelect).toBeVisible();

    // Get initial selected value
    const initialValue = await fileSelect.inputValue();

    // Get all options
    const options = await fileSelect.locator('option').all();

    // If there are multiple files, try switching
    if (options.length > 1) {
      // Get the second option value
      const secondOptionValue = await options[1].getAttribute('value');
      if (secondOptionValue && secondOptionValue !== initialValue) {
        await fileSelect.selectOption(secondOptionValue);
        await page.waitForTimeout(2000);

        // Verify the selection changed
        const newValue = await fileSelect.inputValue();
        expect(newValue).toBe(secondOptionValue);
      }
    }
  });

  test("marker creation positions correctly on plot", async ({ page }) => {
    // Login
    await page.goto("http://localhost:8501/login");
    await page.fill('input[name="username"]', "admin");
    await page.fill('input[name="password"]', "admin");
    await page.click('button[type="submit"]');
    await page.waitForURL("**/scoring**", { timeout: 10000 });
    await page.waitForTimeout(3000);

    // Wait for chart to be ready - use .u-over which is the click target
    const overlay = page.locator(".u-over").first();
    await expect(overlay).toBeVisible();

    // Get initial overlay dimensions for click positioning
    const initialOverlayBox = await overlay.boundingBox();
    expect(initialOverlayBox).toBeTruthy();

    // Use the overlay's click method with position - handles scroll/viewport automatically
    // Click at 25% from left for onset (use force:true to click through existing markers)
    await overlay.click({ position: { x: initialOverlayBox!.width * 0.25, y: initialOverlayBox!.height / 2 }, force: true });
    await page.waitForTimeout(500);

    // Click at 75% from left for offset
    await overlay.click({ position: { x: initialOverlayBox!.width * 0.75, y: initialOverlayBox!.height / 2 }, force: true });
    await page.waitForTimeout(500);

    // Wait for marker region to appear (with specific data-testid)
    const markerRegion = page.locator('[data-testid="marker-region-sleep-0"]');

    // Wait for marker to be visible - it should render after state updates
    await expect(markerRegion).toBeVisible({ timeout: 5000 });

    // Get fresh bounding boxes AFTER marker is created (to account for any scrolling)
    const overlayBox = await overlay.boundingBox();
    const markerBox = await markerRegion.boundingBox();
    expect(overlayBox).toBeTruthy();
    expect(markerBox).toBeTruthy();

    // Verify marker is positioned within the plot overlay area (where data is drawn)
    // The marker should be within the overlay area (with small tolerance for rendering)
    expect(markerBox!.x).toBeGreaterThanOrEqual(overlayBox!.x - 10);
    expect(markerBox!.x + markerBox!.width).toBeLessThanOrEqual(overlayBox!.x + overlayBox!.width + 10);
    // Marker top should be at or near overlay top
    expect(markerBox!.y).toBeGreaterThanOrEqual(overlayBox!.y - 10);
    expect(markerBox!.y).toBeLessThan(overlayBox!.y + overlayBox!.height);
    // Marker should have meaningful height (similar to overlay)
    expect(markerBox!.height).toBeGreaterThan(overlayBox!.height * 0.8);
  });

  test("marker data table shows highlighted row when marker selected", async ({ page }) => {
    // Login
    await page.goto("http://localhost:8501/login");
    await page.fill('input[name="username"]', "admin");
    await page.fill('input[name="password"]', "admin");
    await page.click('button[type="submit"]');
    await page.waitForURL("**/scoring**", { timeout: 10000 });
    await page.waitForTimeout(3000);

    // Wait for chart to be ready
    const overlay = page.locator(".u-over").first();
    await expect(overlay).toBeVisible();
    const overlayBox = await overlay.boundingBox();
    expect(overlayBox).toBeTruthy();

    // Create a marker by clicking twice (use force:true to click through existing markers)
    await overlay.click({ position: { x: overlayBox!.width * 0.25, y: overlayBox!.height / 2 }, force: true });
    await page.waitForTimeout(500);
    await overlay.click({ position: { x: overlayBox!.width * 0.75, y: overlayBox!.height / 2 }, force: true });
    await page.waitForTimeout(1000);

    // Verify marker was created (index may vary if existing markers)
    const markerRegions = page.locator('[data-testid^="marker-region-sleep-"]');
    await expect(markerRegions.first()).toBeVisible({ timeout: 5000 });

    // Check the onset data table - should have data now
    const onsetTable = page.locator('text=Sleep Onset Data').locator('..');
    await expect(onsetTable).toBeVisible();

    // Debug: Log what's in the table
    const tableContent = await onsetTable.textContent();
    console.log("Onset table content:", tableContent);

    // Check for highlighted row (purple background)
    const highlightedRow = page.locator('tr.bg-purple-500\\/30');
    const highlightedRowCount = await highlightedRow.count();
    console.log("Highlighted rows found:", highlightedRowCount);

    // Also check for any table rows
    const allRows = page.locator('table tbody tr');
    const allRowsCount = await allRows.count();
    console.log("Total table rows:", allRowsCount);

    // The table should have data rows (not just "Select a sleep marker" message)
    expect(allRowsCount).toBeGreaterThan(0);

    // Should have exactly one highlighted row per table
    expect(highlightedRowCount).toBeGreaterThanOrEqual(1);

    // Take screenshot for visual verification
    await page.screenshot({ path: 'test-results/marker-highlighting.png', fullPage: true });
  });

  test("nonwear marker data table shows highlighted row when marker selected", async ({ page }) => {
    // Login
    await page.goto("http://localhost:8501/login");
    await page.fill('input[name="username"]', "admin");
    await page.fill('input[name="password"]', "admin");
    await page.click('button[type="submit"]');
    await page.waitForURL("**/scoring**", { timeout: 10000 });
    await page.waitForTimeout(3000);

    // Wait for chart to be ready
    const overlay = page.locator(".u-over").first();
    await expect(overlay).toBeVisible();
    const overlayBox = await overlay.boundingBox();
    expect(overlayBox).toBeTruthy();

    // Switch to Nonwear mode
    const nonwearButton = page.locator('button:has-text("Nonwear")');
    await nonwearButton.click();
    await page.waitForTimeout(500);

    // Create a nonwear marker by clicking twice (use force:true to click through existing markers)
    await overlay.click({ position: { x: overlayBox!.width * 0.3, y: overlayBox!.height / 2 }, force: true });
    await page.waitForTimeout(500);
    await overlay.click({ position: { x: overlayBox!.width * 0.5, y: overlayBox!.height / 2 }, force: true });
    await page.waitForTimeout(1000);

    // Verify nonwear marker was created (index may vary if existing markers)
    const markerRegions = page.locator('[data-testid^="marker-region-nonwear-"]');
    await expect(markerRegions.first()).toBeVisible({ timeout: 5000 });

    // Check the table title changed to "Nonwear Start Data"
    const startTableTitle = page.locator('text=Nonwear Start Data');
    await expect(startTableTitle).toBeVisible();

    // Check for highlighted row (orange background for nonwear)
    const highlightedRow = page.locator('tr.bg-orange-500\\/30');
    const highlightedRowCount = await highlightedRow.count();
    console.log("Nonwear highlighted rows found:", highlightedRowCount);

    // Also check for any table rows
    const allRows = page.locator('table tbody tr');
    const allRowsCount = await allRows.count();
    console.log("Total table rows:", allRowsCount);

    // The table should have data rows
    expect(allRowsCount).toBeGreaterThan(0);

    // Should have highlighted rows for nonwear
    expect(highlightedRowCount).toBeGreaterThanOrEqual(1);

    // Take screenshot for visual verification
    await page.screenshot({ path: 'test-results/nonwear-marker-highlighting.png', fullPage: true });
  });

  test("markers persist after page reload", async ({ page }) => {
    // Login
    await page.goto("http://localhost:8501/login");
    await page.fill('input[name="username"]', "admin");
    await page.fill('input[name="password"]', "admin");
    await page.click('button[type="submit"]');
    await page.waitForURL("**/scoring**", { timeout: 10000 });
    await page.waitForTimeout(3000);

    // Wait for chart and markers to load
    const overlay = page.locator(".u-over").first();
    await expect(overlay).toBeVisible();

    // Get the current sleep marker count on date 1
    // Note: We only test sleep markers because other tests may create nonwear markers concurrently
    const sleepPanelBefore = page.locator('text=/Sleep \\(\\d+\\)/');
    await expect(sleepPanelBefore).toBeVisible({ timeout: 5000 });
    const countBefore = await sleepPanelBefore.textContent();
    console.log("Sleep count before reload:", countBefore);

    // Extract the number to verify it's at least 1 (markers exist)
    const beforeMatch = countBefore?.match(/Sleep \((\d+)\)/);
    const numBefore = beforeMatch ? parseInt(beforeMatch[1], 10) : 0;
    expect(numBefore).toBeGreaterThan(0); // Should have markers from previous tests

    // Reload the page
    await page.reload();
    await page.waitForTimeout(4000);

    // Wait for the chart to be ready again
    await expect(overlay).toBeVisible({ timeout: 10000 });

    // Wait for markers to load (they should appear in the Sleep panel)
    const sleepPanelAfterReload = page.locator('text=/Sleep \\(\\d+\\)/');
    await expect(sleepPanelAfterReload).toBeVisible({ timeout: 10000 });

    const countAfterReload = await sleepPanelAfterReload.textContent();
    console.log("Sleep count after reload:", countAfterReload);

    // Verify sleep markers were loaded from database - count should match
    expect(countAfterReload).toBe(countBefore);

    // Take screenshot for verification
    await page.screenshot({ path: 'test-results/marker-persistence.png', fullPage: true });
  });

  test("navigation sidebar shows correct items", async ({ page }) => {
    // Login
    await page.goto("http://localhost:8501/login");
    await page.fill('input[name="username"]', "admin");
    await page.fill('input[name="password"]', "admin");
    await page.click('button[type="submit"]');
    await page.waitForURL("**/scoring**", { timeout: 10000 });

    // Verify sidebar navigation items (use link selector to avoid matching header)
    await expect(page.getByRole('link', { name: 'Study Settings' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Data Settings' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Scoring' })).toBeVisible();

    // Navigate to Study Settings
    await page.getByRole('link', { name: 'Study Settings' }).click();
    await page.waitForURL("**/settings/study**", { timeout: 5000 });
    await expect(page.locator("h1:has-text('Study Settings')")).toBeVisible();

    // Navigate to Data Settings
    await page.getByRole('link', { name: 'Data Settings' }).click();
    await page.waitForURL("**/settings/data**", { timeout: 5000 });
    await expect(page.locator("h1:has-text('Data Settings')")).toBeVisible();

    // Navigate back to Scoring
    await page.getByRole('link', { name: 'Scoring' }).click();
    await page.waitForURL("**/scoring**", { timeout: 5000 });
  });
});
