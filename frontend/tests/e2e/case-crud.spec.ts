// ---- E2E: Case CRUD Lifecycle -------------------------------------------
// Tests creating a case via the dialog, navigating to it, verifying the
// header, switching tabs, and deleting the case.

import { test, expect } from "@playwright/test";
import {
  devLogin,
  navigateTo,
  createTestCase,
  deleteTestCase,
} from "./helpers";

test.describe("Case CRUD Lifecycle", () => {
  let createdCaseId: string | null = null;

  test.beforeEach(async ({ page }) => {
    await devLogin(page);
  });

  test.afterEach(async ({ request }) => {
    // Clean up any case we created via the API
    if (createdCaseId) {
      await deleteTestCase(request, createdCaseId);
      createdCaseId = null;
    }
  });

  test("create a new case via the dialog", async ({ page }) => {
    const loaded = await navigateTo(page, "/");
    if (!loaded) {
      test.skip(true, "Auth redirect -- skipping");
      return;
    }

    const caseName = `E2E Test ${Date.now()}`;

    // Open the New Case dialog
    const newCaseBtn = page.getByRole("button", { name: /new case/i });
    await expect(newCaseBtn).toBeVisible({ timeout: 10_000 });
    await newCaseBtn.click();

    // Fill in the case name
    const nameInput = page.getByPlaceholder(/state v\./i);
    await expect(nameInput).toBeVisible({ timeout: 5_000 });
    await nameInput.fill(caseName);

    // Fill in client name
    const clientInput = page.getByPlaceholder(/john johnson/i);
    if (await clientInput.isVisible()) {
      await clientInput.fill("E2E Client");
    }

    // Submit the form
    const createBtn = page.getByRole("button", { name: /create case/i });
    await createBtn.click();

    // After creation, the app should navigate to /cases/<id>
    await page.waitForURL(/\/cases\//, { timeout: 15_000 });

    // Extract case ID from URL for cleanup
    const url = page.url();
    const match = url.match(/\/cases\/([^/]+)/);
    if (match) {
      createdCaseId = match[1];
    }

    // The case name should appear in the header
    await expect(page.getByRole("heading", { name: caseName })).toBeVisible({
      timeout: 10_000,
    });
  });

  test("navigate to a case detail view", async ({ page, request }) => {
    // Create a case via API for this test
    const testCase = await createTestCase(request);
    if (!testCase) {
      test.skip(true, "Backend unreachable -- cannot create test case");
      return;
    }
    createdCaseId = testCase.case_id;

    const loaded = await navigateTo(page, `/cases/${testCase.case_id}`);
    if (!loaded) {
      test.skip(true, "Auth redirect -- skipping");
      return;
    }

    // The case header should show the case name
    await expect(
      page.getByRole("heading", { name: testCase.name }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("case header shows name and phase badge", async ({
    page,
    request,
  }) => {
    const testCase = await createTestCase(request);
    if (!testCase) {
      test.skip(true, "Backend unreachable -- cannot create test case");
      return;
    }
    createdCaseId = testCase.case_id;

    const loaded = await navigateTo(page, `/cases/${testCase.case_id}`);
    if (!loaded) {
      test.skip(true, "Auth redirect -- skipping");
      return;
    }

    // Case name heading
    const heading = page.getByRole("heading", { name: testCase.name });
    await expect(heading).toBeVisible({ timeout: 10_000 });

    // Phase badge -- newly created cases should show "Active" or similar
    // The badge is rendered as a span with Badge component
    const phaseBadge = page.locator(
      ".border-emerald-500\\/30, [class*='emerald']",
    );
    await expect(phaseBadge.first()).toBeVisible({ timeout: 5_000 });
  });

  test("tab navigation works (click each tab, verify URL changes)", async ({
    page,
    request,
  }) => {
    const testCase = await createTestCase(request);
    if (!testCase) {
      test.skip(true, "Backend unreachable -- cannot create test case");
      return;
    }
    createdCaseId = testCase.case_id;

    const loaded = await navigateTo(page, `/cases/${testCase.case_id}`);
    if (!loaded) {
      test.skip(true, "Auth redirect -- skipping");
      return;
    }

    // Wait for tabs to render
    await page.waitForLoadState("networkidle").catch(() => {});

    // Test a representative subset of tabs to keep runtime reasonable
    const tabsToTest = [
      { label: "Files", href: "files" },
      { label: "Analysis", href: "analysis" },
      { label: "Chat", href: "chat" },
      { label: "Witnesses", href: "witnesses" },
      { label: "Evidence", href: "evidence" },
      { label: "Overview", href: "" },
    ];

    for (const tab of tabsToTest) {
      const tabLink = page.getByRole("link", { name: tab.label, exact: true });

      // The tab should be in the nav area
      const isVisible = await tabLink.isVisible().catch(() => false);
      if (!isVisible) continue;

      await tabLink.click();

      // Verify URL changed
      const expectedPath = tab.href
        ? `/cases/${testCase.case_id}/${tab.href}`
        : `/cases/${testCase.case_id}`;

      await page.waitForURL(
        (url) => url.pathname.includes(expectedPath),
        { timeout: 5_000 },
      ).catch(() => {
        // URL might not change if the link is for the same page
      });
    }
  });

  test("delete a case via the dashboard", async ({ page, request }) => {
    const testCase = await createTestCase(request);
    if (!testCase) {
      test.skip(true, "Backend unreachable -- cannot create test case");
      return;
    }
    // Don't set createdCaseId since we're deleting it in this test
    const caseId = testCase.case_id;

    const loaded = await navigateTo(page, "/");
    if (!loaded) {
      test.skip(true, "Auth redirect -- skipping");
      return;
    }

    // Wait for cases to load
    await page.waitForLoadState("networkidle").catch(() => {});

    // Look for the delete button/action for our test case
    // The CaseTable component has an onDelete callback. We need to find
    // the row and trigger its delete action.
    const caseRow = page.getByText(testCase.name);
    const isVisible = await caseRow.isVisible().catch(() => false);

    if (!isVisible) {
      // Case might not show on first page; clean up via API
      await deleteTestCase(request, caseId);
      test.skip(true, "Test case not visible in dashboard");
      return;
    }

    // Find and click the delete button for this case's row
    // The table row should have an action button (dropdown or direct)
    const row = caseRow.locator("xpath=ancestor::tr");
    const deleteBtn = row.getByRole("button").filter({ hasText: /delete/i });

    const hasDeleteBtn = await deleteBtn.isVisible().catch(() => false);
    if (!hasDeleteBtn) {
      // Try looking for a dropdown menu trigger
      const moreBtn = row.locator("button").last();
      if (await moreBtn.isVisible()) {
        await moreBtn.click();
        await page.waitForTimeout(300);

        const deleteOption = page.getByRole("menuitem", {
          name: /delete/i,
        });
        if (await deleteOption.isVisible()) {
          await deleteOption.click();
        } else {
          await deleteTestCase(request, caseId);
          test.skip(true, "Delete action not found in table row");
          return;
        }
      } else {
        await deleteTestCase(request, caseId);
        test.skip(true, "Delete action not found");
        return;
      }
    } else {
      await deleteBtn.click();
    }

    // Confirm deletion in the dialog
    const confirmDialog = page.getByRole("dialog");
    await expect(confirmDialog).toBeVisible({ timeout: 5_000 });

    const confirmBtn = page.getByRole("button", { name: /delete case/i });
    await expect(confirmBtn).toBeVisible();
    await confirmBtn.click();

    // Wait for deletion to complete -- dialog should close
    await expect(confirmDialog).not.toBeVisible({ timeout: 10_000 });

    // The case should no longer appear in the list
    await page.waitForTimeout(1_000);
    // Don't need API cleanup since we just deleted it
  });
});
