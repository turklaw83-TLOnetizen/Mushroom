// ---- Dev Auth Fallback ---------------------------------------------------
// Auto-fetches a JWT from the backend's PIN login when Clerk is not configured.
// Only active when NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY is not set.

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const CLERK_KEY = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

let _devToken: string | null = null;
let _devTokenPromise: Promise<string | null> | null = null;

export function isDevAuthMode(): boolean {
    return !CLERK_KEY;
}

export async function getDevToken(): Promise<string | null> {
    if (!isDevAuthMode()) return null;
    if (_devToken) return _devToken;
    if (_devTokenPromise) return _devTokenPromise;

    _devTokenPromise = (async () => {
        try {
            const res = await fetch(`${API_BASE}/api/v1/users/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ user_id: "djt-49a", pin: "" }),
            });
            if (!res.ok) return null;
            const data = await res.json();
            _devToken = data.token;
            return _devToken;
        } catch {
            return null;
        } finally {
            _devTokenPromise = null;
        }
    })();

    return _devTokenPromise;
}
