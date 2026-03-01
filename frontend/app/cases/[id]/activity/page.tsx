// ---- Activity Tab -------------------------------------------------------
"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface ActivityEntry {
    timestamp: string;
    action: string;
    user: string;
    details: string;
}

function formatTimestamp(ts: string): string {
    try {
        const d = new Date(ts);
        return d.toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
        });
    } catch {
        return ts;
    }
}




export default function ActivityPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();

    const { data, isLoading } = useQuery({
        queryKey: ["activity", caseId],
        queryFn: () =>
            api.get<ActivityEntry[]>(`/cases/${caseId}/activity`, {
                params: { limit: 100 },
                getToken,
            }),
    });

    const entries = data ?? [];

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
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        No activity recorded yet.
                    </CardContent>
                </Card>
            ) : (
                <div className="relative">
                    {/* Timeline line */}
                    <div className="absolute left-[19px] top-4 bottom-4 w-px bg-border" />

                    <div className="space-y-1">
                        {entries.map((entry, i) => (
                            <div key={i} className="flex gap-3 items-start relative">
                                {/* Dot */}
                                <div className="w-10 h-10 rounded-full bg-card border border-border flex items-center justify-center shrink-0 z-10">
                                    <div className="w-2.5 h-2.5 rounded-full bg-muted-foreground" />
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
                                            {formatTimestamp(entry.timestamp)}
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
