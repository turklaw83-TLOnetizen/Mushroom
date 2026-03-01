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
        queryFn: () => api.get<unknown[]>(`/compliance/sol/${caseId}`, { getToken }),
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
                                (solQuery.data as unknown[])?.length || 0
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
        </div>
    );
}
