// ---- Sentry Server-Side Configuration -----------------------------------
// Loaded automatically by @sentry/nextjs on the Node.js server.
// Set NEXT_PUBLIC_SENTRY_DSN in .env.local to enable.

import * as Sentry from "@sentry/nextjs";

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (SENTRY_DSN) {
    Sentry.init({
        dsn: SENTRY_DSN,
        environment: process.env.NODE_ENV,
        tracesSampleRate: 0.1,

        // Scrub PII
        beforeSend(event) {
            if (event.user) {
                event.user = { id: event.user.id };
            }
            if (event.request) {
                delete event.request.data;
            }
            return event;
        },
    });
}
