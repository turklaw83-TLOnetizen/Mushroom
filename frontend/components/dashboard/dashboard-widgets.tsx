// ---- Dashboard Activity Feed + Stats ------------------------------------
// Shows recent activity and quick stats on the homepage.
"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";

interface ActivityItem {
    id: string;
    type: string;
    description: string;
    timestamp: string;
    case_name?: string;
    case_id?: string;
}

interface DashboardStats {
    total_cases: number;
    active_cases: number;
    pending_tasks: number;
    upcoming_deadlines: number;
}

function activityIcon(type: string) {
    switch (type) {
        case "case_created": return "📁";
        case "file_uploaded": return "📎";
        case "analysis_started": return "🔬";
        case "analysis_completed": return "✅";
        case "witness_added": return "👤";
        case "event_created": return "📅";
        default: return "📝";
    }
}

export function DashboardStats() {
    const { getToken } = useAuth();

    const { data: notifications, isLoading: notificationsLoading } = useQuery({
        queryKey: ["notifications"],
        queryFn: () => api.get<{ items: Array<{ type: string; case_id: string }>; total: number }>("/notifications", { getToken }),
    });

    const { data: cases, isLoading: casesLoading } = useQuery({
        queryKey: ["cases"],
        queryFn: () => api.get<{ items: Array<{ status: string }>; total: number }>("/cases", { getToken }),
    });

    const isLoading = notificationsLoading || casesLoading;

    if (isLoading) {
        return (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="glass-card px-5 py-4 space-y-2">
                        <Skeleton className="h-5 w-5 rounded" />
                        <Skeleton className="h-7 w-16" />
                        <Skeleton className="h-3 w-20" />
                    </div>
                ))}
            </div>
        );
    }

    const totalCases = cases?.total ?? 0;
    const activeCases = cases?.items?.filter((c) => c.status === "active").length ?? 0;
    const alerts = notifications?.total ?? 0;

    const stats = [
        { label: "Total Cases", value: totalCases, icon: "📁", color: "text-foreground" },
        { label: "Active", value: activeCases, icon: "⚡", color: "text-emerald-400" },
        { label: "Alerts", value: alerts, icon: "🔔", color: "text-amber-400" },
        { label: "Archived", value: totalCases - activeCases, icon: "📦", color: "text-muted-foreground" },
    ];

    return (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {stats.map((stat, i) => (
                <div
                    key={stat.label}
                    className="glass-card px-5 py-4"
                    style={{ animationDelay: `${i * 0.08}s` }}
                >
                    <span className="text-lg">{stat.icon}</span>
                    <p className={`text-2xl font-extrabold tracking-tight mt-1 ${stat.color}`}>
                        {stat.value}
                    </p>
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mt-0.5">
                        {stat.label}
                    </p>
                </div>
            ))}
        </div>
    );
}

export function ActivityFeed() {
    const { getToken } = useAuth();

    const { data, isLoading } = useQuery({
        queryKey: ["dashboard-activity"],
        queryFn: () => api.get<{ items: ActivityItem[] }>("/cases?limit=10", { getToken }),
    });

    if (isLoading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="text-sm font-medium">Recent Cases</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    {Array.from({ length: 5 }).map((_, i) => (
                        <Skeleton key={i} className="h-10 w-full" />
                    ))}
                </CardContent>
            </Card>
        );
    }

    const items = data?.items ?? [];

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-sm font-medium">Recent Cases</CardTitle>
            </CardHeader>
            <CardContent className="space-y-0">
                {items.length === 0 && (
                    <EmptyState
                        icon="📋"
                        title="No recent activity"
                        description="Cases will appear here as they are created."
                    />
                )}
                {items.slice(0, 8).map((item, i) => (
                    <div
                        key={item.id || i}
                        className="flex items-start gap-3 py-2.5 border-b last:border-0"
                    >
                        <span className="text-base mt-0.5">📁</span>
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">
                                {(item as unknown as { name: string }).name || item.description || item.id}
                            </p>
                            {item.case_name && (
                                <Badge variant="outline" className="text-[10px] mt-1">
                                    {item.case_name}
                                </Badge>
                            )}
                        </div>
                    </div>
                ))}
            </CardContent>
        </Card>
    );
}
