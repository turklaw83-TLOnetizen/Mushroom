import type { NextConfig } from "next";

// CSP: Tightened for production security.
// - 'unsafe-eval' REMOVED from script-src (was unnecessary)
// - 'unsafe-inline' kept for style-src only (required by Clerk + Tailwind)
// - Production Clerk domain (*.turkclaw.net) included
// - Localhost origins kept for development
const cspDirectives = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' https://clerk.accounts.dev https://*.clerk.accounts.dev https://*.turkclaw.net",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com",
  "img-src 'self' data: blob: https:",
  "connect-src 'self' https://*.clerk.accounts.dev wss://*.clerk.accounts.dev https://api.clerk.com https://*.turkclaw.net ws://localhost:* http://localhost:*",
  "frame-src 'self' https://clerk.accounts.dev https://*.turkclaw.net",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  "upgrade-insecure-requests",
].join("; ");

const nextConfig: NextConfig = {
  output: "standalone",
  headers: async () => [
    {
      source: "/(.*)",
      headers: [
        { key: "Content-Security-Policy", value: cspDirectives },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains; preload" },
        { key: "X-DNS-Prefetch-Control", value: "off" },
        { key: "X-Download-Options", value: "noopen" },
        { key: "X-Permitted-Cross-Domain-Policies", value: "none" },
      ],
    },
  ],
};

export default nextConfig;
