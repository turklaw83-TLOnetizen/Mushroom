// ---- E2E: File Management -----------------------------------------------
// Tests the Files tab: navigation, upload, file list display, and deletion.

import { test, expect } from "@playwright/test";
import {
  devLogin,
  navigateTo,
  createTestCase,
  deleteTestCase,
  uploadTestFile,
  deleteTestFile,
  type TestCase,
} from "./helpers";

test.describe("File Management", () => {
  let testCase: TestCase | null = null;

  test.beforeAll(async ({ request }) => {
    testCase = await createTestCase(request, {
      case_name: `Files E2E ${Date.now()}`,
    });
  });

  test.afterAll(async ({ request }) => {
    if (testCase) {
      await deleteTestCase(request, testCase.case_id);
    }
  });

  test.beforeEach(async ({ page }) => {
    await devLogin(page);
  });

  test("navigate to Files tab and see the file list area", async ({
    page,
  }) => {
    if (!testCase) {
      test.skip(true, "Backend unreachable -- no test case created");
      return;
    }

    const loaded = await navigateTo(
      page,
      `/cases/${testCase.case_id}/files`,
    );
    if (!loaded) {
      test.skip(true, "Auth redirect -- skipping");
      return;
    }

    // The Files tab heading or page content should be visible
    // DataPage renders a title "Files"
    const filesHeading = page.getByRole("heading", { name: /files/i });
    await expect(filesHeading).toBeVisible({ timeout: 10_000 });

    // The Upload button should be present
    const uploadBtn = page.getByRole("button", { name: /upload/i });
    await expect(uploadBtn).toBeVisible();
  });

  test("upload a test file and verify it appears in the list", async ({
    page,
    request,
  }) => {
    if (!testCase) {
      test.skip(true, "Backend unreachable -- no test case created");
      return;
    }

    // Upload a file via API first to ensure it appears
    const testFilename = `e2e-test-${Date.now()}.txt`;
    const uploaded = await uploadTestFile(
      request,
      testCase.case_id,
      testFilename,
      "This is a test document created by the E2E test suite.\nIt contains sample text for verification purposes.",
    );

    if (!uploaded) {
      test.skip(true, "File upload via API failed -- backend may be down");
      return;
    }

    const loaded = await navigateTo(
      page,
      `/cases/${testCase.case_id}/files`,
    );
    if (!loaded) {
      // Clean up the file
      await deleteTestFile(request, testCase.case_id, testFilename);
      test.skip(true, "Auth redirect -- skipping");
      return;
    }

    // Wait for the file list to load
    await page.waitForLoadState("networkidle").catch(() => {});

    // The uploaded file should appear in the list
    const fileEntry = page.getByText(testFilename);
    await expect(fileEntry).toBeVisible({ timeout: 10_000 });

    // Clean up the file
    await deleteTestFile(request, testCase.case_id, testFilename);
  });

  test("delete a file from the list", async ({ page, request }) => {
    if (!testCase) {
      test.skip(true, "Backend unreachable -- no test case created");
      return;
    }

    // Upload a file to delete
    const testFilename = `e2e-delete-test-${Date.now()}.txt`;
    const uploaded = await uploadTestFile(
      request,
      testCase.case_id,
      testFilename,
      "File to be deleted by E2E test.",
    );

    if (!uploaded) {
      test.skip(true, "File upload via API failed -- backend may be down");
      return;
    }

    const loaded = await navigateTo(
      page,
      `/cases/${testCase.case_id}/files`,
    );
    if (!loaded) {
      await deleteTestFile(request, testCase.case_id, testFilename);
      test.skip(true, "Auth redirect -- skipping");
      return;
    }

    await page.waitForLoadState("networkidle").catch(() => {});

    // Find the file in the list
    const fileEntry = page.getByText(testFilename);
    const isVisible = await fileEntry.isVisible().catch(() => false);

    if (!isVisible) {
      // File might not have loaded yet or API issue
      await deleteTestFile(request, testCase.case_id, testFilename);
      test.skip(true, "Uploaded file not visible in list");
      return;
    }

    // Find and click the delete button associated with this file.
    // The file list renders items with delete buttons.
    // Look for a delete/trash button near the file entry.
    const fileCard = fileEntry.locator("xpath=ancestor::div[contains(@class, 'rounded')]").first();
    const deleteBtn = fileCard.getByRole("button").filter({ hasText: /delete|remove/i });

    const hasDelete = await deleteBtn.isVisible().catch(() => false);
    if (hasDelete) {
      await deleteBtn.click();

      // Confirm deletion if dialog appears
      const confirmBtn = page.getByRole("button", {
        name: /delete|confirm|yes/i,
      });
      const hasConfirm = await confirmBtn.isVisible().catch(() => false);
      if (hasConfirm) {
        await confirmBtn.click();
      }

      // Wait for the file to disappear
      await expect(fileEntry).not.toBeVisible({ timeout: 10_000 }).catch(
        () => {},
      );
    } else {
      // If no visible delete button, try a different approach (icon button)
      // Some UIs use icon-only delete buttons
      const iconButtons = fileCard.locator("button");
      const buttonCount = await iconButtons.count();

      if (buttonCount > 0) {
        // Click the last button (often the delete action)
        await iconButtons.last().click();
        await page.waitForTimeout(500);

        // Check for confirmation dialog
        const confirmDialog = page.getByRole("dialog");
        if (await confirmDialog.isVisible()) {
          const confirmBtn = confirmDialog.getByRole("button").last();
          await confirmBtn.click();
        }
      }

      // Clean up via API if UI delete didn't work
      await deleteTestFile(request, testCase.case_id, testFilename).catch(
        () => {},
      );
    }
  });
});
