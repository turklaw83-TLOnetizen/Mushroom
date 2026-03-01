// ---- Proxy Config (Next.js 16) ------------------------------------------
// Replaces the deprecated middleware.ts for Clerk auth routing.
// See: https://nextjs.org/docs/messages/middleware-to-proxy

import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isPublicRoute = createRouteMatcher([
    "/sign-in(.*)",
    "/sign-up(.*)",
]);

export default clerkMiddleware(async (auth, request) => {
    // Skip protection in dev mode (no Clerk keys configured)
    if (!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
        return;
    }

    if (!isPublicRoute(request)) {
        await auth.protect();
    }
});

export const config = {
    matcher: [
        // Skip Next.js internals and static files
        "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
        // Always run for API routes
        "/(api|trpc)(.*)",
    ],
};
