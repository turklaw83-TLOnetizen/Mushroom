// ---- Theme Sync Hook ----------------------------------------------------
// Listens for cross-tab localStorage changes and system color-scheme
// preference changes to keep the theme in sync everywhere.
"use client";

import { useEffect } from "react";
import { useUIStore } from "@/lib/stores/ui-store";

export function useThemeSync() {
    const setTheme = useUIStore((s) => s.setTheme);

    useEffect(() => {
        // Sync theme when another tab writes to localStorage
        function onStorage(e: StorageEvent) {
            if (e.key !== "mc-ui-store" || !e.newValue) return;
            try {
                const parsed = JSON.parse(e.newValue);
                const newTheme = parsed?.state?.theme;
                if (newTheme === "dark" || newTheme === "light") {
                    document.documentElement.classList.add("theme-transition");
                    document.documentElement.classList.toggle("dark", newTheme === "dark");
                    setTimeout(
                        () => document.documentElement.classList.remove("theme-transition"),
                        250,
                    );
                    // Update store without triggering another storage write cycle
                    useUIStore.setState({ theme: newTheme });
                }
            } catch {
                // Ignore malformed JSON
            }
        }

        // Respond to OS-level color-scheme changes (only when user has no
        // explicit stored preference)
        const mq = window.matchMedia("(prefers-color-scheme: dark)");
        function onSystemChange(e: MediaQueryListEvent) {
            try {
                const raw = localStorage.getItem("mc-ui-store");
                const stored = raw ? JSON.parse(raw) : null;
                // If the user has already persisted a preference, respect it
                if (stored?.state?.theme) return;
            } catch {
                // Treat parse failure as "no preference"
            }
            const newTheme = e.matches ? "dark" : "light";
            document.documentElement.classList.add("theme-transition");
            document.documentElement.classList.toggle("dark", newTheme === "dark");
            setTimeout(
                () => document.documentElement.classList.remove("theme-transition"),
                250,
            );
            useUIStore.setState({ theme: newTheme });
        }

        window.addEventListener("storage", onStorage);
        mq.addEventListener("change", onSystemChange);
        return () => {
            window.removeEventListener("storage", onStorage);
            mq.removeEventListener("change", onSystemChange);
        };
    }, [setTheme]);
}
