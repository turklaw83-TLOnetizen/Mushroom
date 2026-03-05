// ---- Theme-Aware Clerk Provider -----------------------------------------
// Reads theme from Zustand store and passes to Clerk's appearance config.
// Uses a build-time stub key when no real key is available (prerendering safety).
"use client";

import { ClerkProvider } from "@clerk/nextjs";
import { dark } from "@clerk/themes";
import { useUIStore } from "@/lib/stores/ui-store";

// Use real key when available; fall back to a stub for build-time prerendering.
// The stub key lets Clerk hooks initialize without crashing — they return
// unauthenticated state, which is fine during static generation.
// Key format: pk_test_ + base64("domain.clerk.accounts.dev$")
const clerkKey =
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ||
    "pk_test_YnVpbGQuY2xlcmsuYWNjb3VudHMuZGV2JA";

// In production, Clerk JS is served through an nginx proxy at /__clerk
// instead of the clerk.turkclaw.net subdomain (avoids DNS verification delays).
const clerkProxyUrl = process.env.NEXT_PUBLIC_CLERK_PROXY_URL || undefined;

export function ThemeAwareClerk({ children }: { children: React.ReactNode }) {
    const theme = useUIStore((s) => s.theme);

    return (
        <ClerkProvider
            publishableKey={clerkKey}
            proxyUrl={clerkProxyUrl}
            appearance={{
                baseTheme: theme === "dark" ? dark : undefined,
                variables: { colorPrimary: "#6366f1" },
            }}
        >
            {children}
        </ClerkProvider>
    );
}
