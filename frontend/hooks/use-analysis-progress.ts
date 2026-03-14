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
 * Uses fast polling (1.5s) when known running, slow heartbeat (10s)
 * as fallback to detect running state even when WebSocket is unavailable.
 *
 * @param caseId - The case ID
 * @param prepId - The preparation ID (null if no prep selected)
 * @param wsRunning - Whether WebSocket reports running (primary signal)
 */
export function useAnalysisProgress(
    caseId: string,
    prepId: string | null,
    wsRunning: boolean = false,
) {
    const { getToken } = useAuth();

    const query = useQuery<AnalysisProgress>({
        queryKey: ["analysis-progress", caseId, prepId],
        queryFn: () =>
            api.get<AnalysisProgress>(
                `/cases/${caseId}/analysis/status?prep_id=${prepId}`,
                { getToken },
            ),
        enabled: !!prepId,
        // Fast poll when running, slow heartbeat otherwise to detect running state
        refetchInterval: wsRunning ? 1500 : 10000,
        refetchIntervalInBackground: true,
    });

    // Detect running from HTTP response as fallback when WS is down
    const httpDetectedRunning = query.data?.status === "running";

    return {
        progress: query.data ?? IDLE_PROGRESS,
        isPolling: query.isFetching,
        isRunning: wsRunning || httpDetectedRunning,
    };
}
