// ---- useAnalysisProgress Hook -------------------------------------------
// Polls the analysis status endpoint for real-time progress during analysis runs.
// Falls back to WebSocket status when available, polls HTTP otherwise.
"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";

export interface AnalysisProgress {
    status: "idle" | "running" | "complete" | "error" | "stopping";
    progress: number;
    current_module: string;
    module_description?: string;
    error: string;
    elapsed_seconds?: number;
    completed_modules?: string[];
    total_modules?: number;
    tokens_used?: number;
    [key: string]: unknown;
}

const IDLE_PROGRESS: AnalysisProgress = {
    status: "idle",
    progress: 0,
    current_module: "",
    error: "",
};

/**
 * Polls the analysis progress endpoint while analysis is running.
 * Automatically stops polling once analysis is complete/idle.
 *
 * @param caseId - The case ID
 * @param prepId - The preparation ID (null if no prep selected)
 * @param isRunning - Whether to enable polling (set by parent from WebSocket status)
 */
export function useAnalysisProgress(
    caseId: string,
    prepId: string | null,
    isRunning: boolean = false,
) {
    const { getToken } = useAuth();

    const query = useQuery<AnalysisProgress>({
        queryKey: ["analysis-progress", caseId, prepId],
        queryFn: () =>
            api.get<AnalysisProgress>(
                `/cases/${caseId}/analysis/status?prep_id=${prepId}`,
                { getToken },
            ),
        enabled: !!prepId && isRunning,
        refetchInterval: isRunning ? 1500 : false, // Poll every 1.5s while running
        refetchIntervalInBackground: true,
    });

    return {
        progress: query.data ?? IDLE_PROGRESS,
        isPolling: query.isFetching && isRunning,
    };
}
