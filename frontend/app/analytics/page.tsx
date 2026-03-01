// ---- Analytics Dashboard ------------------------------------------------
// Charts and stats — case distribution, revenue trends, workload.
// Pure React charts without external dependencies.
"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface CaseItem {
    id: string;
    name: string;
    status: string;
    case_type: string;
    case_category: string;
    phase: string;
}

function BarChart({ data, label }: { data: Record<string, number>; label: string }) {
    const max = Math.max(...Object.values(data), 1);
    const entries = Object.entries(data).sort(([, a], [, b]) => b - a);

    return (
        <div>
            <p className="text-xs font-medium text-muted-foreground mb-3 uppercase tracking-wider">{label}</p>
            <div className="space-y-2">
                {entries.map(([key, value]) => (
                    <div key={key} className="flex items-center gap-3">
                        <span className="text-xs w-28 truncate text-muted-foreground">{key || "Other"}</span>
                        <div className="flex-1 bg-muted rounded-full h-5 overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 rounded-full transition-all duration-500 flex items-center justify-end px-2"
                                style={{ width: `${Math.max((value / max) * 100, 8)}%` }}
                            >
                                <span className="text-[10px] font-bold text-white">{value}</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

function DonutChart({ data, label }: { data: Record<string, number>; label: string }) {
    const total = Object.values(data).reduce((a, b) => a + b, 0) || 1;
    const colors = ["#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd", "#ddd6fe", "#7c3aed", "#4f46e5"];
    let cumulative = 0;

    return (
        <div className="flex items-center gap-6">
            <svg width="120" height="120" viewBox="0 0 120 120">
                {Object.entries(data).map(([, value], i) => {
                    const percent = value / total;
                    const startAngle = cumulative * 360;
                    cumulative += percent;
                    const endAngle = cumulative * 360;
                    const largeArc = percent > 0.5 ? 1 : 0;
                    const startX = 60 + 50 * Math.cos((Math.PI * (startAngle - 90)) / 180);
                    const startY = 60 + 50 * Math.sin((Math.PI * (startAngle - 90)) / 180);
                    const endX = 60 + 50 * Math.cos((Math.PI * (endAngle - 90)) / 180);
                    const endY = 60 + 50 * Math.sin((Math.PI * (endAngle - 90)) / 180);
                    return (
                        <path
                            key={i}
                            d={`M60,60 L${startX},${startY} A50,50 0 ${largeArc},1 ${endX},${endY} Z`}
                            fill={colors[i % colors.length]}
                            className="transition-all duration-300"
                        />
                    );
                })}
                <circle cx="60" cy="60" r="30" className="fill-background" />
                <text x="60" y="56" textAnchor="middle" className="fill-foreground text-lg font-bold" fontSize="18">
                    {total}
                </text>
                <text x="60" y="72" textAnchor="middle" className="fill-muted-foreground" fontSize="10">
                    {label}
                </text>
            </svg>
            <div className="space-y-1">
                {Object.entries(data).map(([key, value], i) => (
                    <div key={key} className="flex items-center gap-2 text-xs">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ background: colors[i % colors.length] }} />
                        <span className="text-muted-foreground">{key || "Other"}</span>
                        <span className="font-medium ml-auto">{value}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

export default function AnalyticsPage() {
    const { getToken } = useAuth();

    const { data: casesData, isLoading } = useQuery({
        queryKey: ["cases"],
        queryFn: () => api.get<{ items: CaseItem[]; total: number }>("/cases", { getToken }),
    });

    const cases = casesData?.items ?? [];

    // Compute distributions
    const byStatus: Record<string, number> = {};
    const byType: Record<string, number> = {};
    const byCategory: Record<string, number> = {};
    const byPhase: Record<string, number> = {};

    cases.forEach((c) => {
        byStatus[c.status || "unknown"] = (byStatus[c.status || "unknown"] || 0) + 1;
        byType[c.case_type || "other"] = (byType[c.case_type || "other"] || 0) + 1;
        byCategory[c.case_category || "other"] = (byCategory[c.case_category || "other"] || 0) + 1;
        byPhase[c.phase || "intake"] = (byPhase[c.phase || "intake"] || 0) + 1;
    });

    if (isLoading) {
        return (
            <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
                <Skeleton className="h-8 w-48" />
                <div className="grid grid-cols-2 gap-6">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-64 rounded-lg" />
                    ))}
                </div>
            </div>
        );
    }

    return (
        <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Case portfolio insights — {cases.length} total cases
                </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card>
                    <CardHeader>
                        <CardTitle className="text-sm">Cases by Status</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <DonutChart data={byStatus} label="total" />
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="text-sm">Cases by Phase</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <DonutChart data={byPhase} label="phases" />
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="text-sm">Cases by Type</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <BarChart data={byType} label="Case Types" />
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="text-sm">Cases by Category</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <BarChart data={byCategory} label="Categories" />
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
