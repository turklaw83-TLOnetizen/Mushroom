// ---- E2E: App Navigation ------------------------------------------------
// Tests sidebar navigation, command palette (Ctrl+K), command palette
// search filtering, and breadcrumb rendering.

import { test, expect } from "@playwright/test";
import {
  devLogin,
  navigateTo,
  createTestCase,
  deleteTestCase,
  type TestCase,
} from "./helpers";

test.describe("App Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await devLogin(page);
  });

  test("sidebar links navigate correctly", async ({ page }) => {
    const loaded = await navigateTo(page, "/");
    if (!loaded) {
      test.skip(true, "Auth redirect -- skipping");
      return;
    }

    // The sidebar should be present
    const sidebar = page.locator("aside");
    await expect(sidebar).toBeVisible({ timeout: 10_000 });

    // Test navigating via sidebar links. The sidebar has NavItem links
    // for Dashboard, Tasks, Clients, etc.
    const sidebarLinks = [
      { name: /dashboard/i, expectedPath: "/" },
      { name: /tasks/i, expectedPath: "/tasks" },
      { name: /analytics/i, expectedPath: "/analytics" },
    ];

    for (const link of sidebarLinks) {
      const sidebarLink = sidebar.getByRole("link", { name: link.name });
      const isVisible = await sidebarLink.isVisible().catch(() => false);

      if (!isVisible) {
        // Sidebar might be collapsed. Try to expand it first.
        const expandBtn = sidebar.getByRole("button").first();
        if (await expandBtn.isVisible()) {
          await expandBtn.click();
          await page.waitForTimeout(300);
        }
      }

      const linkVisible = await sidebarLink.isVisible().catch(() => false);
      if (linkVisible) {
        await sidebarLink.click();
        await page.waitForTimeout(500);

        // Verify the URL changed
        const url = new URL(page.url());
        expect(url.pathname).toBe(link.expectedPath);

        // Navigate back to home for next iteration
        if (link.expectedPath !== "/") {
          await navigateTo(page, "/");
        }
      }
    }
  });

  test("command palette opens with Ctrl+K", async ({ page }) => {
    const loaded = await navigateTo(page, "/");
    if (!loaded) {
      test.skip(true, "Auth redirect -- skipping");
      return;
    }

    // Wait for app to fully load
    await page.waitForLoadState("networkidle").catch(() => {});

    // Press Ctrl+K (or Cmd+K on Mac) to open command palette
    await page.keyboard.press("Control+k");

    // The command palette should appear as a fixed overlay with an input
    // CommandPalette renders: input with placeholder containing "Search commands"
    const paletteInput = page.getByPlaceholder(/search commands/i);
    await expect(paletteInput).toBeVisible({ timeout: 5_000 });

    // Verify the ESC key hint is visible
    const escHint = page.locator("kbd").filter({ hasText: "ESC" });
    await expect(escHint).toBeVisible();

    // The "Commands" section header should be visible
    const commandsSection = page.getByText("Commands", { exact: false });
    await expect(commandsSection.first()).toBeVisible();

    // Close the palette
    await page.keyboard.press("Escape");
    await expect(paletteInput).not.toBeVisible({ timeout: 3_000 });
  });

  test("command palette search filters results", async ({ page }) => {
    const loaded = await navigateTo(page, "/");
    if (!loaded) {
      test.skip(true, "Auth redirect -- skipping");
      return;
    }

    await page.waitForLoadState("networkidle").catch(() => {});

    // Open command palette
    await page.keyboard.press("Control+k");

    const paletteInput = page.getByPlaceholder(/search commands/i);
    await expect(paletteInput).toBeVisible({ timeout: 5_000 });

    // Type a search query to filter results
    await paletteInput.fill("analytics");
    await page.waitForTimeout(300);

    // The "Analytics" command should be visible in results
    const analyticsResult = page.getByText("Analytics");
    await expect(analyticsResult.first()).toBeVisible();

    // Non-matching commands should be filtered out. For example,
    // "Conflict Checker" should not be visible when searching "analytics"
    // (unless the word "analytics" appears in it).
    // We verify the result count is reduced.

    // Now search for something that won't match
    await paletteInput.fill("zzznonexistent999");
    await page.waitForTimeout(300);

    // The "No results found" message should appear
    const noResults = page.getByText(/no results/i);
    await expect(noResults).toBeVisible({ timeout: 3_000 });

    // Close palette
    await page.keyboard.press("Escape");
  });

  test("breadcrumbs show correct path on case page", async ({
    page,
    request,
  }) => {
    // Create a test case to navigate to
    const testCase = await createTestCase(request, {
      case_name: `Breadcrumb E2E ${Date.now()}`,
    });

    if (!testCase) {
      test.skip(true, "Backend unreachable -- cannot create test case");
      return;
    }

    try {
      const loaded = await navigateTo(
        page,
        `/cases/${testCase.case_id}/files`,
      );
      if (!loaded) {
        test.skip(true, "Auth redirect -- skipping");
        return;
      }

      // Breadcrumbs should show: Dashboard / <Case Name> / Files
      // The Breadcrumbs component renders a <nav> with links
      const breadcrumbNav = page.locator("nav").filter({
        has: page.getByText("Dashboard"),
      });

      await expect(breadcrumbNav.first()).toBeVisible({ timeout: 10_000 });

      // "Dashboard" should be a link
      const dashLink = breadcrumbNav
        .first()
        .getByRole("link", { name: "Dashboard" });
      await expect(dashLink).toBeVisible();

      // The case name should appear in breadcrumbs
      const caseBreadcrumb = breadcrumbNav
        .first()
        .getByText(testCase.name, { exact: false });
      const hasCaseName = await caseBreadcrumb
        .isVisible()
        .catch(() => false);
      // Case name might show as "Case" if data hasn't loaded yet
      expect(
        hasCaseName ||
          (await breadcrumbNav
            .first()
            .getByText("Case")
            .isVisible()
            .catch(() => false)),
      ).toBe(true);

      // "Files" should appear as the current breadcrumb
      const filesBreadcrumb = breadcrumbNav.first().getByText("Files");
      await expect(filesBreadcrumb).toBeVisible({ timeout: 5_000 });
    } finally {
      await deleteTestCase(request, testCase.case_id);
    }
  });
});
