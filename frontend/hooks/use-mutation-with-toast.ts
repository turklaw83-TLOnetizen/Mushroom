// ---- useMutationWithToast ------------------------------------------------
// Centralized mutation wrapper that handles toast notifications, query
// invalidation, and loading state. Eliminates boilerplate across all tabs.
"use client";

import { useMutation, useQueryClient, type InvalidateQueryFilters } from "@tanstack/react-query";
import { toast } from "sonner";

interface MutationOptions<TInput, TResult = unknown> {
    /** The async function to call */
    mutationFn: (input: TInput) => Promise<TResult>;
    /** Success message shown in toast */
    successMessage?: string;
    /** Error message prefix shown in toast */
    errorMessage?: string;
    /** Query keys to invalidate on success */
    invalidateKeys?: InvalidateQueryFilters["queryKey"][];
    /** Callback on success (after invalidation) */
    onSuccess?: (result: TResult, input: TInput) => void;
    /** Callback on error */
    onError?: (error: Error) => void;
}

/**
 * Wraps React Query's useMutation with automatic toast notifications
 * and query invalidation. Replaces the try/catch/toast/invalidate pattern
 * used across all tabs.
 *
 * @example
 * const createWitness = useMutationWithToast({
 *   mutationFn: (data) => api.post(`/witnesses`, data, { getToken }),
 *   successMessage: "Witness added",
 *   invalidateKeys: [["witnesses", caseId]],
 *   onSuccess: () => setDialogOpen(false),
 * });
 *
 * // Use: createWitness.mutate(data)
 * // Loading: createWitness.isPending
 */
export function useMutationWithToast<TInput, TResult = unknown>({
    mutationFn,
    successMessage = "Saved",
    errorMessage = "Failed",
    invalidateKeys = [],
    onSuccess,
    onError,
}: MutationOptions<TInput, TResult>) {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn,
        onSuccess: (result, input) => {
            if (successMessage) toast.success(successMessage);
            invalidateKeys.forEach((key) => {
                queryClient.invalidateQueries({ queryKey: key });
            });
            onSuccess?.(result, input);
        },
        onError: (err: Error) => {
            toast.error(errorMessage, { description: err.message });
            onError?.(err);
        },
    });
}
