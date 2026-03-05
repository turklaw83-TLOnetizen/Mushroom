// ---- Notifications Page --------------------------------------------------
// Displays all notifications sorted by timestamp (newest first).
"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { api } from "@/lib/api-client";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface NotificationItem {
    type: string;
    title: string;
    detail: string;
    case_id?: string;
    severity: string;
    timestamp: string;
}

interface NotificationsResponse {
    items: NotificationItem[];
    total: number;
}

const severityColor: Record<string, string> = {
    info: "text-blue-400 border-blue-400/30 bg-blue-400/10",
    warning: "text-amber-400 border-amber-400/30 bg-amber-400/10",
    error: "text-red-400 border-red-400/30 bg-red-400/10",
    success: "text-green-400 border-green-400/30 bg-green-400/10",
};

const severityLabel: Record<string, string> = {
    info: "Info",
    warning: "Warning",
    error: "Error",
    success: "Success",
};

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

export default function NotificationsPage() {
    const { getToken } = useAuth();

    const { data, isLoading } = useQuery({
        queryKey: ["notifications"],
        queryFn: () =>
            api.get<NotificationsResponse>("/notifications", { getToken }),
    });

    const items = data?.items ?? [];

    // Sort newest first
    const sorted = [...items].sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    );

    return (
        <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Notifications</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        {data?.total ?? 0} notification{(data?.total ?? 0) !== 1 ? "s" : ""}
                    </p>
                </div>
            </div>

            {isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 6 }).map((_, i) => (
                        <Skeleton key={i} className="h-20 w-full rounded-lg" />
                    ))}
                </div>
            ) : sorted.length === 0 ? (
                <Card className="border-dashed">
                    <CardContent className="py-16 text-center text-muted-foreground">
                        No notifications yet.
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-2">
                    {sorted.map((item, i) => (
                        <Card key={i} className="hover:bg-accent/20 transition-colors">
                            <CardContent className="py-3">
                                <div className="flex items-start justify-between gap-4">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <p className="text-sm font-medium truncate">
                                                {item.title}
                                            </p>
                                            <Badge
                                                variant="outline"
                                                className={`text-[10px] shrink-0 ${severityColor[item.severity] || ""}`}
                                            >
                                                {severityLabel[item.severity] || item.severity}
                                            </Badge>
                                        </div>
                                        {item.detail && (
                                            <p className="text-xs text-muted-foreground line-clamp-2">
                                                {item.detail}
                                            </p>
                                        )}
                                        {item.case_id && (
                                            <Link
                                                href={`/cases/${item.case_id}`}
                                                className="text-xs text-primary hover:underline mt-1 inline-block"
                                            >
                                                View case
                                            </Link>
                                        )}
                                    </div>
                                    <span className="text-xs text-muted-foreground whitespace-nowrap shrink-0">
                                        {formatTimestamp(item.timestamp)}
                                    </span>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
