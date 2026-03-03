// ---- Clerk Auth Proxy (Next.js 16) --------------------------------------
// Protects all routes except sign-in, sign-up, and API.
// Unauthenticated users are redirected to /sign-in.

import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isPublicRoute = createRouteMatcher([
    "/sign-in(.*)",
    "/sign-up(.*)",
    "/api(.*)",
]);

export default clerkMiddleware(async (auth, request) => {
    if (!isPublicRoute(request)) {
        await auth.protect({
            unauthenticatedUrl: new URL("/sign-in", request.url).toString(),
        });
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
