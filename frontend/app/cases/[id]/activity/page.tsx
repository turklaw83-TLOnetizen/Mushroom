// ---- Activity Tab — Full Implementation -----------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePresence } from "@/hooks/use-presence";
import { PresenceAvatars } from "@/components/presence-avatars";

interface ActivityEntry {
    id?: string;
    timestamp: string;
    action: string;
    user: string;
    details: string;
    category?: string;
    metadata?: Record<string, unknown>;
}

const CATEGORY_COLORS: Record<string, string> = {
    analysis: "bg-indigo-500",
    file: "bg-blue-500",
    case: "bg-emerald-500",
    user: "bg-amber-500",
    export: "bg-purple-500",
    system: "bg-gray-500",
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

function getRelativeDay(ts: string): string {
    try {
        const d = new Date(ts);
        const now = new Date();
        const diff = Math.floor((now.getTime() - d.getTime()) / 86400000);
        if (diff === 0) return "Today";
        if (diff === 1) return "Yesterday";
        return d.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
    } catch {
        return "";
    }
}

export default function ActivityPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const [filter, setFilter] = useState<string>("all");
    const [limit, setLimit] = useState(50);
    const { viewers, isConnected } = usePresence(caseId);

    const { data, isLoading, error } = useQuery({
        queryKey: ["activity", caseId, filter, limit],
        queryFn: () =>
            api.get<ActivityEntry[]>(`/cases/${caseId}/activity`, {
                params: {
                    limit,
                    ...(filter !== "all" ? { category: filter } : {}),
                },
                getToken,
            }),
    });

    const entries = data ?? [];
    const categories = ["all", "analysis", "file", "case", "user", "export", "system"];

    // Group entries by day
    const groupedEntries: Record<string, ActivityEntry[]> = {};
    entries.forEach((entry) => {
        const day = getRelativeDay(entry.timestamp);
        if (!groupedEntries[day]) groupedEntries[day] = [];
        groupedEntries[day].push(entry);
    });

    return (
        <div className="space-y-5">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">Activity Log</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Recent actions and changes for this case
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    {/* Presence indicators */}
                    {isConnected && viewers.length > 0 && (
                        <PresenceAvatars caseId={caseId} />
                    )}
                </div>
            </div>

            {/* Filter Bar */}
            <div className="flex gap-1 flex-wrap">
                {categories.map((cat) => (
                    <Button
                        key={cat}
                        variant={filter === cat ? "default" : "outline"}
                        size="sm"
                        onClick={() => setFilter(cat)}
                        className="text-xs capitalize"
                    >
                        {cat}
                    </Button>
                ))}
            </div>

            {isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 8 }).map((_, i) => (
                        <Skeleton key={i} className="h-14 w-full rounded-lg" />
                    ))}
                </div>
            ) : error ? (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        Failed to load activity log.
                    </CardContent>
                </Card>
            ) : entries.length === 0 ? (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        No activity recorded yet.
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-6">
                    {Object.entries(groupedEntries).map(([day, dayEntries]) => (
                        <div key={day}>
                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                                {day}
                            </p>
                            <div className="relative">
                                {/* Timeline line */}
                                <div className="absolute left-[19px] top-4 bottom-4 w-px bg-border" />

                                <div className="space-y-1">
                                    {dayEntries.map((entry, i) => (
                                        <div key={entry.id || i} className="flex gap-3 items-start relative">
                                            {/* Dot */}
                                            <div className="w-10 h-10 rounded-full bg-card border border-border flex items-center justify-center shrink-0 z-10">
                                                <div
                                                    className={`w-2.5 h-2.5 rounded-full ${
                                                        CATEGORY_COLORS[entry.category || "system"] ||
                                                        "bg-muted-foreground"
                                                    }`}
                                                />
                                            </div>

                                            <Card className="flex-1 hover:bg-accent/20 transition-colors">
                                                <CardContent className="py-2.5 flex items-center justify-between">
                                                    <div>
                                                        <div className="flex items-center gap-2">
                                                            <p className="text-sm font-medium">
                                                                {entry.action}
                                                            </p>
                                                            {entry.user && (
                                                                <Badge
                                                                    variant="outline"
                                                                    className="text-[10px]"
                                                                >
                                                                    {entry.user}
                                                                </Badge>
                                                            )}
                                                            {entry.category && (
                                                                <Badge
                                                                    variant="secondary"
                                                                    className="text-[10px]"
                                                                >
                                                                    {entry.category}
                                                                </Badge>
                                                            )}
                                                        </div>
                                                        {entry.details && (
                                                            <p className="text-xs text-muted-foreground mt-0.5">
                                                                {entry.details}
                                                            </p>
                                                        )}
                                                    </div>
                                                    <span className="text-xs text-muted-foreground whitespace-nowrap ml-4">
                                                        {formatTimestamp(entry.timestamp)}
                                                    </span>
                                                </CardContent>
                                            </Card>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    ))}

                    {/* Load More */}
                    {entries.length >= limit && (
                        <div className="text-center">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setLimit((l) => l + 50)}
                            >
                                Load More
                            </Button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
