// ---- E2E Test Helpers ---------------------------------------------------
// Shared utilities for Playwright E2E tests.
// Handles dev-mode auth, API interactions, and test data cleanup.

import { Page, expect, APIRequestContext } from "@playwright/test";

// ---- Constants ----------------------------------------------------------

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const APP_BASE =
  process.env.BASE_URL ?? "http://localhost:3000";

/** Default dev-mode user credentials (matches lib/dev-auth.ts) */
const DEV_USER_ID = "djt-49a";
const DEV_USER_PIN = "";

// ---- Auth Helpers -------------------------------------------------------

/**
 * Authenticate in dev mode by fetching a JWT from the backend's PIN login
 * endpoint and storing it as a cookie / localStorage token so the frontend
 * API client picks it up automatically.
 *
 * When NEXT_PUBLIC_AUTH_DISABLED=true (or Clerk keys are absent), the
 * frontend's `dev-auth.ts` module auto-fetches a token. For E2E tests we
 * replicate that flow and inject the token into localStorage so every
 * subsequent navigation in the same browser context is authenticated.
 */
export async function devLogin(page: Page): Promise<string | null> {
  try {
    const response = await page.request.post(
      `${API_BASE}/api/v1/users/login`,
      {
        data: { user_id: DEV_USER_ID, pin: DEV_USER_PIN },
        headers: { "Content-Type": "application/json" },
      },
    );

    if (!response.ok()) {
      console.warn(
        `[e2e helpers] Dev login failed with status ${response.status()}`,
      );
      return null;
    }

    const body = await response.json();
    const token: string | null = body.token ?? null;

    if (token) {
      // Store the token so the frontend dev-auth module finds it
      await page.addInitScript((t: string) => {
        (window as unknown as Record<string, string>).__dev_token = t;
      }, token);
    }

    return token;
  } catch (err) {
    console.warn("[e2e helpers] Dev login request failed:", err);
    return null;
  }
}

/**
 * Fetch a raw dev JWT using the Playwright APIRequestContext (no browser
 * needed). Useful for direct API calls in test setup/teardown.
 */
export async function getDevToken(
  request: APIRequestContext,
): Promise<string | null> {
  try {
    const response = await request.post(
      `${API_BASE}/api/v1/users/login`,
      {
        data: { user_id: DEV_USER_ID, pin: DEV_USER_PIN },
        headers: { "Content-Type": "application/json" },
      },
    );
    if (!response.ok()) return null;
    const body = await response.json();
    return body.token ?? null;
  } catch {
    return null;
  }
}

// ---- Navigation Helpers -------------------------------------------------

/**
 * Navigate to a page and wait for the app to settle. Handles the case where
 * Clerk redirects unauthenticated users to /sign-in.
 *
 * Returns `true` if the target page loaded, `false` if redirected to sign-in.
 */
export async function navigateTo(
  page: Page,
  path: string,
): Promise<boolean> {
  await page.goto(path, { waitUntil: "domcontentloaded" });

  // Give the app a moment to potentially redirect
  await page.waitForTimeout(500);

  const url = page.url();
  if (url.includes("sign-in")) {
    return false;
  }

  // Wait for network to settle (but don't fail if it times out)
  await page.waitForLoadState("networkidle").catch(() => {});
  return true;
}

/**
 * Determine whether the app is running in dev-auth mode (no Clerk).
 * Checks if the homepage redirects to sign-in.
 */
export async function isDevAuth(page: Page): Promise<boolean> {
  const loaded = await navigateTo(page, "/");
  return loaded; // If it loaded without redirect, we're in dev-auth mode
}

// ---- Case CRUD Helpers --------------------------------------------------

export interface TestCase {
  case_id: string;
  name: string;
}

/**
 * Create a test case via the API. Returns the case_id.
 */
export async function createTestCase(
  request: APIRequestContext,
  overrides: {
    case_name?: string;
    description?: string;
    case_type?: string;
    client_name?: string;
  } = {},
): Promise<TestCase | null> {
  const token = await getDevToken(request);
  const caseName =
    overrides.case_name ??
    `E2E Test Case ${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

  try {
    const response = await request.post(`${API_BASE}/api/v1/cases`, {
      data: {
        case_name: caseName,
        description: overrides.description ?? "Created by E2E test suite",
        case_type: overrides.case_type ?? "criminal",
        client_name: overrides.client_name ?? "Test Client",
      },
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!response.ok()) {
      console.warn(
        `[e2e helpers] Failed to create test case: ${response.status()}`,
      );
      return null;
    }

    const body = await response.json();
    return { case_id: body.case_id, name: caseName };
  } catch (err) {
    console.warn("[e2e helpers] Create test case failed:", err);
    return null;
  }
}

/**
 * Delete a test case via the API. Used for cleanup.
 */
export async function deleteTestCase(
  request: APIRequestContext,
  caseId: string,
): Promise<boolean> {
  const token = await getDevToken(request);

  try {
    const response = await request.delete(
      `${API_BASE}/api/v1/cases/${caseId}`,
      {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      },
    );
    return response.ok();
  } catch {
    return false;
  }
}

// ---- File Helpers -------------------------------------------------------

/**
 * Upload a test file to a case via the API.
 */
export async function uploadTestFile(
  request: APIRequestContext,
  caseId: string,
  filename: string,
  content: string,
): Promise<boolean> {
  const token = await getDevToken(request);

  try {
    const response = await request.post(
      `${API_BASE}/api/v1/cases/${caseId}/files`,
      {
        multipart: {
          files: {
            name: filename,
            mimeType: "text/plain",
            buffer: Buffer.from(content, "utf-8"),
          },
        },
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      },
    );
    return response.ok();
  } catch {
    return false;
  }
}

/**
 * Delete a file from a case via the API.
 */
export async function deleteTestFile(
  request: APIRequestContext,
  caseId: string,
  filename: string,
): Promise<boolean> {
  const token = await getDevToken(request);

  try {
    const response = await request.delete(
      `${API_BASE}/api/v1/cases/${caseId}/files/${encodeURIComponent(filename)}`,
      {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      },
    );
    return response.ok();
  } catch {
    return false;
  }
}

// ---- Assertion Helpers --------------------------------------------------

/**
 * Skip the test if the backend is not reachable.
 */
export async function skipIfBackendDown(
  request: APIRequestContext,
): Promise<void> {
  try {
    const response = await request.get(`${API_BASE}/api/v1/health`);
    if (!response.ok()) {
      throw new Error(`Backend health check returned ${response.status()}`);
    }
  } catch {
    // If health endpoint doesn't exist, try a basic connectivity check
    try {
      await request.get(API_BASE);
    } catch {
      throw new Error(
        "Backend is not reachable. Skipping E2E tests that require API.",
      );
    }
  }
}

/**
 * Wait for a specific heading to appear on the page.
 */
export async function waitForHeading(
  page: Page,
  text: string | RegExp,
  timeout = 10_000,
): Promise<void> {
  const heading = page.getByRole("heading", { name: text });
  await expect(heading).toBeVisible({ timeout });
}
