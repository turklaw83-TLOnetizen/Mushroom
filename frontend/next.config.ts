import type { NextConfig } from "next";

// Clerk loads JS/API from a subdomain of the app's domain (clerk.turkclaw.net)
// as well as *.clerk.accounts.dev (dev) and *.clerk.com (shared prod).
const cspDirectives = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://*.clerk.accounts.dev https://*.clerk.com https://*.turkclaw.net",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com",
  "img-src 'self' data: blob: https:",
  "connect-src 'self' https://*.clerk.accounts.dev wss://*.clerk.accounts.dev https://*.clerk.com wss://*.clerk.com https://*.turkclaw.net wss://*.turkclaw.net https://api.clerk.com ws://localhost:* http://localhost:*",
  "frame-src 'self' https://*.clerk.accounts.dev https://*.clerk.com https://*.turkclaw.net",
  "object-src 'none'",
  "base-uri 'self'",
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
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      ],
    },
  ],
};

export default nextConfig;
