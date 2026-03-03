// ---- Dashboard Activity Feed + Stats ------------------------------------
// Shows recent activity and quick stats on the homepage.
"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import type { CaseItem } from "@/hooks/use-cases";
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

interface UpcomingDeadlinesResponse {
    count: number;
    items?: Array<{ date: string; title: string; case_id: string }>;
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
        case "case_created": return "\uD83D\uDCC1";
        case "file_uploaded": return "\uD83D\uDCCE";
        case "analysis_started": return "\uD83D\uDD2C";
        case "analysis_completed": return "\u2705";
        case "witness_added": return "\uD83D\uDC64";
        case "event_created": return "\uD83D\uDCC5";
        default: return "\uD83D\uDCDD";
    }
}

/**
 * Count deadlines within the next 7 days from loaded cases data.
 * Falls back to client-side computation if the calendar API is unavailable.
 */
function countDeadlinesThisWeek(cases?: Array<{ next_deadline?: string; next_event?: string }>): number {
    if (!cases) return 0;
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const weekFromNow = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000);

    let count = 0;
    for (const c of cases) {
        const dateStr = (c as CaseItem).next_deadline || (c as CaseItem).next_event;
        if (!dateStr) continue;
        try {
            const d = new Date(dateStr);
            if (isNaN(d.getTime())) continue;
            const target = new Date(d.getFullYear(), d.getMonth(), d.getDate());
            if (target >= today && target <= weekFromNow) {
                count++;
            }
        } catch {
            // skip invalid dates
        }
    }
    return count;
}

export function DashboardStats() {
    const { getToken } = useAuth();

    const { data: notifications } = useQuery({
        queryKey: ["notifications"],
        queryFn: () => api.get<{ items: Array<{ type: string; case_id: string }>; total: number }>("/notifications", { getToken }),
    });

    const { data: cases } = useQuery({
        queryKey: ["cases"],
        queryFn: () => api.get<{ items: CaseItem[]; total: number }>("/cases", { getToken }),
    });

    // Try the calendar API for deadline count; fall back to computing from cases
    const { data: calendarDeadlines } = useQuery({
        queryKey: ["calendar-upcoming-week"],
        queryFn: () =>
            api.get<UpcomingDeadlinesResponse>("/calendar/upcoming", {
                params: { days: 7 },
                getToken,
                noRetry: true,
            }),
        retry: false,
    });

    const totalCases = cases?.total ?? 0;
    const activeCases = cases?.items?.filter((c) => c.status === "active").length ?? 0;
    const alerts = notifications?.total ?? 0;

    // Prefer calendar API count, fall back to client-side computation from cases data
    const deadlinesThisWeek =
        calendarDeadlines?.count ?? countDeadlinesThisWeek(cases?.items);

    return (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
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
                    <p className="text-xs text-muted-foreground uppercase tracking-wider">Deadlines This Week</p>
                    <p className={`text-2xl font-bold mt-1 ${deadlinesThisWeek > 0 ? "text-red-400" : "text-muted-foreground"}`}>
                        {deadlinesThisWeek}
                    </p>
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
                        <span className="text-base mt-0.5">{"\uD83D\uDCC1"}</span>
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
