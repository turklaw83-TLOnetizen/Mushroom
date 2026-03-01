// ---- API Client ---------------------------------------------------------
// Typed fetch wrapper with Clerk auth, retry logic, and offline detection.

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---- Retry Configuration ------------------------------------------------
const RETRY_STATUS_CODES = [429, 500, 502, 503, 504];
const MAX_RETRIES = 3;
const BASE_DELAY_MS = 500;

export class ApiError extends Error {
    status: number;
    detail: string;
    requestId: string;

    constructor(status: number, detail: string, requestId: string = "") {
        super(detail);
        this.name = "ApiError";
        this.status = status;
        this.detail = detail;
        this.requestId = requestId;
    }
}

type RequestOptions = {
    method?: string;
    body?: unknown;
    params?: Record<string, string | number | boolean | undefined>;
    headers?: Record<string, string>;
    getToken?: () => Promise<string | null>;
    /** Disable retry for this request */
    noRetry?: boolean;
};

// ---- Offline Detection --------------------------------------------------

let _isOffline = false;
const _offlineListeners = new Set<(offline: boolean) => void>();

export function onOfflineChange(cb: (offline: boolean) => void) {
    _offlineListeners.add(cb);
    return () => _offlineListeners.delete(cb);
}

export function isOffline() {
    return _isOffline;
}

function _setOffline(value: boolean) {
    if (_isOffline !== value) {
        _isOffline = value;
        _offlineListeners.forEach((cb) => cb(value));
    }
}

if (typeof window !== "undefined") {
    window.addEventListener("online", () => _setOffline(false));
    window.addEventListener("offline", () => _setOffline(true));
}

// ---- Core Request Function with Retry -----------------------------------

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { method = "GET", body, params, headers = {}, getToken, noRetry } = options;

    // Build URL with query params
    const url = new URL(`/api/v1${path}`, API_BASE);
    if (params) {
        Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined) {
                url.searchParams.set(key, String(value));
            }
        });
    }

    // Attach Clerk token if available
    if (getToken) {
        const token = await getToken();
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }
    }

    const fetchOptions: RequestInit = {
        method,
        headers: {
            "Content-Type": "application/json",
            ...headers,
        },
    };

    if (body && method !== "GET") {
        fetchOptions.body = JSON.stringify(body);
    }

    const maxAttempts = noRetry ? 1 : MAX_RETRIES;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
        try {
            const response = await fetch(url.toString(), fetchOptions);

            // Success — mark online
            _setOffline(false);

            if (response.ok) {
                if (response.status === 204 || response.headers.get("content-length") === "0") {
                    return {} as T;
                }
                return response.json();
            }

            // Auto-redirect to sign-in on 401
            if (response.status === 401 && typeof window !== "undefined") {
                window.location.href = "/sign-in";
                return new Promise<T>(() => { });
            }

            // Retry on transient errors
            if (RETRY_STATUS_CODES.includes(response.status) && attempt < maxAttempts - 1) {
                const retryAfter = response.headers.get("Retry-After");
                const delay = retryAfter
                    ? parseInt(retryAfter, 10) * 1000
                    : BASE_DELAY_MS * Math.pow(2, attempt);
                await new Promise((r) => setTimeout(r, delay));
                continue;
            }

            // Non-retryable error
            let detail = `HTTP ${response.status}`;
            let requestId = "";
            try {
                const errorData = await response.json();
                detail = errorData.detail || detail;
                requestId = errorData.request_id || "";
            } catch { /* Non-JSON */ }

            throw new ApiError(response.status, detail, requestId);
        } catch (err) {
            // Network error (offline, DNS, etc.)
            if (err instanceof ApiError) throw err;

            if (attempt < maxAttempts - 1) {
                _setOffline(true);
                await new Promise((r) => setTimeout(r, BASE_DELAY_MS * Math.pow(2, attempt)));
                continue;
            }

            _setOffline(true);
            throw new ApiError(0, "Network error — check your connection");
        }
    }

    throw new ApiError(0, "Request failed after retries");
}

// ---- Convenience Methods ------------------------------------------------

export const api = {
    get: <T>(path: string, options?: Omit<RequestOptions, "method">) =>
        request<T>(path, { ...options, method: "GET" }),

    post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
        request<T>(path, { ...options, method: "POST", body }),

    put: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
        request<T>(path, { ...options, method: "PUT", body }),

    patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
        request<T>(path, { ...options, method: "PATCH", body }),

    delete: <T>(path: string, options?: Omit<RequestOptions, "method">) =>
        request<T>(path, { ...options, method: "DELETE" }),

    // File upload (multipart) — no retry for uploads
    upload: async <T>(
        path: string,
        files: File[],
        getToken?: () => Promise<string | null>,
    ): Promise<T> => {
        const url = new URL(`/api/v1${path}`, API_BASE);
        const formData = new FormData();
        files.forEach((f) => formData.append("files", f));

        const headers: Record<string, string> = {};
        if (getToken) {
            const token = await getToken();
            if (token) headers["Authorization"] = `Bearer ${token}`;
        }

        const response = await fetch(url.toString(), {
            method: "POST",
            headers,
            body: formData,
        });

        if (!response.ok) {
            let detail = `HTTP ${response.status}`;
            try {
                const errorData = await response.json();
                detail = errorData.detail || detail;
            } catch { /* ignore */ }
            throw new ApiError(response.status, detail);
        }

        return response.json();
    },
};
