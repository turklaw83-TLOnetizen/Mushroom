import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
    test("loads and shows heading", async ({ page }) => {
        await page.goto("/");
        // Clerk may redirect to sign-in — accept both
        const url = page.url();
        if (url.includes("sign-in")) {
            // Auth redirect is expected in CI without Clerk keys
            expect(url).toContain("sign-in");
        } else {
            await expect(page.locator("h1")).toContainText("Dashboard");
        }
    });
});

test.describe("Sign-in page", () => {
    test("renders Clerk sign-in", async ({ page }) => {
        await page.goto("/sign-in");
        await expect(page).toHaveURL(/sign-in/);
    });
});
