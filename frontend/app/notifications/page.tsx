// ---- Notifications Page --------------------------------------------------
// Displays all notifications sorted by timestamp (newest first).
"use client";

import { useState } from "react";
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
    case_name?: string;
    severity: string;
    timestamp: string;
}

interface NotificationGroup {
    case_id: string;
    case_name: string;
    items: NotificationItem[];
    max_severity: string;
}

interface NotificationsResponse {
    items: NotificationItem[];
    grouped?: NotificationGroup[];
    total: number;
}

const severityColor: Record<string, string> = {
    info: "text-blue-400 border-blue-400/30 bg-blue-400/10",
    warning: "text-amber-400 border-amber-400/30 bg-amber-400/10",
    error: "text-red-400 border-red-400/30 bg-red-400/10",
    success: "text-green-400 border-green-400/30 bg-green-400/10",
    critical: "text-red-400 border-red-400/30 bg-red-400/10",
    high: "text-orange-400 border-orange-400/30 bg-orange-400/10",
    medium: "text-amber-400 border-amber-400/30 bg-amber-400/10",
    low: "text-blue-400 border-blue-400/30 bg-blue-400/10",
};

const severityLabel: Record<string, string> = {
    info: "Info",
    warning: "Warning",
    error: "Error",
    success: "Success",
    critical: "Critical",
    high: "High",
    medium: "Medium",
    low: "Low",
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

function NotificationCard({ item, showCaseLink = true }: { item: NotificationItem; showCaseLink?: boolean }) {
    return (
        <Card className="hover:bg-accent/20 transition-colors">
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
                        {showCaseLink && item.case_id && (
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
    );
}

export default function NotificationsPage() {
    const { getToken } = useAuth();
    const [viewMode, setViewMode] = useState<"grouped" | "flat">("grouped");

    const { data, isLoading } = useQuery({
        queryKey: ["notifications"],
        queryFn: () =>
            api.get<NotificationsResponse>("/notifications", { getToken }),
    });

    const items = data?.items ?? [];
    const grouped = data?.grouped ?? [];

    // Sort flat items newest first
    const sorted = [...items].sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    );

    // Sort groups by max severity then item count
    const sevOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
    const sortedGroups = [...grouped].sort((a, b) => {
        const sa = sevOrder[a.max_severity] ?? 3;
        const sb = sevOrder[b.max_severity] ?? 3;
        if (sa !== sb) return sa - sb;
        return b.items.length - a.items.length;
    });

    return (
        <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Notifications</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        {data?.total ?? 0} notification{(data?.total ?? 0) !== 1 ? "s" : ""}
                    </p>
                </div>
                {items.length > 0 && (
                    <div className="flex items-center gap-1 rounded-md border p-0.5">
                        <button
                            onClick={() => setViewMode("grouped")}
                            className={`text-xs px-2.5 py-1 rounded transition-colors ${viewMode === "grouped" ? "bg-accent text-accent-foreground font-medium" : "text-muted-foreground hover:text-foreground"}`}
                        >
                            By Case
                        </button>
                        <button
                            onClick={() => setViewMode("flat")}
                            className={`text-xs px-2.5 py-1 rounded transition-colors ${viewMode === "flat" ? "bg-accent text-accent-foreground font-medium" : "text-muted-foreground hover:text-foreground"}`}
                        >
                            All
                        </button>
                    </div>
                )}
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
            ) : viewMode === "grouped" && sortedGroups.length > 0 ? (
                <div className="space-y-5">
                    {sortedGroups.map((group) => (
                        <div key={group.case_id}>
                            {/* Group Header */}
                            <div className="flex items-center gap-2 mb-2">
                                {group.case_id !== "ungrouped" ? (
                                    <Link
                                        href={`/cases/${group.case_id}`}
                                        className="text-sm font-semibold hover:underline"
                                    >
                                        {group.case_name}
                                    </Link>
                                ) : (
                                    <span className="text-sm font-semibold">General</span>
                                )}
                                <Badge
                                    variant="outline"
                                    className={`text-[10px] ${severityColor[group.max_severity] || ""}`}
                                >
                                    {group.items.length}
                                </Badge>
                            </div>
                            {/* Group Items */}
                            <div className="space-y-1.5 pl-3 border-l-2 border-accent">
                                {group.items.map((item, i) => (
                                    <NotificationCard
                                        key={`${group.case_id}-${i}`}
                                        item={item}
                                        showCaseLink={false}
                                    />
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="space-y-2">
                    {sorted.map((item, i) => (
                        <NotificationCard key={i} item={item} />
                    ))}
                </div>
            )}
        </div>
    );
}
