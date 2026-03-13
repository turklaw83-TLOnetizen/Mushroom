/**
 * Mock API client for testing frontend components and hooks.
 *
 * Replaces @/lib/api-client with a vi.fn()-based mock that intercepts
 * all API calls and returns configurable responses.
 *
 * Usage:
 *   import { setupApiMock, mockApiResponse } from "../helpers/mock-api-client";
 *
 *   // At module level:
 *   setupApiMock();
 *
 *   // In individual tests:
 *   mockApiResponse("GET", "/api/v1/cases", [mockCriminalCase]);
 */
import { vi } from "vitest";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface MockRoute {
  method: HttpMethod;
  urlPattern: string;
  response: unknown;
  status: number;
}

const _routes: MockRoute[] = [];
let _defaultResponse: unknown = {};

/**
 * Sets up the API client mock. Call at module level.
 */
export function setupApiMock() {
  vi.mock("@/lib/api-client", () => ({
    apiClient: {
      get: vi.fn().mockImplementation((url: string) => _handleRequest("GET", url)),
      post: vi.fn().mockImplementation((url: string, body?: unknown) => _handleRequest("POST", url, body)),
      put: vi.fn().mockImplementation((url: string, body?: unknown) => _handleRequest("PUT", url, body)),
      patch: vi.fn().mockImplementation((url: string, body?: unknown) => _handleRequest("PATCH", url, body)),
      delete: vi.fn().mockImplementation((url: string) => _handleRequest("DELETE", url)),
    },
  }));
}

/**
 * Register a mock response for a specific method + URL pattern.
 */
export function mockApiResponse(
  method: HttpMethod,
  urlPattern: string,
  response: unknown,
  status = 200,
) {
  _routes.push({ method, urlPattern, response, status });
}

/**
 * Set the default response for unmatched routes.
 */
export function setDefaultApiResponse(response: unknown) {
  _defaultResponse = response;
}

/**
 * Clear all registered mock routes.
 */
export function clearApiMocks() {
  _routes.length = 0;
  _defaultResponse = {};
}

function _handleRequest(method: HttpMethod, url: string, _body?: unknown): Promise<unknown> {
  // Search routes in reverse (last registered wins)
  for (let i = _routes.length - 1; i >= 0; i--) {
    const route = _routes[i];
    if (route.method === method && url.includes(route.urlPattern)) {
      if (route.status >= 400) {
        return Promise.reject(new Error(`API Error ${route.status}`));
      }
      return Promise.resolve(route.response);
    }
  }
  return Promise.resolve(_defaultResponse);
}
