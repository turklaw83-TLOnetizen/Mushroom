// ---- Sentry Frontend Integration ----------------------------------------
// Sentry is now configured via the root-level config files:
//   sentry.client.config.ts  — browser initialization
//   sentry.server.config.ts  — Node.js server initialization
//   sentry.edge.config.ts    — edge/middleware initialization
//
// Set NEXT_PUBLIC_SENTRY_DSN in .env.local to enable.
// This file is kept for backward compatibility but is no longer needed.

export { captureException, captureMessage } from "@sentry/nextjs";
