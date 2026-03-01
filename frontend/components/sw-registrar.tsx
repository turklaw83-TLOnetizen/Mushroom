// ---- Service Worker Registrar -------------------------------------------
// Client component that registers the service worker on mount.
// Placed in the root layout so it runs once per session.
"use client";

import { useEffect } from "react";

export function ServiceWorkerRegistrar() {
    useEffect(() => {
        if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
            navigator.serviceWorker
                .register("/sw.js")
                .then((registration) => {
                    console.log("[SW] Registered:", registration.scope);
                })
                .catch((err) => {
                    console.warn("[SW] Registration failed:", err);
                });
        }
    }, []);

    return null;
}
