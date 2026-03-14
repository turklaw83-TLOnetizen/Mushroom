// ---- Tab Persistence Hook ---------------------------------------------------
// Remembers the last-visited tab for each case in localStorage. On initial
// navigation to a case root, automatically redirects to the remembered tab.
"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

const STORAGE_KEY = "mc-last-tabs";
const MAX_ENTRIES = 50;

/**
 * Save the current tab for a case, and optionally redirect to the
 * last-used tab when the user lands on the case root (overview).
 */
export function useTabPersistence(caseId: string) {
    const pathname = usePathname();
    const router = useRouter();
    const basePath = `/cases/${caseId}`;

    // Save current tab to localStorage whenever it changes
    useEffect(() => {
        if (!pathname.startsWith(basePath)) return;
        // Extract the tab path segment (everything after /cases/[id])
        const tabPath = pathname.slice(basePath.length) || "";
        if (!tabPath) return; // Don't save the overview (empty path = default landing)
        try {
            const stored: Record<string, string> = JSON.parse(
                localStorage.getItem(STORAGE_KEY) || "{}",
            );
            stored[caseId] = tabPath;
            // Keep only the last N cases to avoid unbounded growth
            const keys = Object.keys(stored);
            if (keys.length > MAX_ENTRIES) {
                delete stored[keys[0]];
            }
            localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
        } catch {
            // localStorage may be unavailable (SSR, private browsing, quota)
        }
    }, [pathname, caseId, basePath]);

    // On initial mount at case root, redirect to the last-used tab
    useEffect(() => {
        // Only redirect if we're at the case root (overview)
        if (pathname !== basePath) return;
        try {
            const stored: Record<string, string> = JSON.parse(
                localStorage.getItem(STORAGE_KEY) || "{}",
            );
            const lastTab = stored[caseId];
            if (lastTab && lastTab !== "") {
                router.replace(`${basePath}${lastTab}`);
            }
        } catch {
            // localStorage may be unavailable
        }
        // Only run on mount — intentionally omitting router from deps
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
}
