// ---- Shared Tab Error Boundary ------------------------------------------
// Re-exports for all case sub-tabs so each has its own error boundary.
"use client";

import { Button } from "@/components/ui/button";

export function TabErrorFallback({
    error,
    reset,
    tabName,
}: {
    error: Error & { digest?: string };
    reset: () => void;
    tabName?: string;
}) {
    return (
        <div className="flex flex-col items-center justify-center min-h-[300px] gap-4 p-8">
            <span className="text-4xl">⚠️</span>
            <div className="text-center space-y-2 max-w-md">
                <h2 className="text-lg font-semibold">
                    {tabName ? `${tabName} failed to load` : "Something went wrong"}
                </h2>
                <p className="text-sm text-muted-foreground">
                    {error.message || "An unexpected error occurred."}
                </p>
                {error.digest && (
                    <p className="text-xs text-muted-foreground/70 font-mono">
                        {error.digest}
                    </p>
                )}
            </div>
            <Button onClick={reset} variant="outline" size="sm">
                Try again
            </Button>
        </div>
    );
}
