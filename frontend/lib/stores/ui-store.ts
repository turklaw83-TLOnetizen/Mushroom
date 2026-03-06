// ---- UI Store -----------------------------------------------------------
// Client-only UI state managed by Zustand with localStorage persistence.

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UIState {
    sidebarOpen: boolean;
    theme: "light" | "dark";
    commandPaletteOpen: boolean;
    pinnedCaseIds: string[];
    toggleSidebar: () => void;
    setSidebarOpen: (open: boolean) => void;
    setTheme: (t: "light" | "dark") => void;
    setCommandPaletteOpen: (open: boolean) => void;
    pinCase: (id: string) => void;
    unpinCase: (id: string) => void;
}

export const useUIStore = create<UIState>()(
    persist(
        (set) => ({
            sidebarOpen: true,
            theme: "dark",
            commandPaletteOpen: false,
            pinnedCaseIds: [],
            toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
            setSidebarOpen: (open) => set({ sidebarOpen: open }),
            setTheme: (theme) => set({ theme }),
            setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
            pinCase: (id) =>
                set((s) => {
                    if (s.pinnedCaseIds.includes(id) || s.pinnedCaseIds.length >= 5) return s;
                    return { pinnedCaseIds: [...s.pinnedCaseIds, id] };
                }),
            unpinCase: (id) =>
                set((s) => ({
                    pinnedCaseIds: s.pinnedCaseIds.filter((cid) => cid !== id),
                })),
        }),
        {
            name: "mc-ui-store",
            partialize: (state) => ({
                sidebarOpen: state.sidebarOpen,
                theme: state.theme,
                pinnedCaseIds: state.pinnedCaseIds,
            }),
        },
    ),
);
