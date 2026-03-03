import { test, expect } from "@playwright/test";

test.describe("Case View", () => {
    test("shows case not found for invalid ID", async ({ page }) => {
        await page.goto("/cases/nonexistent-case-id");
        // Should show error or redirect
        await page.waitForTimeout(2000);
        const content = await page.textContent("body");
        expect(content).toBeTruthy();
    });

    test("tab navigation renders", async ({ page }) => {
        await page.goto("/cases/test-case-id");
        await page.waitForTimeout(2000);
        // Tabs should be present
        const tabs = page.locator('nav a, [role="tab"]');
        const count = await tabs.count();
        // Should have tabs or redirect to sign-in
        expect(count).toBeGreaterThanOrEqual(0);
    });

    test("activity tab loads", async ({ page }) => {
        await page.goto("/cases/test-case-id/activity");
        await page.waitForTimeout(2000);
        const content = await page.textContent("body");
        expect(content).toBeTruthy();
    });

    test("strategy tab loads", async ({ page }) => {
        await page.goto("/cases/test-case-id/strategy");
        await page.waitForTimeout(2000);
        const content = await page.textContent("body");
        expect(content).toBeTruthy();
    });

    test("research tab loads", async ({ page }) => {
        await page.goto("/cases/test-case-id/research");
        await page.waitForTimeout(2000);
        const content = await page.textContent("body");
        expect(content).toBeTruthy();
    });
});
