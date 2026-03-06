"use client";
// ---- GDPR Compliance Tools -----------------------------------------------
// Data portability (Article 20), right to erasure (Article 17), consent status.
export const dynamic = "force-dynamic";

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";

// ---- Types ----------------------------------------------------------------

interface ConsentEntry {
    purpose: string;
    granted: boolean;
    granted_at?: string;
    revoked_at?: string;
}

interface ConsentData {
    client_id: string;
    consents: ConsentEntry[];
}

interface ErasureResult {
    status: string;
    message: string;
    records_deleted?: number;
}

// ---- Main Page ------------------------------------------------------------

export default function GDPRPage() {
    const { getToken } = useAuth();
    const [clientId, setClientId] = useState("");
    const [exportData, setExportData] = useState<Record<string, unknown> | null>(null);
    const [erasureResult, setErasureResult] = useState<ErasureResult | null>(null);

    const trimmedId = clientId.trim();

    // Auto-load consent status when client ID is entered
    const consentQuery = useQuery({
        queryKey: ["gdpr-consent", trimmedId],
        queryFn: () => api.get<ConsentData>(`/gdpr/consent/${trimmedId}`, { getToken }),
        enabled: trimmedId.length > 0,
    });

    // Data export mutation
    const exportMutation = useMutationWithToast<void, Record<string, unknown>>({
        mutationFn: () => api.get<Record<string, unknown>>(`/gdpr/export/${trimmedId}`, { getToken }),
        successMessage: "Data export retrieved",
        errorMessage: "Failed to export data",
        onSuccess: (result) => setExportData(result),
    });

    // Erasure mutation
    const erasureMutation = useMutationWithToast<void, ErasureResult>({
        mutationFn: () => api.post<ErasureResult>(`/gdpr/forget/${trimmedId}`, {}, { getToken }),
        successMessage: "Erasure request processed",
        errorMessage: "Erasure request failed",
        invalidateKeys: [["gdpr-consent", trimmedId]],
        onSuccess: (result) => {
            setErasureResult(result);
            setExportData(null);
        },
    });

    const handleDownloadJson = useCallback(() => {
        if (!exportData) return;
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `gdpr-export-${trimmedId}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }, [exportData, trimmedId]);

    return (
        <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold tracking-tight">GDPR Compliance Tools</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Data portability, erasure, and consent management
                </p>
            </div>

            {/* Client ID Input */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base">Client Lookup</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex gap-3 items-center">
                        <Input
                            placeholder="Enter client ID..."
                            value={clientId}
                            onChange={(e) => {
                                setClientId(e.target.value);
                                setExportData(null);
                                setErasureResult(null);
                            }}
                            className="max-w-sm"
                        />
                        {trimmedId && (
                            <Badge variant="secondary" className="text-xs">
                                Querying: {trimmedId}
                            </Badge>
                        )}
                    </div>
                </CardContent>
            </Card>

            {/* Action Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* 1. Data Export (Article 20) */}
                <Card className={cn(!trimmedId && "opacity-50 pointer-events-none")}>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Data Export</CardTitle>
                        <p className="text-xs text-muted-foreground">GDPR Article 20 — Data Portability</p>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <p className="text-sm text-muted-foreground">
                            Export all personal data associated with this client in machine-readable JSON format.
                        </p>
                        <Button
                            size="sm"
                            onClick={() => exportMutation.mutate()}
                            disabled={!trimmedId || exportMutation.isPending}
                        >
                            {exportMutation.isPending ? "Exporting..." : "Export Data"}
                        </Button>
                    </CardContent>
                </Card>

                {/* 2. Right to Erasure (Article 17) */}
                <Card className={cn(!trimmedId && "opacity-50 pointer-events-none")}>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Right to Erasure</CardTitle>
                        <p className="text-xs text-muted-foreground">GDPR Article 17 — Right to be Forgotten</p>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <p className="text-sm text-muted-foreground">
                            Permanently delete all personal data for this client. This action cannot be undone.
                        </p>
                        <AlertDialog>
                            <AlertDialogTrigger asChild>
                                <Button
                                    size="sm"
                                    variant="destructive"
                                    disabled={!trimmedId || erasureMutation.isPending}
                                >
                                    {erasureMutation.isPending ? "Processing..." : "Request Erasure"}
                                </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                                <AlertDialogHeader>
                                    <AlertDialogTitle>Confirm Data Erasure</AlertDialogTitle>
                                    <AlertDialogDescription>
                                        This will permanently delete all personal data for client{" "}
                                        <strong>{trimmedId}</strong>. This action cannot be undone and complies
                                        with GDPR Article 17.
                                    </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                                    <AlertDialogAction
                                        variant="destructive"
                                        onClick={() => erasureMutation.mutate()}
                                    >
                                        Confirm Erasure
                                    </AlertDialogAction>
                                </AlertDialogFooter>
                            </AlertDialogContent>
                        </AlertDialog>
                    </CardContent>
                </Card>

                {/* 3. Consent Status */}
                <Card className={cn(!trimmedId && "opacity-50 pointer-events-none")}>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Consent Status</CardTitle>
                        <p className="text-xs text-muted-foreground">Auto-loads when client ID is entered</p>
                    </CardHeader>
                    <CardContent>
                        {!trimmedId ? (
                            <p className="text-sm text-muted-foreground">Enter a client ID to view consent status.</p>
                        ) : consentQuery.isLoading ? (
                            <div className="space-y-2">
                                {Array.from({ length: 3 }).map((_, i) => (
                                    <Skeleton key={i} className="h-6 w-full" />
                                ))}
                            </div>
                        ) : consentQuery.isError ? (
                            <p className="text-sm text-destructive">Failed to load consent data.</p>
                        ) : consentQuery.data?.consents?.length === 0 ? (
                            <p className="text-sm text-muted-foreground">No consent records found.</p>
                        ) : (
                            <div className="space-y-2">
                                {consentQuery.data?.consents?.map((c, i) => (
                                    <div key={i} className="flex items-center justify-between text-sm">
                                        <span className="capitalize">{c.purpose.replace(/_/g, " ")}</span>
                                        <Badge
                                            variant={c.granted ? "default" : "secondary"}
                                            className={cn(
                                                "text-xs",
                                                c.granted
                                                    ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                                                    : "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
                                            )}
                                        >
                                            {c.granted ? "Granted" : "Not Granted"}
                                        </Badge>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Export Result */}
            {exportData && (
                <Card className="glass-card">
                    <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-base">Export Result</CardTitle>
                            <Button size="sm" variant="outline" onClick={handleDownloadJson}>
                                Download JSON
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <pre className="bg-muted/50 rounded-md p-4 text-xs font-mono overflow-auto max-h-96">
                            {JSON.stringify(exportData, null, 2)}
                        </pre>
                    </CardContent>
                </Card>
            )}

            {/* Erasure Result */}
            {erasureResult && (
                <Card className={cn(
                    erasureResult.status === "success"
                        ? "border-emerald-500/30 bg-emerald-500/5"
                        : "border-red-500/30 bg-red-500/5",
                )}>
                    <CardContent className="pt-4 pb-3">
                        <div className="flex items-center gap-3">
                            <Badge
                                variant={erasureResult.status === "success" ? "default" : "destructive"}
                                className="text-xs"
                            >
                                {erasureResult.status}
                            </Badge>
                            <p className="text-sm">{erasureResult.message}</p>
                            {erasureResult.records_deleted !== undefined && (
                                <span className="text-xs text-muted-foreground ml-auto">
                                    {erasureResult.records_deleted} records deleted
                                </span>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Consent Table (full view when data available) */}
            {trimmedId && consentQuery.data?.consents && consentQuery.data.consents.length > 0 && (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Consent Details</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="divide-y">
                            <div className="grid grid-cols-4 gap-4 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                <span>Purpose</span>
                                <span>Status</span>
                                <span>Granted At</span>
                                <span>Revoked At</span>
                            </div>
                            {consentQuery.data.consents.map((c, i) => (
                                <div key={i} className="grid grid-cols-4 gap-4 py-2.5 text-sm">
                                    <span className="capitalize font-medium">{c.purpose.replace(/_/g, " ")}</span>
                                    <span>
                                        <Badge
                                            variant={c.granted ? "default" : "secondary"}
                                            className={cn(
                                                "text-xs",
                                                c.granted
                                                    ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                                                    : "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
                                            )}
                                        >
                                            {c.granted ? "Granted" : "Not Granted"}
                                        </Badge>
                                    </span>
                                    <span className="text-muted-foreground">{c.granted_at || "—"}</span>
                                    <span className="text-muted-foreground">{c.revoked_at || "—"}</span>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
