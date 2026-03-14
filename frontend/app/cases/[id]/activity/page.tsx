// ---- Activity Tab -------------------------------------------------------
"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { formatDate } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";

interface ActivityEntry {
    timestamp: string;
    action: string;
    user: string;
    details: string;
}

/** Map action types to timeline dot colors */
function actionDotColor(action: string): string {
    const a = action?.toLowerCase().replace(/\s+/g, "_") ?? "";
    if (a.includes("case_created") || a.includes("created")) return "bg-emerald-500";
    if (a.includes("file_uploaded") || a.includes("upload")) return "bg-blue-500";
    if (a.includes("analysis_started") || a.includes("analysis_completed") || a.includes("analysis")) return "bg-violet-500";
    if (a.includes("prep_created") || a.includes("preparation")) return "bg-indigo-500";
    if (a.includes("export")) return "bg-cyan-500";
    if (a.includes("delete") || a.includes("removed")) return "bg-red-400";
    if (a.includes("update") || a.includes("edited") || a.includes("modified")) return "bg-amber-500";
    return "bg-muted-foreground";
}

export default function ActivityPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();

    const { data, isLoading, error, refetch } = useQuery({
        queryKey: ["activity", caseId],
        queryFn: () =>
            api.get<ActivityEntry[]>(`/cases/${caseId}/activity`, {
                params: { limit: 100 },
                getToken,
            }),
    });

    const entries = data ?? [];

    if (error) {
        return (
            <div className="p-6">
                <Card className="border-destructive/50">
                    <CardContent className="py-8 text-center">
                        <p className="text-destructive font-medium">Failed to load data</p>
                        <p className="text-sm text-muted-foreground mt-1">{error.message || "An unexpected error occurred"}</p>
                        <Button variant="outline" size="sm" className="mt-4" onClick={() => refetch()}>
                            Try Again
                        </Button>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="space-y-5">
            <div>
                <h2 className="text-xl font-bold tracking-tight">Activity Log</h2>
                <p className="text-sm text-muted-foreground mt-0.5">
                    Recent actions and changes for this case
                </p>
            </div>

            {isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 8 }).map((_, i) => (
                        <Skeleton key={i} className="h-14 w-full rounded-lg" />
                    ))}
                </div>
            ) : entries.length === 0 ? (
                <EmptyState
                    icon="&#x1F4DD;"
                    title="No activity recorded yet"
                    description="Activity is tracked automatically. Upload files, run analysis, or make changes to see events here."
                />
            ) : (
                <div className="relative">
                    {/* Timeline line */}
                    <div className="absolute left-[19px] top-4 bottom-4 w-px bg-border" />

                    <div className="space-y-1">
                        {entries.map((entry, i) => (
                            <div key={i} className="flex gap-3 items-start relative">
                                {/* Dot — color-coded by action type */}
                                <div className="w-10 h-10 rounded-full bg-card border border-border flex items-center justify-center shrink-0 z-10">
                                    <div className={cn("w-2.5 h-2.5 rounded-full", actionDotColor(entry.action))} />
                                </div>

                                <Card className="flex-1 hover:bg-accent/20 transition-colors">
                                    <CardContent className="py-2.5 flex items-center justify-between">
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <p className="text-sm font-medium">{entry.action}</p>
                                                {entry.user && (
                                                    <Badge variant="outline" className="text-[10px]">
                                                        {entry.user}
                                                    </Badge>
                                                )}
                                            </div>
                                            {entry.details && (
                                                <p className="text-xs text-muted-foreground mt-0.5">
                                                    {entry.details}
                                                </p>
                                            )}
                                        </div>
                                        <span className="text-xs text-muted-foreground whitespace-nowrap">
                                            {formatDate(entry.timestamp)}
                                        </span>
                                    </CardContent>
                                </Card>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
