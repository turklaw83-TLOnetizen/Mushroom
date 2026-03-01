// ---- Sentry Frontend Integration ----------------------------------------
// Error tracking + performance monitoring for Next.js.
// Install: npm install @sentry/nextjs
// Set NEXT_PUBLIC_SENTRY_DSN in .env.local to enable.
//
// After installing, call initSentry() in your root layout:
//   import { initSentry } from "@/lib/sentry";
//   initSentry();

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;

export function initSentry() {
    if (!SENTRY_DSN) {
        return;
    }

    try {
        // Dynamic import — only loads if @sentry/nextjs is installed
        // @ts-expect-error — resolved at runtime when package is installed
        import("@sentry/nextjs").then((Sentry: any) => {
            Sentry.init({
                dsn: SENTRY_DSN,
                environment: process.env.NODE_ENV,
                tracesSampleRate: 0.1,
                replaysSessionSampleRate: 0,
                replaysOnErrorSampleRate: 0.5,
                beforeSend(event: any) {
                    if (event.user) {
                        event.user = { id: event.user.id };
                    }
                    return event;
                },
                ignoreErrors: [
                    "ResizeObserver loop",
                    "AbortError",
                    "Network request failed",
                    "Load failed",
                    "ChunkLoadError",
                ],
            });
            console.info("✅ Sentry frontend initialized");
        }).catch(() => {
            console.info("@sentry/nextjs not installed — run: npm install @sentry/nextjs");
        });
    } catch {
        // Sentry not available
    }
}
