// ---- UI Store -----------------------------------------------------------
// Client-only UI state managed by Zustand with localStorage persistence.

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UIState {
    sidebarOpen: boolean;
    theme: "light" | "dark";
    commandPaletteOpen: boolean;
    toggleSidebar: () => void;
    setSidebarOpen: (open: boolean) => void;
    setTheme: (t: "light" | "dark") => void;
    setCommandPaletteOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>()(
    persist(
        (set) => ({
            sidebarOpen: true,
            theme: "dark",
            commandPaletteOpen: false,
            toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
            setSidebarOpen: (open) => set({ sidebarOpen: open }),
            setTheme: (theme) => set({ theme }),
            setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
        }),
        {
            name: "mc-ui-store",
            partialize: (state) => ({
                sidebarOpen: state.sidebarOpen,
                theme: state.theme,
            }),
        },
    ),
);
