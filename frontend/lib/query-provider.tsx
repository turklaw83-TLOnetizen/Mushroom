// ---- TanStack Query Provider with Global Error Handling -----------------
"use client";

import { QueryClient, QueryClientProvider, MutationCache, QueryCache } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { ApiError } from "@/lib/api-client";

function handleGlobalError(error: unknown, context: string) {
    // Don't toast on 401 (api-client handles redirect)
    if (error instanceof ApiError && error.status === 401) return;

    const message =
        error instanceof ApiError
            ? error.detail
            : error instanceof Error
                ? error.message
                : "An unexpected error occurred";

    toast.error(`${context} failed`, {
        description: message,
        duration: 5000,
    });
}

export function QueryProvider({ children }: { children: React.ReactNode }) {
    const [queryClient] = useState(
        () =>
            new QueryClient({
                queryCache: new QueryCache({
                    onError: (error, query) => {
                        // Only show toast for queries that have already loaded once
                        // (prevents initial load errors from double-toasting with error boundaries)
                        if (query.state.data !== undefined) {
                            handleGlobalError(error, "Background refresh");
                        }
                    },
                }),
                mutationCache: new MutationCache({
                    onError: (error) => {
                        handleGlobalError(error, "Request");
                    },
                }),
                defaultOptions: {
                    queries: {
                        staleTime: 30 * 1000,
                        retry: (failureCount, error) => {
                            if (error instanceof ApiError && error.status < 500) return false;
                            return failureCount < 2;
                        },
                        refetchOnWindowFocus: false,
                    },
                    mutations: {
                        retry: 0,
                    },
                },
            }),
    );

    return (
        <QueryClientProvider client={queryClient}>
            {children}
        </QueryClientProvider>
    );
}
