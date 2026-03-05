// ---- Analysis Result Section ---------------------------------------------
// Reusable wrapper for analysis output display.
// Handles empty/loading states and provides consistent styling.
"use client";

import { type ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface ResultSectionProps {
    title: string;
    icon?: string;
    isEmpty: boolean;
    isLoading?: boolean;
    emptyMessage?: string;
    children: ReactNode;
    className?: string;
}

export function ResultSection({
    title,
    icon,
    isEmpty,
    isLoading,
    emptyMessage = "Run analysis to generate this content.",
    children,
    className,
}: ResultSectionProps) {
    if (isLoading) {
        return (
            <Card className={className}>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        {icon && <span aria-hidden="true">{icon}</span>}
                        {title}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-4 w-5/6" />
                    <Skeleton className="h-4 w-2/3" />
                </CardContent>
            </Card>
        );
    }

    if (isEmpty) {
        return (
            <Card className={`${className ?? ""} border-dashed`}>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        {icon && <span aria-hidden="true">{icon}</span>}
                        {title}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <p className="text-sm text-muted-foreground italic">{emptyMessage}</p>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className={className}>
            <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                    {icon && <span aria-hidden="true">{icon}</span>}
                    {title}
                </CardTitle>
            </CardHeader>
            <CardContent>{children}</CardContent>
        </Card>
    );
}
