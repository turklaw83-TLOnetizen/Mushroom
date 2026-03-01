// ---- useAsyncAction Hook ------------------------------------------------
// Wraps an async function with loading state and error toast handling.
// For one-off actions that don't fit the React Query mutation pattern.
"use client";

import { useState, useCallback } from "react";
import { toast } from "sonner";

interface AsyncActionOptions {
    /** Error message prefix shown in toast */
    errorMessage?: string;
    /** Success message (optional) */
    successMessage?: string;
}

/**
 * Returns [execute, isLoading] for any async action with automatic
 * error handling and optional toast notifications.
 *
 * @example
 * const [handleExport, isExporting] = useAsyncAction(
 *   async (format: string) => {
 *     const blob = await api.get(`/export/${format}`, { getToken });
 *     downloadBlob(blob, `case.${format}`);
 *   },
 *   { successMessage: "Exported", errorMessage: "Export failed" },
 * );
 */
export function useAsyncAction<TArgs extends unknown[] = []>(
    action: (...args: TArgs) => Promise<void>,
    options: AsyncActionOptions = {},
): [(...args: TArgs) => Promise<void>, boolean] {
    const [isLoading, setIsLoading] = useState(false);

    const execute = useCallback(
        async (...args: TArgs) => {
            setIsLoading(true);
            try {
                await action(...args);
                if (options.successMessage) toast.success(options.successMessage);
            } catch (err) {
                toast.error(options.errorMessage || "Failed", {
                    description: err instanceof Error ? err.message : "Unknown error",
                });
            } finally {
                setIsLoading(false);
            }
        },
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [action],
    );

    return [execute, isLoading];
}
