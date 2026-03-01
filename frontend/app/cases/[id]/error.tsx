// ---- Case Error Boundary ------------------------------------------------
"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function CaseError({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    return (
        <div className="flex items-center justify-center p-12">
            <Card className="max-w-md w-full border-destructive/50">
                <CardContent className="pt-6 text-center space-y-4">
                    <div className="text-4xl">⚠️</div>
                    <h2 className="text-lg font-semibold">Something went wrong</h2>
                    <p className="text-sm text-muted-foreground">
                        {error.message || "An unexpected error occurred while loading this case."}
                    </p>
                    {error.digest && (
                        <p className="text-xs text-muted-foreground font-mono">
                            Error ID: {error.digest}
                        </p>
                    )}
                    <Button onClick={reset} variant="outline">
                        Try again
                    </Button>
                </CardContent>
            </Card>
        </div>
    );
}
