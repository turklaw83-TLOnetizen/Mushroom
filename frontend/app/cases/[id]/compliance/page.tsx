// ---- Compliance Tab -----------------------------------------------------
"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface TrustEntry {
    id: string;
    date: string;
    amount: number;
    type: string;
    description: string;
}

interface SOLClaim {
    id: string;
    claim_type: string;
    incident_date: string;
    discovery_date?: string;
    deadline: string;
    days_remaining: number | null;
    urgency: string;
    urgency_level: string;
    description?: string;
    tolling_notes?: string;
}

interface SOLData {
    claims: SOLClaim[];
    notes?: string;
}

function SOLBadge({ claim }: { claim: SOLClaim }) {
    const days = claim.days_remaining;
    if (days === null || days === undefined) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                N/A
            </span>
        );
    }
    if (days < 0) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                EXPIRED
            </span>
        );
    }
    if (days <= 30) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-800 animate-pulse dark:bg-red-900/40 dark:text-red-300">
                {days} days
            </span>
        );
    }
    if (days <= 90) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
                {days} days
            </span>
        );
    }
    return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300">
            {days} days
        </span>
    );
}

export default function CompliancePage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();

    const conflictsQuery = useQuery({
        queryKey: ["compliance", "conflicts", caseId],
        queryFn: () => api.get<Record<string, unknown>>(`/compliance/conflicts/${caseId}`, { getToken }),
    });

    const trustQuery = useQuery({
        queryKey: ["compliance", "trust", caseId],
        queryFn: () => api.get<TrustEntry[]>(`/compliance/trust/${caseId}`, { getToken }),
    });

    const solQuery = useQuery({
        queryKey: ["compliance", "sol", caseId],
        queryFn: () => api.get<SOLData>(`/compliance/sol/${caseId}`, { getToken }),
    });

    const trust = trustQuery.data ?? [];
    const trustBalance = trust.reduce((sum, e) => {
        return sum + (e.type === "deposit" ? e.amount : -e.amount);
    }, 0);

    return (
        <div className="space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Conflicts</p>
                        <p className="text-2xl font-bold mt-1">
                            {conflictsQuery.isLoading ? (
                                <Skeleton className="h-8 w-8 inline-block" />
                            ) : (
                                <Badge variant="outline" className="text-emerald-400 border-emerald-500/30 text-lg">
                                    Clear
                                </Badge>
                            )}
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Trust Balance</p>
                        <p className={`text-2xl font-bold mt-1 ${trustBalance < 0 ? "text-red-400" : ""}`}>
                            ${trustBalance.toLocaleString()}
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">SOL Claims</p>
                        <p className="text-2xl font-bold mt-1">
                            {solQuery.isLoading ? (
                                <Skeleton className="h-8 w-8 inline-block" />
                            ) : (
                                solQuery.data?.claims?.length || 0
                            )}
                        </p>
                    </CardContent>
                </Card>
            </div>

            {/* Trust Ledger */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center justify-between">
                        Trust Account Ledger
                        <Badge variant="secondary">{trust.length} entries</Badge>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {trust.length === 0 ? (
                        <p className="text-sm text-muted-foreground text-center py-6">
                            No trust account entries.
                        </p>
                    ) : (
                        <div className="space-y-2">
                            {trust.map((entry, i) => (
                                <div
                                    key={entry.id || i}
                                    className="flex items-center justify-between py-2 border-b border-border last:border-0"
                                >
                                    <div>
                                        <p className="text-sm">{entry.description}</p>
                                        <p className="text-xs text-muted-foreground">{entry.date}</p>
                                    </div>
                                    <span
                                        className={`text-sm font-bold ${entry.type === "deposit" ? "text-emerald-400" : "text-red-400"
                                            }`}
                                    >
                                        {entry.type === "deposit" ? "+" : "−"}${Math.abs(entry.amount).toFixed(2)}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* SOL Claims */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center justify-between">
                        Statute of Limitations Tracking
                        <Badge variant="secondary">
                            {solQuery.data?.claims?.length || 0} claims
                        </Badge>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {solQuery.isLoading ? (
                        <div className="space-y-3">
                            {Array.from({ length: 2 }).map((_, i) => (
                                <Skeleton key={i} className="h-16 w-full rounded-lg" />
                            ))}
                        </div>
                    ) : !solQuery.data?.claims?.length ? (
                        <p className="text-sm text-muted-foreground text-center py-6">
                            No SOL claims tracked for this case.
                        </p>
                    ) : (
                        <div className="space-y-2">
                            {solQuery.data.claims.map((claim) => (
                                <div
                                    key={claim.id}
                                    className="flex items-center justify-between py-3 border-b border-border last:border-0"
                                >
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-0.5">
                                            <span className="text-sm font-medium">
                                                {claim.claim_type}
                                            </span>
                                            <SOLBadge claim={claim} />
                                        </div>
                                        {claim.description && (
                                            <p className="text-xs text-muted-foreground">
                                                {claim.description}
                                            </p>
                                        )}
                                        <p className="text-xs text-muted-foreground mt-0.5">
                                            Incident: {claim.incident_date}
                                            {claim.deadline && claim.deadline !== "See administrative filing deadlines"
                                                ? ` \u00b7 Deadline: ${claim.deadline}`
                                                : ""}
                                        </p>
                                        {claim.tolling_notes && (
                                            <p className="text-[10px] text-muted-foreground italic mt-0.5">
                                                Tolling: {claim.tolling_notes}
                                            </p>
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
