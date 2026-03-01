// ---- Client Portal Page -------------------------------------------------
// Read-only case status portal for clients. Shows case progress,
// recent activity, invoices, and deadline calendar.
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface PortalCase {
    id: string;
    name: string;
    status: string;
    phase: string;
    case_type: string;
    client_name: string;
    updated_at: string;
}

const phaseProgress: Record<string, number> = {
    intake: 10,
    investigation: 25,
    discovery: 40,
    pre_trial: 55,
    negotiation: 65,
    mediation: 75,
    trial_prep: 85,
    trial: 95,
    settlement: 100,
    closed: 100,
};

function ProgressBar({ phase }: { phase: string }) {
    const pct = phaseProgress[phase] ?? 20;
    return (
        <div className="space-y-1">
            <div className="flex justify-between text-[10px] text-muted-foreground">
                <span>Case Progress</span>
                <span>{pct}%</span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                    className="h-full bg-gradient-to-r from-indigo-500 to-emerald-500 rounded-full transition-all duration-700"
                    style={{ width: `${pct}%` }}
                />
            </div>
        </div>
    );
}

export default function ClientPortalPage() {
    const { getToken } = useAuth();
    const [selectedCase, setSelectedCase] = useState<string | null>(null);

    const { data, isLoading } = useQuery({
        queryKey: ["cases"],
        queryFn: () => api.get<{ items: PortalCase[]; total: number }>("/cases", { getToken }),
    });

    const cases = data?.items ?? [];
    const activeCase = cases.find((c) => c.id === selectedCase);

    const { data: billingData } = useQuery({
        queryKey: ["billing", selectedCase],
        queryFn: () => api.get<{ balance: number; invoices: any[] }>(`/cases/${selectedCase}/billing/invoices`, { getToken }),
        enabled: !!selectedCase,
    });

    const { data: calendarData } = useQuery({
        queryKey: ["calendar", selectedCase],
        queryFn: () => api.get<{ items: any[] }>(`/cases/${selectedCase}/calendar`, { getToken }),
        enabled: !!selectedCase,
    });

    return (
        <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Client Portal</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Case status and documents for client review
                </p>
            </div>

            {isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 3 }).map((_, i) => (
                        <Skeleton key={i} className="h-20 w-full rounded-lg" />
                    ))}
                </div>
            ) : !selectedCase ? (
                /* Case selector */
                <div className="space-y-3">
                    <p className="text-sm font-medium">Select a case to view:</p>
                    {cases.length === 0 ? (
                        <Card>
                            <CardContent className="py-8 text-center text-muted-foreground">
                                No cases found
                            </CardContent>
                        </Card>
                    ) : (
                        cases.map((c) => (
                            <Card
                                key={c.id}
                                className="cursor-pointer hover:border-primary/40 transition-colors"
                                onClick={() => setSelectedCase(c.id)}
                            >
                                <CardContent className="pt-4 pb-3">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-sm font-medium">{c.name}</p>
                                            <p className="text-xs text-muted-foreground mt-0.5">
                                                {c.case_type} · {c.client_name}
                                            </p>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Badge variant="outline" className="text-[10px]">{c.phase}</Badge>
                                            <Badge variant={c.status === "active" ? "default" : "secondary"} className="text-[10px]">
                                                {c.status}
                                            </Badge>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))
                    )}
                </div>
            ) : (
                /* Case detail view */
                <div className="space-y-4">
                    <Button variant="ghost" size="sm" onClick={() => setSelectedCase(null)}>
                        ← Back to cases
                    </Button>

                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">{activeCase?.name}</CardTitle>
                            <CardDescription>
                                {activeCase?.case_type} · {activeCase?.client_name}
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex gap-2">
                                <Badge variant="outline">{activeCase?.phase}</Badge>
                                <Badge variant={activeCase?.status === "active" ? "default" : "secondary"}>
                                    {activeCase?.status}
                                </Badge>
                            </div>
                            <ProgressBar phase={activeCase?.phase || "intake"} />
                        </CardContent>
                    </Card>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Upcoming Events */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-sm">Upcoming Events</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {calendarData?.items?.length ? (
                                    <div className="space-y-2">
                                        {calendarData.items.slice(0, 5).map((evt: any, i: number) => (
                                            <div key={i} className="flex items-center gap-2 text-sm">
                                                <span>📅</span>
                                                <span className="truncate">{evt.title}</span>
                                                <span className="text-xs text-muted-foreground ml-auto">
                                                    {evt.date}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-xs text-muted-foreground">No upcoming events</p>
                                )}
                            </CardContent>
                        </Card>

                        {/* Billing Summary */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-sm">Billing</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {billingData ? (
                                    <div className="space-y-2">
                                        <p className="text-2xl font-bold">
                                            ${(billingData.balance || 0).toLocaleString()}
                                        </p>
                                        <p className="text-xs text-muted-foreground">Outstanding balance</p>
                                        <p className="text-xs text-muted-foreground mt-2">
                                            {billingData.invoices?.length || 0} invoice(s) on file
                                        </p>
                                    </div>
                                ) : (
                                    <p className="text-xs text-muted-foreground">Loading billing data...</p>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </div>
            )}
        </div>
    );
}
