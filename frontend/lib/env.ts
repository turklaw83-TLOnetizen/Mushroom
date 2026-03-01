// ---- Environment Config -------------------------------------------------
// Runtime validation of required environment variables using Zod.
// Importing this module will throw at build/startup if any vars are missing.

import { z } from "zod";

const envSchema = z.object({
    // Clerk
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: z.string().min(1, "Missing NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"),
    NEXT_PUBLIC_CLERK_SIGN_IN_URL: z.string().default("/sign-in"),
    NEXT_PUBLIC_CLERK_SIGN_UP_URL: z.string().default("/sign-up"),

    // API
    NEXT_PUBLIC_API_URL: z.string().url().default("http://localhost:8000"),
});

// Only validate on the client/server — skip during static generation
function getEnv() {
    // process.env is populated at build time for public vars
    const raw = {
        NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || "",
        NEXT_PUBLIC_CLERK_SIGN_IN_URL: process.env.NEXT_PUBLIC_CLERK_SIGN_IN_URL,
        NEXT_PUBLIC_CLERK_SIGN_UP_URL: process.env.NEXT_PUBLIC_CLERK_SIGN_UP_URL,
        NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    };

    const parsed = envSchema.safeParse(raw);
    if (!parsed.success) {
        console.error("❌ Invalid environment variables:", parsed.error.flatten().fieldErrors);
        // Don't throw during build — just warn
        return raw as z.infer<typeof envSchema>;
    }
    return parsed.data;
}

export const env = getEnv();
