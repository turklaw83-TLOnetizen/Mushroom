// ---- Client Portal Page -------------------------------------------------
// Read-only portal view for clients. Shows case status, payment summaries,
// and recent communications via the /portal/client/{id}/status endpoint.
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

interface PortalStatus {
    client_id: string;
    client_name: string;
    cases: Array<{
        id: string;
        name: string;
        phase: string;
        sub_phase: string;
        case_type: string;
        last_updated: string;
        next_court_date: { date: string; title: string } | null;
    }>;
    payment_summary: {
        plan_id: string;
        total_amount: number;
        total_paid: number;
        remaining: number;
        status: string;
        next_due_date: string | null;
        next_due_amount: number;
    } | null;
    recent_communications: Array<{
        subject: string;
        channel: string;
        sent_at: string;
        status: string;
    }>;
}

interface ClientItem {
    id: string;
    name: string;
    first_name: string;
    last_name: string;
    email: string;
}

function formatDate(iso: string): string {
    try {
        return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch { return iso; }
}

export default function ClientPortalPage() {
    const { getToken } = useAuth();
    const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
    const [searchQ, setSearchQ] = useState("");

    // List clients for selection
    const clientsQuery = useQuery({
        queryKey: ["crm-clients-portal"],
        queryFn: () => api.get<{ items: ClientItem[] }>("/crm/clients", { getToken }),
    });

    // Fetch portal status for selected client
    const portalQuery = useQuery({
        queryKey: ["portal-status", selectedClientId],
        queryFn: () => api.get<PortalStatus>(`/portal/client/${selectedClientId}/status`, { getToken }),
        enabled: !!selectedClientId,
    });

    const clients = clientsQuery.data?.items ?? [];
    const filteredClients = searchQ
        ? clients.filter(c => {
            const name = c.name || `${c.first_name} ${c.last_name}`;
            return name.toLowerCase().includes(searchQ.toLowerCase()) ||
                   (c.email || "").toLowerCase().includes(searchQ.toLowerCase());
        })
        : clients;

    const portal = portalQuery.data;

    return (
        <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Client Portal</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Read-only case status, payments, and communications
                </p>
            </div>

            {!selectedClientId ? (
                /* Client selector */
                <div className="space-y-4">
                    <Input
                        placeholder="Search clients..."
                        value={searchQ}
                        onChange={(e) => setSearchQ(e.target.value)}
                        className="max-w-sm"
                    />
                    {clientsQuery.isLoading ? (
                        <div className="space-y-3">
                            {Array.from({ length: 3 }).map((_, i) => (
                                <Skeleton key={i} className="h-16 w-full rounded-lg" />
                            ))}
                        </div>
                    ) : filteredClients.length === 0 ? (
                        <Card className="border-dashed">
                            <CardContent className="py-8 text-center text-muted-foreground">
                                {searchQ ? "No clients match your search" : "No clients found"}
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="space-y-2">
                            {filteredClients.map(c => (
                                <Card
                                    key={c.id}
                                    className="cursor-pointer hover:border-primary/40 transition-colors"
                                    onClick={() => setSelectedClientId(c.id)}
                                >
                                    <CardContent className="py-3 flex items-center justify-between">
                                        <div>
                                            <p className="text-sm font-medium">
                                                {c.name || `${c.first_name} ${c.last_name}`.trim()}
                                            </p>
                                            {c.email && (
                                                <p className="text-xs text-muted-foreground">{c.email}</p>
                                            )}
                                        </div>
                                        <Badge variant="outline" className="text-xs">Select</Badge>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </div>
            ) : portalQuery.isLoading ? (
                <div className="space-y-3">
                    <Skeleton className="h-8 w-48" />
                    <Skeleton className="h-32 w-full" />
                    <Skeleton className="h-32 w-full" />
                </div>
            ) : portal ? (
                /* Portal Detail View */
                <div className="space-y-5">
                    <div className="flex items-center gap-3">
                        <Button variant="ghost" size="sm" onClick={() => setSelectedClientId(null)}>
                            &larr; Back
                        </Button>
                        <h2 className="text-lg font-semibold">{portal.client_name}</h2>
                    </div>

                    {/* Cases */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Cases</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {portal.cases.length === 0 ? (
                                <p className="text-sm text-muted-foreground">No linked cases</p>
                            ) : (
                                <div className="space-y-3">
                                    {portal.cases.map(c => (
                                        <div key={c.id} className="flex items-center justify-between py-2 border-b last:border-0">
                                            <div>
                                                <p className="text-sm font-medium">{c.name}</p>
                                                <div className="flex items-center gap-2 mt-0.5">
                                                    <Badge variant="outline" className="text-[10px]">{c.case_type}</Badge>
                                                    <Badge variant="secondary" className="text-[10px]">{c.phase}</Badge>
                                                    {c.sub_phase && (
                                                        <span className="text-[10px] text-muted-foreground">{c.sub_phase}</span>
                                                    )}
                                                </div>
                                            </div>
                                            {c.next_court_date && (
                                                <div className="text-right">
                                                    <p className="text-xs font-medium">{formatDate(c.next_court_date.date)}</p>
                                                    <p className="text-[10px] text-muted-foreground">{c.next_court_date.title}</p>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Payment Summary */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base">Payment Summary</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {portal.payment_summary ? (
                                    <div className="space-y-3">
                                        <div className="grid grid-cols-2 gap-3">
                                            <div>
                                                <p className="text-xs text-muted-foreground">Total</p>
                                                <p className="text-lg font-bold">${portal.payment_summary.total_amount.toLocaleString()}</p>
                                            </div>
                                            <div>
                                                <p className="text-xs text-muted-foreground">Paid</p>
                                                <p className="text-lg font-bold text-emerald-400">${portal.payment_summary.total_paid.toLocaleString()}</p>
                                            </div>
                                        </div>
                                        <Separator />
                                        <div className="flex justify-between">
                                            <span className="text-sm text-muted-foreground">Remaining</span>
                                            <span className="text-sm font-medium">${portal.payment_summary.remaining.toLocaleString()}</span>
                                        </div>
                                        {portal.payment_summary.next_due_date && (
                                            <div className="flex justify-between">
                                                <span className="text-sm text-muted-foreground">Next Due</span>
                                                <span className="text-sm">
                                                    ${portal.payment_summary.next_due_amount} on {formatDate(portal.payment_summary.next_due_date)}
                                                </span>
                                            </div>
                                        )}
                                        <Badge variant={portal.payment_summary.status === "active" ? "default" : "secondary"}>
                                            {portal.payment_summary.status}
                                        </Badge>
                                    </div>
                                ) : (
                                    <p className="text-sm text-muted-foreground">No payment plan on file</p>
                                )}
                            </CardContent>
                        </Card>

                        {/* Recent Communications */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base">Recent Communications</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {portal.recent_communications.length > 0 ? (
                                    <div className="space-y-2">
                                        {portal.recent_communications.map((comm, i) => (
                                            <div key={i} className="flex items-start gap-2 py-1.5 border-b last:border-0">
                                                <span className="text-sm" aria-hidden="true">
                                                    {comm.channel === "sms" ? "\uD83D\uDCAC" : "\uD83D\uDCE7"}
                                                </span>
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-sm truncate">{comm.subject}</p>
                                                    <p className="text-[10px] text-muted-foreground">
                                                        {formatDate(comm.sent_at)}
                                                    </p>
                                                </div>
                                                <Badge variant="outline" className="text-[10px] shrink-0">
                                                    {comm.status}
                                                </Badge>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-muted-foreground">No recent communications</p>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </div>
            ) : (
                <Card>
                    <CardContent className="py-8 text-center text-muted-foreground">
                        Failed to load portal data
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
