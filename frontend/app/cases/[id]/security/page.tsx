// ---- Security Dashboard ---------------------------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

// ---- Types ----------------------------------------------------------------

interface FileScan {
    file_name: string;
    status: "clean" | "threat" | "pending";
    scanned_at: string;
    threats: string[];
}

interface FileScanResponse {
    scans: FileScan[];
}

interface DLPRule {
    id: string;
    name: string;
    action: string;
    description: string;
}

interface DLPRulesResponse {
    rules: DLPRule[];
}

interface DLPAuditEntry {
    timestamp: string;
    user: string;
    action: string;
    details: string;
}

interface DLPAuditResponse {
    entries: DLPAuditEntry[];
}

interface AccessLogEntry {
    user: string;
    action: string;
    timestamp: string;
    ip: string;
}

interface AccessLogResponse {
    entries: AccessLogEntry[];
}

interface EncryptionStatus {
    status: string;
    encrypted_count: number;
    total_count: number;
    last_rotated: string;
}

// ---- Component ------------------------------------------------------------

export default function SecurityPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const [activeTab, setActiveTab] = useState<
        "file-security" | "dlp-rules" | "access-log" | "encryption"
    >("file-security");

    // ---- File Security queries --------------------------------------------

    const {
        data: scansData,
        isLoading: scansLoading,
        isError: scansError,
    } = useQuery({
        queryKey: ["security-scans", caseId],
        queryFn: () =>
            api.get<FileScanResponse>(`/cases/${caseId}/security/scans`, {
                getToken,
            }),
        enabled: activeTab === "file-security",
    });

    // ---- DLP Rules queries ------------------------------------------------

    const {
        data: rulesData,
        isLoading: rulesLoading,
        isError: rulesError,
    } = useQuery({
        queryKey: ["dlp-rules"],
        queryFn: () => api.get<DLPRulesResponse>("/dlp/rules", { getToken }),
        enabled: activeTab === "dlp-rules",
    });

    const {
        data: dlpAuditData,
        isLoading: dlpAuditLoading,
        isError: dlpAuditError,
    } = useQuery({
        queryKey: ["dlp-audit", caseId],
        queryFn: () =>
            api.get<DLPAuditResponse>("/dlp/audit-log", {
                params: { case_id: caseId },
                getToken,
            }),
        enabled: activeTab === "dlp-rules",
    });

    // ---- Access Log queries -----------------------------------------------

    const {
        data: accessLogData,
        isLoading: accessLogLoading,
        isError: accessLogError,
    } = useQuery({
        queryKey: ["security-access-log", caseId],
        queryFn: () =>
            api.get<AccessLogResponse>(
                `/cases/${caseId}/security/access-log`,
                { getToken },
            ),
        enabled: activeTab === "access-log",
    });

    // ---- Encryption queries -----------------------------------------------

    const {
        data: encryptionData,
        isLoading: encryptionLoading,
        isError: encryptionError,
    } = useQuery({
        queryKey: ["security-encryption", caseId],
        queryFn: () =>
            api.get<EncryptionStatus>(
                `/cases/${caseId}/security/encryption`,
                { getToken },
            ),
        enabled: activeTab === "encryption",
    });

    // ---- Helpers ----------------------------------------------------------

    function scanStatusBadge(status: FileScan["status"]) {
        switch (status) {
            case "clean":
                return (
                    <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30 text-[10px]">
                        Clean
                    </Badge>
                );
            case "threat":
                return (
                    <Badge className="bg-red-500/10 text-red-400 border-red-500/30 text-[10px]">
                        Threat
                    </Badge>
                );
            case "pending":
                return (
                    <Badge className="bg-amber-500/10 text-amber-400 border-amber-500/30 text-[10px]">
                        Pending
                    </Badge>
                );
            default:
                return <Badge variant="secondary" className="text-[10px]">{status}</Badge>;
        }
    }

    function encryptionPercentage(): number {
        if (!encryptionData || encryptionData.total_count === 0) return 0;
        return Math.round(
            (encryptionData.encrypted_count / encryptionData.total_count) * 100,
        );
    }

    // ---- Render -----------------------------------------------------------

    return (
        <div className="space-y-5">
            <div>
                <h2 className="text-xl font-bold tracking-tight">
                    Security Dashboard
                </h2>
                <p className="text-sm text-muted-foreground mt-0.5">
                    File scanning, DLP policies, access auditing, and encryption
                    status
                </p>
            </div>

            {/* Tab Nav */}
            <div className="flex gap-1 border-b border-border">
                {[
                    { key: "file-security" as const, label: "File Security" },
                    { key: "dlp-rules" as const, label: "DLP Rules" },
                    { key: "access-log" as const, label: "Access Log" },
                    { key: "encryption" as const, label: "Encryption" },
                ].map((tab) => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                            activeTab === tab.key
                                ? "border-primary text-primary"
                                : "border-transparent text-muted-foreground hover:text-foreground"
                        }`}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* ---- Tab 1: File Security ---------------------------------- */}
            {activeTab === "file-security" && (
                <div className="space-y-3">
                    {scansLoading ? (
                        Array.from({ length: 5 }).map((_, i) => (
                            <Skeleton key={i} className="h-16 w-full rounded-lg" />
                        ))
                    ) : scansError ? (
                        <Card className="border-destructive">
                            <CardContent className="py-8 text-center text-destructive">
                                Failed to load file scan results. Please try
                                again later.
                            </CardContent>
                        </Card>
                    ) : !scansData?.scans || scansData.scans.length === 0 ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                <p className="text-lg mb-2">No scan results</p>
                                <p className="text-sm">
                                    File scans will appear here once files have
                                    been uploaded and scanned.
                                </p>
                            </CardContent>
                        </Card>
                    ) : (
                        <>
                            {/* Summary counts */}
                            <div className="grid grid-cols-3 gap-4">
                                <Card>
                                    <CardContent className="py-4 text-center">
                                        <p className="text-2xl font-bold text-emerald-400">
                                            {scansData.scans.filter((s) => s.status === "clean").length}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-1">Clean</p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="py-4 text-center">
                                        <p className="text-2xl font-bold text-red-400">
                                            {scansData.scans.filter((s) => s.status === "threat").length}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-1">Threats</p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="py-4 text-center">
                                        <p className="text-2xl font-bold text-amber-400">
                                            {scansData.scans.filter((s) => s.status === "pending").length}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-1">Pending</p>
                                    </CardContent>
                                </Card>
                            </div>

                            {/* Scan list */}
                            {scansData.scans.map((scan, i) => (
                                <Card
                                    key={i}
                                    className={
                                        scan.status === "threat"
                                            ? "border-red-500/30"
                                            : ""
                                    }
                                >
                                    <CardContent className="py-3 flex items-center justify-between">
                                        <div>
                                            <p className="text-sm font-medium">
                                                {scan.file_name}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                Scanned:{" "}
                                                {new Date(
                                                    scan.scanned_at,
                                                ).toLocaleString()}
                                            </p>
                                            {scan.threats.length > 0 && (
                                                <div className="flex flex-wrap gap-1 mt-1">
                                                    {scan.threats.map(
                                                        (threat, ti) => (
                                                            <span
                                                                key={ti}
                                                                className="text-[10px] text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded"
                                                            >
                                                                {threat}
                                                            </span>
                                                        ),
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                        {scanStatusBadge(scan.status)}
                                    </CardContent>
                                </Card>
                            ))}
                        </>
                    )}
                </div>
            )}

            {/* ---- Tab 2: DLP Rules -------------------------------------- */}
            {activeTab === "dlp-rules" && (
                <div className="space-y-6">
                    {/* Active Rules */}
                    <div className="space-y-3">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                            Active Rules
                        </p>
                        {rulesLoading ? (
                            Array.from({ length: 4 }).map((_, i) => (
                                <Skeleton
                                    key={i}
                                    className="h-16 rounded-lg"
                                />
                            ))
                        ) : rulesError ? (
                            <Card className="border-destructive">
                                <CardContent className="py-8 text-center text-destructive">
                                    Failed to load DLP rules. Please try again
                                    later.
                                </CardContent>
                            </Card>
                        ) : !rulesData?.rules ||
                          rulesData.rules.length === 0 ? (
                            <Card className="border-dashed">
                                <CardContent className="py-12 text-center text-muted-foreground">
                                    No DLP rules configured. Contact admin to set
                                    up policies.
                                </CardContent>
                            </Card>
                        ) : (
                            rulesData.rules.map((rule) => (
                                <Card key={rule.id}>
                                    <CardContent className="py-3">
                                        <div className="flex items-center justify-between">
                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <p className="text-sm font-medium">
                                                        {rule.name}
                                                    </p>
                                                    <Badge
                                                        variant="outline"
                                                        className="text-[10px]"
                                                    >
                                                        {rule.action}
                                                    </Badge>
                                                </div>
                                                <p className="text-xs text-muted-foreground mt-0.5">
                                                    {rule.description}
                                                </p>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))
                        )}
                    </div>

                    {/* Audit Log */}
                    <div className="space-y-3">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                            DLP Audit Log
                        </p>
                        {dlpAuditLoading ? (
                            Array.from({ length: 6 }).map((_, i) => (
                                <Skeleton
                                    key={i}
                                    className="h-12 rounded-lg"
                                />
                            ))
                        ) : dlpAuditError ? (
                            <Card className="border-destructive">
                                <CardContent className="py-8 text-center text-destructive">
                                    Failed to load audit log.
                                </CardContent>
                            </Card>
                        ) : !dlpAuditData?.entries ||
                          dlpAuditData.entries.length === 0 ? (
                            <Card className="border-dashed">
                                <CardContent className="py-8 text-center text-muted-foreground">
                                    No DLP audit entries for this case.
                                </CardContent>
                            </Card>
                        ) : (
                            dlpAuditData.entries.map((entry, i) => (
                                <Card key={i}>
                                    <CardContent className="py-2.5 flex items-center justify-between">
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <p className="text-sm font-medium">
                                                    {entry.user}
                                                </p>
                                                <Badge
                                                    variant="secondary"
                                                    className="text-[10px]"
                                                >
                                                    {entry.action}
                                                </Badge>
                                            </div>
                                            <p className="text-xs text-muted-foreground">
                                                {entry.details}
                                            </p>
                                        </div>
                                        <span className="text-xs text-muted-foreground whitespace-nowrap ml-4">
                                            {new Date(
                                                entry.timestamp,
                                            ).toLocaleString()}
                                        </span>
                                    </CardContent>
                                </Card>
                            ))
                        )}
                    </div>
                </div>
            )}

            {/* ---- Tab 3: Access Log ------------------------------------- */}
            {activeTab === "access-log" && (
                <div className="space-y-2">
                    {accessLogLoading ? (
                        Array.from({ length: 8 }).map((_, i) => (
                            <Skeleton key={i} className="h-14 w-full rounded-lg" />
                        ))
                    ) : accessLogError ? (
                        <Card className="border-destructive">
                            <CardContent className="py-8 text-center text-destructive">
                                Failed to load access log. Please try again
                                later.
                            </CardContent>
                        </Card>
                    ) : !accessLogData?.entries ||
                      accessLogData.entries.length === 0 ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                <p className="text-lg mb-2">No access log entries</p>
                                <p className="text-sm">
                                    Access events for this case will appear here
                                    as users interact with it.
                                </p>
                            </CardContent>
                        </Card>
                    ) : (
                        <>
                            <Card>
                                <CardContent className="py-0">
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-sm">
                                            <thead>
                                                <tr className="border-b border-border text-left">
                                                    <th className="py-2.5 pr-4 font-medium text-muted-foreground text-xs">
                                                        User
                                                    </th>
                                                    <th className="py-2.5 pr-4 font-medium text-muted-foreground text-xs">
                                                        Action
                                                    </th>
                                                    <th className="py-2.5 pr-4 font-medium text-muted-foreground text-xs">
                                                        IP Address
                                                    </th>
                                                    <th className="py-2.5 font-medium text-muted-foreground text-xs">
                                                        Timestamp
                                                    </th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {accessLogData.entries.map(
                                                    (entry, i) => (
                                                        <tr
                                                            key={i}
                                                            className="border-b border-border/50 last:border-0"
                                                        >
                                                            <td className="py-2.5 pr-4 font-medium">
                                                                {entry.user}
                                                            </td>
                                                            <td className="py-2.5 pr-4">
                                                                <Badge
                                                                    variant="outline"
                                                                    className="text-[10px]"
                                                                >
                                                                    {
                                                                        entry.action
                                                                    }
                                                                </Badge>
                                                            </td>
                                                            <td className="py-2.5 pr-4 font-mono text-xs text-muted-foreground">
                                                                {entry.ip}
                                                            </td>
                                                            <td className="py-2.5 text-xs text-muted-foreground whitespace-nowrap">
                                                                {new Date(
                                                                    entry.timestamp,
                                                                ).toLocaleString()}
                                                            </td>
                                                        </tr>
                                                    ),
                                                )}
                                            </tbody>
                                        </table>
                                    </div>
                                </CardContent>
                            </Card>
                        </>
                    )}
                </div>
            )}

            {/* ---- Tab 4: Encryption ------------------------------------- */}
            {activeTab === "encryption" && (
                <div className="space-y-4">
                    {encryptionLoading ? (
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                {Array.from({ length: 4 }).map((_, i) => (
                                    <Skeleton
                                        key={i}
                                        className="h-24 rounded-lg"
                                    />
                                ))}
                            </div>
                            <Skeleton className="h-32 rounded-lg" />
                        </div>
                    ) : encryptionError ? (
                        <Card className="border-destructive">
                            <CardContent className="py-8 text-center text-destructive">
                                Failed to load encryption status. Please try
                                again later.
                            </CardContent>
                        </Card>
                    ) : !encryptionData ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                <p className="text-lg mb-2">
                                    Encryption status unavailable
                                </p>
                                <p className="text-sm">
                                    Upload files to this case to see encryption
                                    information.
                                </p>
                            </CardContent>
                        </Card>
                    ) : (
                        <>
                            {/* Metrics */}
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <Card>
                                    <CardContent className="py-6 text-center">
                                        <p className="text-3xl font-bold text-emerald-400">
                                            {encryptionPercentage()}%
                                        </p>
                                        <p className="text-sm text-muted-foreground mt-1">
                                            Coverage
                                        </p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="py-6 text-center">
                                        <p className="text-3xl font-bold text-indigo-400">
                                            {encryptionData.encrypted_count}
                                        </p>
                                        <p className="text-sm text-muted-foreground mt-1">
                                            Encrypted
                                        </p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="py-6 text-center">
                                        <p className="text-3xl font-bold">
                                            {encryptionData.total_count}
                                        </p>
                                        <p className="text-sm text-muted-foreground mt-1">
                                            Total Files
                                        </p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="py-6 text-center">
                                        <p
                                            className={`text-3xl font-bold ${
                                                encryptionData.total_count -
                                                    encryptionData.encrypted_count >
                                                0
                                                    ? "text-amber-400"
                                                    : "text-emerald-400"
                                            }`}
                                        >
                                            {encryptionData.total_count -
                                                encryptionData.encrypted_count}
                                        </p>
                                        <p className="text-sm text-muted-foreground mt-1">
                                            Unencrypted
                                        </p>
                                    </CardContent>
                                </Card>
                            </div>

                            {/* Status Details */}
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-base">
                                        Encryption Details
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-muted-foreground">
                                            Status
                                        </span>
                                        <Badge
                                            className={
                                                encryptionData.status ===
                                                "active"
                                                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                                                    : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                                            }
                                        >
                                            {encryptionData.status}
                                        </Badge>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-muted-foreground">
                                            Last Key Rotation
                                        </span>
                                        <span className="text-sm">
                                            {encryptionData.last_rotated
                                                ? new Date(
                                                      encryptionData.last_rotated,
                                                  ).toLocaleString()
                                                : "Never"}
                                        </span>
                                    </div>

                                    {/* Coverage bar */}
                                    <div>
                                        <div className="flex items-center justify-between mb-1">
                                            <span className="text-xs text-muted-foreground">
                                                Encryption Coverage
                                            </span>
                                            <span className="text-xs font-medium">
                                                {encryptionPercentage()}%
                                            </span>
                                        </div>
                                        <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                                            <div
                                                className={`h-full rounded-full transition-all ${
                                                    encryptionPercentage() ===
                                                    100
                                                        ? "bg-emerald-500"
                                                        : encryptionPercentage() >=
                                                            75
                                                          ? "bg-indigo-500"
                                                          : "bg-amber-500"
                                                }`}
                                                style={{
                                                    width: `${encryptionPercentage()}%`,
                                                }}
                                            />
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
