// ---- Preparation Context ------------------------------------------------
// Shared prep selection across all case war room tabs.
"use client";

import {
    createContext,
    useContext,
    useState,
    useMemo,
    type ReactNode,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";

export interface Preparation {
    id: string;
    type: string;
    name: string;
    created_at?: string;
    last_updated?: string;
}

interface PrepContextValue {
    /** All preparations for this case */
    preparations: Preparation[];
    /** Currently selected preparation (first by default) */
    activePrepId: string | null;
    /** The active preparation object */
    activePrep: Preparation | null;
    /** Set the active preparation */
    setActivePrepId: (id: string) => void;
    /** Loading state */
    isLoading: boolean;
}

const PrepContext = createContext<PrepContextValue | null>(null);

export function PrepProvider({
    caseId,
    children,
}: {
    caseId: string;
    children: ReactNode;
}) {
    const { getToken } = useAuth();
    const [selectedPrepId, setSelectedPrepId] = useState<string | null>(null);

    const { data, isLoading } = useQuery({
        queryKey: ["cases", caseId, "preparations"],
        queryFn: () =>
            api.get<{ items: Preparation[] }>(`/cases/${caseId}/preparations`, {
                getToken,
            }),
    });

    const preparations = useMemo(() => data?.items ?? [], [data]);

    const value = useMemo<PrepContextValue>(() => {
        const activePrepId = selectedPrepId ?? preparations[0]?.id ?? null;
        const activePrep = preparations.find((p) => p.id === activePrepId) ?? null;

        return {
            preparations,
            activePrepId,
            activePrep,
            setActivePrepId: setSelectedPrepId,
            isLoading,
        };
    }, [preparations, selectedPrepId, isLoading]);

    return <PrepContext.Provider value={value}>{children}</PrepContext.Provider>;
}

export function usePrep() {
    const ctx = useContext(PrepContext);
    if (!ctx)
        throw new Error("usePrep must be used within a PrepProvider");
    return ctx;
}
