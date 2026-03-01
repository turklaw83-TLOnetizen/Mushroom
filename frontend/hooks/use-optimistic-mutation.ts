// ---- Optimistic Mutation Hook -------------------------------------------
// Wraps useMutation with optimistic cache updates + rollback on error.
"use client";

import { useMutation, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

interface OptimisticOptions<TData, TVariables> {
    /** API method: "post" | "put" | "patch" | "delete" */
    method: "post" | "put" | "patch" | "delete";
    /** API path (e.g., "/cases/{id}/witnesses") */
    path: string | ((vars: TVariables) => string);
    /** Query keys to invalidate on success */
    invalidateKeys: QueryKey[];
    /** Query key for optimistic update */
    optimisticKey?: QueryKey;
    /** Transform cache data optimistically before server responds */
    optimisticUpdate?: (oldData: TData | undefined, variables: TVariables) => TData;
    /** Success toast message */
    successMessage?: string | ((data: unknown, vars: TVariables) => string);
    /** Error toast message */
    errorMessage?: string;
}

export function useOptimisticMutation<
    TData = unknown,
    TVariables = unknown,
>(opts: OptimisticOptions<TData, TVariables>) {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (variables: TVariables) => {
            const path = typeof opts.path === "function"
                ? opts.path(variables)
                : opts.path;

            switch (opts.method) {
                case "post":
                    return api.post(path, variables, { getToken });
                case "put":
                    return api.put(path, variables, { getToken });
                case "patch":
                    return api.patch(path, variables, { getToken });
                case "delete":
                    return api.delete(path, { getToken });
            }
        },

        onMutate: async (variables: TVariables) => {
            if (!opts.optimisticKey || !opts.optimisticUpdate) return;

            // Cancel outgoing refetches so they don't overwrite our optimistic update
            await queryClient.cancelQueries({ queryKey: opts.optimisticKey });

            // Snapshot previous value for rollback
            const previous = queryClient.getQueryData<TData>(opts.optimisticKey);

            // Optimistically update
            queryClient.setQueryData<TData>(
                opts.optimisticKey,
                (old) => opts.optimisticUpdate!(old, variables),
            );

            return { previous };
        },

        onError: (_error, _variables, context) => {
            // Rollback on error
            if (opts.optimisticKey && context?.previous !== undefined) {
                queryClient.setQueryData(opts.optimisticKey, context.previous);
            }
            if (opts.errorMessage) {
                toast.error(opts.errorMessage);
            }
        },

        onSuccess: (data, variables) => {
            if (opts.successMessage) {
                const msg = typeof opts.successMessage === "function"
                    ? opts.successMessage(data, variables)
                    : opts.successMessage;
                toast.success(msg);
            }
        },

        onSettled: () => {
            // Always refetch to ensure server truth
            opts.invalidateKeys.forEach((key) => {
                queryClient.invalidateQueries({ queryKey: key });
            });
        },
    });
}
