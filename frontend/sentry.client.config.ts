// ---- Sentry Client-Side Configuration -----------------------------------
// Loaded automatically by @sentry/nextjs on the browser.
// Set NEXT_PUBLIC_SENTRY_DSN in .env.local to enable.

import * as Sentry from "@sentry/nextjs";

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (SENTRY_DSN) {
    Sentry.init({
        dsn: SENTRY_DSN,
        environment: process.env.NODE_ENV,

        // Performance: sample 10% of transactions
        tracesSampleRate: 0.1,

        // Session Replay: capture 0% of sessions, 50% of sessions with errors
        replaysSessionSampleRate: 0,
        replaysOnErrorSampleRate: 0.5,

        // Scrub PII — only keep user ID
        beforeSend(event) {
            if (event.user) {
                event.user = { id: event.user.id };
            }
            return event;
        },

        // Ignore noisy browser errors that aren't actionable
        ignoreErrors: [
            "ResizeObserver loop",
            "AbortError",
            "Network request failed",
            "Load failed",
            "ChunkLoadError",
            "Non-Error promise rejection",
        ],
    });
}
