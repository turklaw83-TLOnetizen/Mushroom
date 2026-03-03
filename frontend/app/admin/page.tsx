"use client";
// ---- Admin Health Dashboard ---------------------------------------------
// System health, router counts, running jobs, email queue stats.
export const dynamic = "force-dynamic";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface HealthData {
    status: string;
    database: string;
    version: string;
    uptime_seconds?: number;
    latency_ms?: number;
}

interface EmailStats {
    pending?: number;
    approved?: number;
    dismissed?: number;
}

function StatCard({
    title,
    value,
    description,
    variant = "default",
}: {
    title: string;
    value: string | number;
    description?: string;
    variant?: "default" | "success" | "warning" | "danger";
}) {
    const colors = {
        default: "border-border",
        success: "border-green-500/30 bg-green-500/5",
        warning: "border-amber-500/30 bg-amber-500/5",
        danger: "border-red-500/30 bg-red-500/5",
    };
    return (
        <Card className={colors[variant]}>
            <CardContent className="pt-4 pb-3">
                <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">
                    {title}
                </p>
                <p className="text-2xl font-bold mt-1">{value}</p>
                {description && (
                    <p className="text-xs text-muted-foreground mt-1">{description}</p>
                )}
            </CardContent>
        </Card>
    );
}

function formatUptime(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (h > 24) return `${Math.floor(h / 24)}d ${h % 24}h`;
    return `${h}h ${m}m`;
}

export default function AdminPage() {
    const { getToken } = useAuth();

    const { data: health, isLoading: healthLoading } = useQuery({
        queryKey: ["health"],
        queryFn: () =>
            api.get<HealthData>("/health", { getToken, noRetry: true } as never)
                .catch(() => ({ status: "unreachable", database: "unknown", version: "unknown" } as HealthData)),
        refetchInterval: 15000,
    });

    const { data: emailStats } = useQuery({
        queryKey: ["email-stats"],
        queryFn: () => api.get<EmailStats>("/email/queue/stats", { getToken }),
    });

    const { data: notifications } = useQuery({
        queryKey: ["notifications"],
        queryFn: () => api.get<{ total: number }>("/notifications", { getToken }),
    });

    const dbStatus = health?.database === "connected" ? "success" : "danger";
    const apiStatus = health?.status === "healthy" ? "success" : "danger";

    return (
        <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Admin Dashboard</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    System health and operational status
                </p>
            </div>

            {/* Health Grid */}
            {healthLoading ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-24 rounded-lg" />
                    ))}
                </div>
            ) : (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard
                        title="API Status"
                        value={health?.status === "healthy" ? "Healthy" : "Down"}
                        variant={apiStatus as "success" | "danger"}
                    />
                    <StatCard
                        title="Database"
                        value={health?.database === "connected" ? "Connected" : "Disconnected"}
                        variant={dbStatus as "success" | "danger"}
                    />
                    <StatCard
                        title="Uptime"
                        value={health?.uptime_seconds ? formatUptime(health.uptime_seconds) : "—"}
                    />
                    <StatCard
                        title="Latency"
                        value={health?.latency_ms ? `${health.latency_ms}ms` : "—"}
                        description="DB round-trip"
                    />
                </div>
            )}

            {/* Operational Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">API Routers</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-3xl font-bold">21</p>
                        <p className="text-xs text-muted-foreground mt-1">Registered endpoints</p>
                        <div className="flex flex-wrap gap-1 mt-3">
                            {["cases", "files", "analysis", "crm", "search", "billing", "calendar", "esign", "email", "backup"].map((r) => (
                                <Badge key={r} variant="outline" className="text-[10px]">{r}</Badge>
                            ))}
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">Email Queue</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-3xl font-bold">{emailStats?.pending ?? 0}</p>
                        <p className="text-xs text-muted-foreground mt-1">Pending review</p>
                        <div className="flex gap-3 mt-3 text-xs text-muted-foreground">
                            <span>✅ {emailStats?.approved ?? 0} approved</span>
                            <span>🚫 {emailStats?.dismissed ?? 0} dismissed</span>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">Active Alerts</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-3xl font-bold">{notifications?.total ?? 0}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                            Overdue tasks, deadlines, low balances
                        </p>
                    </CardContent>
                </Card>
            </div>

            {/* System Info */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-sm font-medium">System Configuration</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                            <p className="text-muted-foreground text-xs">Version</p>
                            <p className="font-mono">{health?.version || "—"}</p>
                        </div>
                        <div>
                            <p className="text-muted-foreground text-xs">Rate Limit</p>
                            <p className="font-mono">120 req/min</p>
                        </div>
                        <div>
                            <p className="text-muted-foreground text-xs">Auth</p>
                            <p className="font-mono">Clerk JWKS</p>
                        </div>
                        <div>
                            <p className="text-muted-foreground text-xs">Database</p>
                            <p className="font-mono">PostgreSQL 16</p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
