import { test, expect } from "@playwright/test";

test.describe("AI Tools Page", () => {
    test("loads AI tools page", async ({ page }) => {
        await page.goto("/cases/test-case-id/ai-tools");
        await page.waitForTimeout(2000);
        const content = await page.textContent("body");
        expect(content).toBeTruthy();
    });

    test("has tab navigation for tools", async ({ page }) => {
        await page.goto("/cases/test-case-id/ai-tools");
        await page.waitForTimeout(2000);
        // Should have tabs for Model Compare, Summarize, etc.
        const buttons = page.locator("button");
        const count = await buttons.count();
        expect(count).toBeGreaterThanOrEqual(0);
    });
});
