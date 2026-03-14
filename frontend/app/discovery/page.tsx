// ---- Cross-Case Discovery Dashboard ----------------------------------------
// Aggregates discovery requests across all civil cases.
"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { CrossCaseDiscoveryItem } from "@/types/api";

const STATUS_COLORS: Record<string, string> = {
    draft: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    served: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    response_pending: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
    response_received: "bg-green-500/15 text-green-400 border-green-500/30",
    deficient: "bg-red-500/15 text-red-400 border-red-500/30",
    motion_to_compel: "bg-orange-500/15 text-orange-400 border-orange-500/30",
    complete: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
};

const TYPE_LABELS: Record<string, string> = {
    interrogatories: "Interrogatories",
    rfp: "RFP",
    rfa: "RFA",
};

interface DashboardResponse {
    items: CrossCaseDiscoveryItem[];
    stats: {
        total_requests: number;
        overdue: number;
        pending_response: number;
        due_within_7_days: number;
    };
}

export default function DiscoveryDashboardPage() {
    const { getToken } = useAuth();

    const { data, isLoading } = useQuery<DashboardResponse>({
        queryKey: ["discovery-dashboard"],
        queryFn: () => api.get<DashboardResponse>("/discovery/dashboard", { getToken }),
    });

    if (isLoading) {
        return (
            <div className="space-y-6 p-6">
                <Skeleton className="h-8 w-72" />
                <div className="grid grid-cols-4 gap-4">
                    {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24" />)}
                </div>
                <Skeleton className="h-96" />
            </div>
        );
    }

    const stats = data?.stats;
    const items = data?.items || [];

    return (
        <div className="space-y-6 p-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Discovery Command Center</h1>
                <p className="text-muted-foreground mt-1">Cross-case discovery tracking for all civil matters</p>
            </div>

            {/* Stats Cards */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card className="glass-card">
                        <CardContent className="pt-4 pb-3 px-4">
                            <p className="text-xs text-muted-foreground uppercase tracking-wider">Total Requests</p>
                            <p className="text-2xl font-bold mt-1">{stats.total_requests}</p>
                        </CardContent>
                    </Card>
                    <Card className="glass-card">
                        <CardContent className="pt-4 pb-3 px-4">
                            <p className="text-xs text-muted-foreground uppercase tracking-wider">Overdue</p>
                            <p className={`text-2xl font-bold mt-1 ${stats.overdue > 0 ? "text-red-400" : ""}`}>
                                {stats.overdue}
                            </p>
                        </CardContent>
                    </Card>
                    <Card className="glass-card">
                        <CardContent className="pt-4 pb-3 px-4">
                            <p className="text-xs text-muted-foreground uppercase tracking-wider">Pending Response</p>
                            <p className="text-2xl font-bold mt-1">{stats.pending_response}</p>
                        </CardContent>
                    </Card>
                    <Card className="glass-card">
                        <CardContent className="pt-4 pb-3 px-4">
                            <p className="text-xs text-muted-foreground uppercase tracking-wider">Due in 7 Days</p>
                            <p className={`text-2xl font-bold mt-1 ${stats.due_within_7_days > 0 ? "text-yellow-400" : ""}`}>
                                {stats.due_within_7_days}
                            </p>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* Requests Table */}
            <Card className="glass-card">
                <CardHeader>
                    <CardTitle className="text-lg">All Active Discovery</CardTitle>
                </CardHeader>
                <CardContent>
                    {items.length === 0 ? (
                        <p className="text-center text-muted-foreground py-8">
                            No active discovery requests across your civil cases.
                        </p>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="sticky top-0 z-10 bg-background">
                                    <tr className="border-b border-border text-left text-muted-foreground">
                                        <th className="py-2 px-3">Case</th>
                                        <th className="py-2 px-3">Direction</th>
                                        <th className="py-2 px-3">Type</th>
                                        <th className="py-2 px-3">Title</th>
                                        <th className="py-2 px-3">Status</th>
                                        <th className="py-2 px-3">Served</th>
                                        <th className="py-2 px-3">Due</th>
                                        <th className="py-2 px-3">Items</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {items.map((item) => (
                                        <tr
                                            key={`${item.case_id}-${item.request_id}`}
                                            className={`border-b border-border/50 hover:bg-muted/20 ${
                                                item.is_overdue ? "bg-red-500/5" : ""
                                            }`}
                                        >
                                            <td className="py-2 px-3">
                                                <Link
                                                    href={`/cases/${item.case_id}/discovery`}
                                                    className="text-brand-indigo hover:underline"
                                                >
                                                    {item.case_name}
                                                </Link>
                                            </td>
                                            <td className="py-2 px-3">
                                                <Badge variant="secondary" className="text-xs">
                                                    {item.direction === "outbound" ? "Sent" : "Received"}
                                                </Badge>
                                            </td>
                                            <td className="py-2 px-3">
                                                {TYPE_LABELS[item.request_type] || item.request_type}
                                            </td>
                                            <td className="py-2 px-3 font-medium">{item.title}</td>
                                            <td className="py-2 px-3">
                                                <Badge
                                                    variant="outline"
                                                    className={STATUS_COLORS[item.status] || ""}
                                                >
                                                    {item.status.replace(/_/g, " ")}
                                                </Badge>
                                            </td>
                                            <td className="py-2 px-3 text-muted-foreground">
                                                {item.date_served || "—"}
                                            </td>
                                            <td className="py-2 px-3">
                                                <span className={item.is_overdue ? "text-red-400 font-semibold" : ""}>
                                                    {item.response_due || "—"}
                                                </span>
                                                {item.days_until_due !== null && item.days_until_due < 0 && (
                                                    <span className="text-xs text-red-400 ml-1">
                                                        ({Math.abs(item.days_until_due)}d overdue)
                                                    </span>
                                                )}
                                                {item.days_until_due !== null && item.days_until_due >= 0 && item.days_until_due <= 7 && (
                                                    <span className="text-xs text-yellow-400 ml-1">
                                                        ({item.days_until_due}d left)
                                                    </span>
                                                )}
                                            </td>
                                            <td className="py-2 px-3 text-muted-foreground">
                                                {item.item_count}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
