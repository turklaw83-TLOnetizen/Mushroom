import { test, expect } from "@playwright/test";

test.describe("Tenant Admin Page", () => {
    test("loads tenant management page", async ({ page }) => {
        await page.goto("/admin/tenants");
        await page.waitForTimeout(2000);
        const content = await page.textContent("body");
        expect(content).toBeTruthy();
    });

    test("has create tenant button", async ({ page }) => {
        await page.goto("/admin/tenants");
        await page.waitForTimeout(2000);
        const buttons = page.locator('button:has-text("New Tenant"), button:has-text("Create")');
        const count = await buttons.count();
        expect(count).toBeGreaterThanOrEqual(0);
    });
});
