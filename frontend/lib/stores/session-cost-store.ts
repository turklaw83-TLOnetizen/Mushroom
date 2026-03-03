// ---- Session Cost Store -------------------------------------------------
// Tracks API token usage and estimated cost for the current browser session.

import { create } from "zustand";

export interface CostEntry {
    timestamp: number;
    tokens: number;
    cost: number;
    model: string;
    endpoint: string;
}

interface SessionCostState {
    totalTokens: number;
    totalCost: number;
    entries: CostEntry[];
    addEntry: (entry: Omit<CostEntry, "timestamp">) => void;
    reset: () => void;
}

export const useSessionCostStore = create<SessionCostState>()((set) => ({
    totalTokens: 0,
    totalCost: 0,
    entries: [],

    addEntry: (entry) =>
        set((s) => {
            const full: CostEntry = { ...entry, timestamp: Date.now() };
            return {
                totalTokens: s.totalTokens + entry.tokens,
                totalCost: s.totalCost + entry.cost,
                entries: [...s.entries, full],
            };
        }),

    reset: () => set({ totalTokens: 0, totalCost: 0, entries: [] }),
}));
