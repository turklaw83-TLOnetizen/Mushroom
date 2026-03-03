// ---- Offline Indicator (Phase 23) ------------------------------------------
"use client";

import { useState, useEffect } from "react";
import { isOffline, onOfflineChange } from "@/lib/api-client";

export function OfflineIndicator() {
    const [offline, setOffline] = useState(false);

    useEffect(() => {
        setOffline(isOffline());
        const unsub = onOfflineChange(setOffline);
        return () => { unsub(); };
    }, []);

    if (!offline) return null;

    return (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 animate-in slide-in-from-bottom-4 fade-in duration-300">
            <div className="flex items-center gap-2 px-4 py-2 bg-amber-500/90 text-amber-950 rounded-full shadow-lg backdrop-blur-sm">
                <div className="w-2 h-2 rounded-full bg-amber-950 animate-pulse" />
                <span className="text-sm font-medium">
                    You&apos;re offline. Changes will sync when connection is restored.
                </span>
            </div>
        </div>
    );
}
