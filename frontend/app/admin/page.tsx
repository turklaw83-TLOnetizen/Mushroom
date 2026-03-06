"use client";
// ---- Admin Dashboard ----------------------------------------------------
// System health, user management, router counts, email queue stats.
export const dynamic = "force-dynamic";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { HealthData, UserItem, TeamStats } from "@/types/api";

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

const ROLE_OPTIONS = ["admin", "attorney", "paralegal"];

function UserManagementSection() {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [editingUserId, setEditingUserId] = useState<string | null>(null);

    const { data: usersData, isLoading } = useQuery({
        queryKey: ["admin-users"],
        queryFn: () =>
            api.get<{ items: UserItem[]; total: number }>("/users?include_inactive=true&per_page=100", { getToken }),
    });

    const { data: teamStats } = useQuery({
        queryKey: ["team-stats"],
        queryFn: () => api.get<TeamStats>("/users/team-stats", { getToken }),
    });

    const updateUser = useMutation({
        mutationFn: ({ userId, updates }: { userId: string; updates: { role?: string } }) =>
            api.patch<{ status: string }>(`/users/${userId}`, updates, { getToken }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["admin-users"] });
            queryClient.invalidateQueries({ queryKey: ["team-stats"] });
            toast.success("User updated");
            setEditingUserId(null);
        },
        onError: () => toast.error("Failed to update user"),
    });

    const users = usersData?.items ?? [];

    return (
        <div className="space-y-4">
            {/* Team Stats Row */}
            {teamStats && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    <StatCard title="Total Users" value={teamStats.total_users} />
                    <StatCard title="Active" value={teamStats.active_users} variant="success" />
                    <StatCard title="Admins" value={teamStats.admins} />
                    <StatCard title="Attorneys" value={teamStats.attorneys} />
                    <StatCard title="Paralegals" value={teamStats.paralegals} />
                </div>
            )}

            {/* User Table */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Team Members</CardTitle>
                    <CardDescription>Manage user roles and access</CardDescription>
                </CardHeader>
                <CardContent>
                    {isLoading ? (
                        <div className="space-y-2">
                            {Array.from({ length: 3 }).map((_, i) => (
                                <Skeleton key={i} className="h-12 w-full" />
                            ))}
                        </div>
                    ) : users.length === 0 ? (
                        <p className="text-sm text-muted-foreground py-4">No users found</p>
                    ) : (
                        <div className="divide-y">
                            {users.map((u) => (
                                <div key={u.id} className="flex items-center justify-between py-3">
                                    <div className="flex items-center gap-3">
                                        <div className="h-9 w-9 rounded-full bg-primary/10 flex items-center justify-center text-sm font-bold text-primary">
                                            {u.initials || u.name?.slice(0, 2).toUpperCase() || "?"}
                                        </div>
                                        <div>
                                            <p className="text-sm font-medium">
                                                {u.name || u.id}
                                                {!u.active && (
                                                    <Badge variant="secondary" className="ml-2 text-[10px]">
                                                        Inactive
                                                    </Badge>
                                                )}
                                            </p>
                                            <p className="text-xs text-muted-foreground">{u.email || u.id}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {editingUserId === u.id ? (
                                            <Select
                                                defaultValue={u.role}
                                                onValueChange={(role) => {
                                                    updateUser.mutate({ userId: u.id, updates: { role } });
                                                }}
                                            >
                                                <SelectTrigger className="w-32 h-8 text-xs">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {ROLE_OPTIONS.map((r) => (
                                                        <SelectItem key={r} value={r} className="text-xs capitalize">
                                                            {r}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        ) : (
                                            <>
                                                <Badge
                                                    variant={u.role === "admin" ? "default" : "outline"}
                                                    className="text-xs capitalize"
                                                >
                                                    {u.role}
                                                </Badge>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="h-7 text-xs"
                                                    onClick={() => setEditingUserId(u.id)}
                                                >
                                                    Edit
                                                </Button>
                                            </>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
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
                    System health, user management, and operational status
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

            {/* User Management */}
            <UserManagementSection />

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
                            <span>{emailStats?.approved ?? 0} approved</span>
                            <span>{emailStats?.dismissed ?? 0} dismissed</span>
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

            {/* Admin Tools */}
            <div className="space-y-2">
                <h2 className="text-lg font-semibold tracking-tight">Admin Tools</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <Link href="/admin/gdpr">
                        <Card className="hover:border-primary/30 transition-colors cursor-pointer">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium">🔒 GDPR Compliance</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <p className="text-xs text-muted-foreground">
                                    Data export, right to erasure, and consent management
                                </p>
                            </CardContent>
                        </Card>
                    </Link>
                    <Link href="/admin/batch">
                        <Card className="hover:border-primary/30 transition-colors cursor-pointer">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium">📦 Batch Operations</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <p className="text-xs text-muted-foreground">
                                    Bulk status updates, assignments, exports, and archiving
                                </p>
                            </CardContent>
                        </Card>
                    </Link>
                    <Link href="/admin/analytics">
                        <Card className="hover:border-primary/30 transition-colors cursor-pointer">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium">📊 Cost Analytics</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <p className="text-xs text-muted-foreground">
                                    LLM costs, analysis quality scores, and usage tracking
                                </p>
                            </CardContent>
                        </Card>
                    </Link>
                </div>
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
