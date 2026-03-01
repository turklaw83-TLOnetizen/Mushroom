// ---- Dashboard Activity Feed + Stats ------------------------------------
// Shows recent activity and quick stats on the homepage.
"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

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

function timeAgo(ts: string): string {
    const diff = Date.now() - new Date(ts).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
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

    const { data: notifications } = useQuery({
        queryKey: ["notifications"],
        queryFn: () => api.get<{ items: Array<{ type: string; case_id: string }>; total: number }>("/notifications", { getToken }),
    });

    const { data: cases } = useQuery({
        queryKey: ["cases"],
        queryFn: () => api.get<{ items: Array<{ status: string }>; total: number }>("/cases", { getToken }),
    });

    const totalCases = cases?.total ?? 0;
    const activeCases = cases?.items?.filter((c) => c.status === "active").length ?? 0;
    const alerts = notifications?.total ?? 0;

    return (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
                <CardContent className="pt-4 pb-3">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Total Cases</p>
                    <p className="text-2xl font-bold mt-1">{totalCases}</p>
                </CardContent>
            </Card>
            <Card>
                <CardContent className="pt-4 pb-3">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Active</p>
                    <p className="text-2xl font-bold mt-1 text-green-400">{activeCases}</p>
                </CardContent>
            </Card>
            <Card>
                <CardContent className="pt-4 pb-3">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Alerts</p>
                    <p className="text-2xl font-bold mt-1 text-amber-400">{alerts}</p>
                </CardContent>
            </Card>
            <Card>
                <CardContent className="pt-4 pb-3">
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Archived</p>
                    <p className="text-2xl font-bold mt-1 text-muted-foreground">{totalCases - activeCases}</p>
                </CardContent>
            </Card>
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
                    <CardTitle className="text-sm font-medium">Recent Activity</CardTitle>
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
                    <p className="text-sm text-muted-foreground text-center py-4">
                        No recent activity
                    </p>
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
