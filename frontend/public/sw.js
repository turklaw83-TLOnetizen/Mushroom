// ---- Service Worker for Project Mushroom Cloud --------------------------
// Provides offline support with two caching strategies:
// - CacheFirst for app shell (HTML, CSS, JS bundles)
// - NetworkFirst for API data (serve cached if offline)
// Streaming and WebSocket endpoints are never cached.

const CACHE_VERSION = "pmc-v1";
const APP_SHELL_CACHE = `app-shell-${CACHE_VERSION}`;
const DATA_CACHE = `data-${CACHE_VERSION}`;

// App shell resources to pre-cache on install
const APP_SHELL_URLS = [
    "/",
    "/manifest.json",
    "/icon-192.png",
    "/icon-512.png",
];

// Patterns that should NEVER be cached (streaming, WebSocket, auth)
const NO_CACHE_PATTERNS = [
    /\/chat\/stream/,
    /\/ws\//,
    /\/api\/v1\/ws\//,
    /clerk/,
    /\/__clerk/,
    /hot-update/,
    /_next\/webpack-hmr/,
];

// Patterns for API data routes (NetworkFirst)
const API_PATTERN = /\/api\/v1\//;

// ---- Install: pre-cache app shell --------------------------------------

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(APP_SHELL_CACHE).then((cache) => {
            return cache.addAll(APP_SHELL_URLS).catch((err) => {
                // Pre-cache is best-effort; don't block install if assets
                // aren't available yet (e.g., first deploy).
                console.warn("[SW] Pre-cache partial failure:", err);
            });
        })
    );
    // Activate immediately without waiting for old tabs to close
    self.skipWaiting();
});

// ---- Activate: clean old caches ----------------------------------------

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys
                    .filter((key) => key !== APP_SHELL_CACHE && key !== DATA_CACHE)
                    .map((key) => caches.delete(key))
            );
        })
    );
    // Take control of all open tabs immediately
    self.clients.claim();
});

// ---- Fetch: route to appropriate strategy ------------------------------

self.addEventListener("fetch", (event) => {
    const { request } = event;

    // Only handle GET requests
    if (request.method !== "GET") return;

    const url = new URL(request.url);

    // Never cache streaming/WebSocket/auth endpoints
    if (NO_CACHE_PATTERNS.some((pattern) => pattern.test(url.pathname + url.search))) {
        return;
    }

    // API requests: NetworkFirst (serve cached data if offline)
    if (API_PATTERN.test(url.pathname)) {
        event.respondWith(networkFirst(request, DATA_CACHE));
        return;
    }

    // App shell (HTML, CSS, JS, images): CacheFirst
    event.respondWith(cacheFirst(request, APP_SHELL_CACHE));
});

// ---- CacheFirst Strategy ------------------------------------------------
// Try cache first; if miss, fetch from network and cache the response.

async function cacheFirst(request, cacheName) {
    const cached = await caches.match(request);
    if (cached) return cached;

    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        // Offline and not cached — return a basic offline page
        return new Response("Offline — cached version not available", {
            status: 503,
            headers: { "Content-Type": "text/plain" },
        });
    }
}

// ---- NetworkFirst Strategy ----------------------------------------------
// Try network first; if it fails (offline), serve from cache.

async function networkFirst(request, cacheName) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        const cached = await caches.match(request);
        if (cached) return cached;

        return new Response(
            JSON.stringify({ error: "Offline", detail: "No cached data available" }),
            {
                status: 503,
                headers: { "Content-Type": "application/json" },
            }
        );
    }
}
