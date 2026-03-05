// ---- Global Error Boundary ----------------------------------------------
"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function GlobalError({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        console.error("Global error:", error);
    }, [error]);

    return (
        <html lang="en" className="dark">
            <body className="font-sans antialiased bg-background text-foreground">
                <div className="flex min-h-screen items-center justify-center p-6">
                    <div className="max-w-md text-center space-y-4">
                        <div className="text-5xl" aria-hidden="true">💥</div>
                        <h1 className="text-2xl font-bold">Something went wrong</h1>
                        <p className="text-sm text-muted-foreground">
                            {error.message || "An unexpected error occurred."}
                        </p>
                        {error.digest && (
                            <p className="text-xs text-muted-foreground font-mono">
                                Error ID: {error.digest}
                            </p>
                        )}
                        <Button onClick={reset} className="mt-4">
                            Try Again
                        </Button>
                    </div>
                </div>
            </body>
        </html>
    );
}
