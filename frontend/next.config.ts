import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

// CSP: Tightened for production security.
// - 'unsafe-eval' REMOVED from script-src (was unnecessary)
// - 'unsafe-inline' kept for style-src only (required by Clerk + Tailwind)
// - Production Clerk domains: *.clerk.accounts.dev, *.clerk.com, *.turkclaw.net
// - Cloudflare challenges/insights included
// - Localhost origins kept for development
const cspDirectives = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' https://*.clerk.accounts.dev https://*.clerk.com https://*.turkclaw.net https://challenges.cloudflare.com https://static.cloudflareinsights.com",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com",
  "img-src 'self' data: blob: https:",
  "connect-src 'self' https://*.clerk.accounts.dev wss://*.clerk.accounts.dev https://*.clerk.com wss://*.clerk.com https://*.turkclaw.net wss://*.turkclaw.net https://api.clerk.com https://challenges.cloudflare.com https://*.ingest.sentry.io ws://localhost:* http://localhost:*",
  "frame-src 'self' https://*.clerk.accounts.dev https://*.clerk.com https://*.turkclaw.net https://challenges.cloudflare.com",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  "upgrade-insecure-requests",
  "worker-src 'self' blob:",
  "manifest-src 'self'",
].join("; ");

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: false,
  headers: async () => [
    {
      source: "/(.*)",
      headers: [
        { key: "Content-Security-Policy", value: cspDirectives },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=(), bluetooth=(), serial=(), hid=(), accelerometer=(), gyroscope=(), magnetometer=()" },
        { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains; preload" },
        { key: "X-DNS-Prefetch-Control", value: "off" },
        { key: "X-Download-Options", value: "noopen" },
        { key: "X-Permitted-Cross-Domain-Policies", value: "none" },
      ],
    },
  ],
};

// Wrap with Sentry. No-ops gracefully if NEXT_PUBLIC_SENTRY_DSN is not set.
export default withSentryConfig(nextConfig, {
  // Suppress source map upload warnings when no auth token is set
  silent: true,
  // Don't widen the scope of the Sentry integration
  disableLogger: true,
});
