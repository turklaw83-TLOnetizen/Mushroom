// ---- Tab Prefetch Helpers -----------------------------------------------
// Prefetch tab data on hover for instant tab switches.
"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";
import { api } from "@/lib/api-client";

/**
 * Returns a prefetch function that preloads tab data into the query cache
 * when the user hovers over a tab link.
 */
export function useTabPrefetch(caseId: string, prepId: string | null) {
    const queryClient = useQueryClient();
    const { getToken } = useAuth();

    const prefetch = useCallback(
        (tabHref: string) => {
            switch (tabHref) {
                case "/files":
                    queryClient.prefetchQuery({
                        queryKey: ["cases", caseId, "files"],
                        queryFn: () => api.get(`/cases/${caseId}/files`, { getToken }),
                        staleTime: 30_000,
                    });
                    break;

                case "/witnesses":
                    if (prepId) {
                        queryClient.prefetchQuery({
                            queryKey: ["witnesses", caseId, prepId],
                            queryFn: () =>
                                api.get(`/cases/${caseId}/preparations/${prepId}/witnesses`, {
                                    getToken,
                                }),
                            staleTime: 30_000,
                        });
                    }
                    break;

                case "/evidence":
                    if (prepId) {
                        queryClient.prefetchQuery({
                            queryKey: ["evidence", caseId, prepId],
                            queryFn: () =>
                                api.get(`/cases/${caseId}/preparations/${prepId}/evidence`, {
                                    getToken,
                                }),
                            staleTime: 30_000,
                        });
                    }
                    break;

                case "/strategy":
                    if (prepId) {
                        queryClient.prefetchQuery({
                            queryKey: ["strategy", caseId, prepId],
                            queryFn: () =>
                                api.get(`/cases/${caseId}/preparations/${prepId}/strategy`, {
                                    getToken,
                                }),
                            staleTime: 30_000,
                        });
                    }
                    break;

                case "/billing":
                    queryClient.prefetchQuery({
                        queryKey: ["billing", "time", caseId],
                        queryFn: () => api.get(`/billing/time/${caseId}`, { getToken }),
                        staleTime: 30_000,
                    });
                    queryClient.prefetchQuery({
                        queryKey: ["billing", "summary", caseId],
                        queryFn: () =>
                            api.get(`/billing/summary/${caseId}`, { getToken }),
                        staleTime: 30_000,
                    });
                    break;

                case "/calendar":
                    queryClient.prefetchQuery({
                        queryKey: ["calendar", caseId],
                        queryFn: () =>
                            api.get("/calendar/events", {
                                params: { case_id: caseId },
                                getToken,
                            }),
                        staleTime: 30_000,
                    });
                    break;

                case "/compliance":
                    queryClient.prefetchQuery({
                        queryKey: ["compliance", "trust", caseId],
                        queryFn: () =>
                            api.get(`/compliance/trust/${caseId}`, { getToken }),
                        staleTime: 30_000,
                    });
                    break;

                case "/activity":
                    queryClient.prefetchQuery({
                        queryKey: ["activity", caseId],
                        queryFn: () =>
                            api.get(`/cases/${caseId}/activity`, {
                                params: { limit: 100 },
                                getToken,
                            }),
                        staleTime: 30_000,
                    });
                    break;

                case "/documents":
                    queryClient.prefetchQuery({
                        queryKey: ["documents", caseId],
                        queryFn: () =>
                            api.get(`/documents/drafts/${caseId}`, { getToken }),
                        staleTime: 30_000,
                    });
                    break;

                default:
                    break;
            }
        },
        [queryClient, caseId, prepId, getToken],
    );

    return prefetch;
}
