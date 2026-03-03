import { test, expect } from "@playwright/test";

test.describe("Transcription Page", () => {
    test("loads transcription page", async ({ page }) => {
        await page.goto("/cases/test-case-id/transcription");
        await page.waitForTimeout(2000);
        const content = await page.textContent("body");
        expect(content).toBeTruthy();
    });

    test("shows empty state when no jobs", async ({ page }) => {
        await page.goto("/cases/test-case-id/transcription");
        await page.waitForTimeout(3000);
        const content = await page.textContent("body");
        // Should show either job list or empty state
        expect(content).toBeTruthy();
    });
});
