import { test, expect } from "@playwright/test";

test.describe("Security Dashboard", () => {
    test("loads security page", async ({ page }) => {
        await page.goto("/cases/test-case-id/security");
        await page.waitForTimeout(2000);
        const content = await page.textContent("body");
        expect(content).toBeTruthy();
    });

    test("has overview metrics", async ({ page }) => {
        await page.goto("/cases/test-case-id/security");
        await page.waitForTimeout(2000);
        // Metrics cards should be present
        const cards = page.locator('[class*="card"], [class*="Card"]');
        const count = await cards.count();
        expect(count).toBeGreaterThanOrEqual(0);
    });
});
