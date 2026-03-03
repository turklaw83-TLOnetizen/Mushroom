// ---- Theme-Aware Toaster ------------------------------------------------
// Reads theme from Zustand store so toasts match the current theme.
"use client";

import { Toaster } from "sonner";
import { useUIStore } from "@/lib/stores/ui-store";

export function ThemeAwareToaster() {
    const theme = useUIStore((s) => s.theme);
    return (
        <Toaster
            theme={theme}
            position="bottom-right"
            toastOptions={{ className: "border-border" }}
        />
    );
}
