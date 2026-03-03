// ---- Cloud Backup Configuration (Admin Only) ----------------------------
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

interface BackupStatus {
    dropbox: { available: boolean };
    b2: { available: boolean };
}

interface BackupItem {
    name: string;
    size: number;
    date: string;
    path: string;
}

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatDate(ts: string): string {
    try {
        const d = new Date(ts);
        return d.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "numeric",
            minute: "2-digit",
        });
    } catch {
        return ts;
    }
}

export default function BackupPage() {
    const { getToken } = useAuth();
    const { isAdmin, isLoading: roleLoading } = useRole();
    const [dropboxCaseId, setDropboxCaseId] = useState("");
    const [b2CaseId, setB2CaseId] = useState("");

    // Backup status
    const statusQuery = useQuery({
        queryKey: ["backup-status"],
        queryFn: () => api.get<BackupStatus>("/backup/status", { getToken }),
    });

    // List backups
    const dropboxListQuery = useQuery({
        queryKey: ["backup-list", "dropbox"],
        queryFn: () =>
            api.get<BackupItem[]>("/backup/list", {
                params: { target: "dropbox" },
                getToken,
            }),
        enabled: !!statusQuery.data?.dropbox?.available,
    });

    const b2ListQuery = useQuery({
        queryKey: ["backup-list", "b2"],
        queryFn: () =>
            api.get<BackupItem[]>("/backup/list", {
                params: { target: "b2" },
                getToken,
            }),
        enabled: !!statusQuery.data?.b2?.available,
    });

    // Run backup mutations
    const runDropboxBackup = useMutationWithToast<void>({
        mutationFn: () =>
            api.post(
                "/backup/run",
                {
                    target: "dropbox",
                    ...(dropboxCaseId ? { case_id: dropboxCaseId } : {}),
                },
                { getToken },
            ),
        successMessage: "Dropbox backup complete",
        errorMessage: "Dropbox backup failed",
        invalidateKeys: [["backup-list", "dropbox"]],
    });

    const runB2Backup = useMutationWithToast<void>({
        mutationFn: () =>
            api.post(
                "/backup/run",
                {
                    target: "b2",
                    ...(b2CaseId ? { case_id: b2CaseId } : {}),
                },
                { getToken },
            ),
        successMessage: "B2 backup complete",
        errorMessage: "B2 backup failed",
        invalidateKeys: [["backup-list", "b2"]],
    });

    const dropboxBackups = dropboxListQuery.data ?? [];
    const b2Backups = b2ListQuery.data ?? [];

    // Admin gate
    if (roleLoading) {
        return (
            <div className="p-6 md:p-8 max-w-6xl mx-auto">
                <Skeleton className="h-8 w-48 mb-2" />
                <Skeleton className="h-4 w-72 mb-6" />
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <Skeleton className="h-64 rounded-lg" />
                    <Skeleton className="h-64 rounded-lg" />
                </div>
            </div>
        );
    }

    if (!isAdmin) {
        return (
            <div className="p-6 md:p-8 max-w-6xl mx-auto">
                <div className="text-center py-16">
                    <p className="text-lg font-medium text-muted-foreground">Access Denied</p>
                    <p className="text-sm text-muted-foreground mt-1">
                        Only administrators can manage cloud backup configuration.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Cloud Backup</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Manage Dropbox and Backblaze B2 backup targets
                </p>
            </div>

            {/* Status Summary */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Dropbox Sync</p>
                        <div className="mt-1">
                            {statusQuery.isLoading ? (
                                <Skeleton className="h-6 w-24 inline-block" />
                            ) : (
                                <Badge
                                    variant={statusQuery.data?.dropbox?.available ? "default" : "secondary"}
                                >
                                    {statusQuery.data?.dropbox?.available ? "Connected" : "Not Configured"}
                                </Badge>
                            )}
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Backblaze B2</p>
                        <div className="mt-1">
                            {statusQuery.isLoading ? (
                                <Skeleton className="h-6 w-24 inline-block" />
                            ) : (
                                <Badge
                                    variant={statusQuery.data?.b2?.available ? "default" : "secondary"}
                                >
                                    {statusQuery.data?.b2?.available ? "Connected" : "Not Configured"}
                                </Badge>
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Two-Column Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Dropbox Section */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Dropbox Sync</CardTitle>
                        <CardDescription>
                            {statusQuery.data?.dropbox?.available
                                ? "Auto-sync case files to local Dropbox folder"
                                : "Configure Dropbox desktop app to enable sync"}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {statusQuery.data?.dropbox?.available && (
                            <>
                                <div className="flex gap-2">
                                    <Input
                                        placeholder="Case ID (optional, blank = all)"
                                        value={dropboxCaseId}
                                        onChange={(e) => setDropboxCaseId(e.target.value)}
                                        className="flex-1"
                                    />
                                    <Button
                                        size="sm"
                                        onClick={() => runDropboxBackup.mutate()}
                                        disabled={runDropboxBackup.isPending}
                                    >
                                        {runDropboxBackup.isPending ? "Running..." : "Run Backup"}
                                    </Button>
                                </div>

                                {/* Backup list */}
                                <div>
                                    <p className="text-xs font-medium text-muted-foreground mb-2">
                                        Recent Backups
                                    </p>
                                    {dropboxListQuery.isLoading ? (
                                        <div className="space-y-2">
                                            {Array.from({ length: 3 }).map((_, i) => (
                                                <Skeleton key={i} className="h-10 w-full" />
                                            ))}
                                        </div>
                                    ) : dropboxBackups.length === 0 ? (
                                        <p className="text-sm text-muted-foreground text-center py-4">
                                            No backups found.
                                        </p>
                                    ) : (
                                        <div className="space-y-1 max-h-64 overflow-y-auto">
                                            {dropboxBackups.map((item, i) => (
                                                <div
                                                    key={i}
                                                    className="flex items-center justify-between py-2 border-b border-border last:border-0 text-sm"
                                                >
                                                    <div>
                                                        <p className="font-medium text-xs truncate max-w-[200px]">
                                                            {item.name}
                                                        </p>
                                                        <p className="text-xs text-muted-foreground">
                                                            {formatDate(item.date)}
                                                        </p>
                                                    </div>
                                                    <span className="text-xs text-muted-foreground">
                                                        {formatSize(item.size)}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </>
                        )}

                        {!statusQuery.isLoading && !statusQuery.data?.dropbox?.available && (
                            <p className="text-sm text-muted-foreground text-center py-4">
                                Install and configure Dropbox desktop app to enable sync backup.
                            </p>
                        )}
                    </CardContent>
                </Card>

                {/* B2 Section */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Backblaze B2</CardTitle>
                        <CardDescription>
                            {statusQuery.data?.b2?.available
                                ? "Encrypted cloud backup to B2 storage"
                                : "Set B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, and B2_BUCKET_NAME env vars"}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {statusQuery.data?.b2?.available && (
                            <>
                                <div className="flex gap-2">
                                    <Input
                                        placeholder="Case ID (optional, blank = all)"
                                        value={b2CaseId}
                                        onChange={(e) => setB2CaseId(e.target.value)}
                                        className="flex-1"
                                    />
                                    <Button
                                        size="sm"
                                        onClick={() => runB2Backup.mutate()}
                                        disabled={runB2Backup.isPending}
                                    >
                                        {runB2Backup.isPending ? "Running..." : "Run Backup"}
                                    </Button>
                                </div>

                                {/* Backup list */}
                                <div>
                                    <p className="text-xs font-medium text-muted-foreground mb-2">
                                        Recent Backups
                                    </p>
                                    {b2ListQuery.isLoading ? (
                                        <div className="space-y-2">
                                            {Array.from({ length: 3 }).map((_, i) => (
                                                <Skeleton key={i} className="h-10 w-full" />
                                            ))}
                                        </div>
                                    ) : b2Backups.length === 0 ? (
                                        <p className="text-sm text-muted-foreground text-center py-4">
                                            No backups found.
                                        </p>
                                    ) : (
                                        <div className="space-y-1 max-h-64 overflow-y-auto">
                                            {b2Backups.map((item, i) => (
                                                <div
                                                    key={i}
                                                    className="flex items-center justify-between py-2 border-b border-border last:border-0 text-sm"
                                                >
                                                    <div>
                                                        <p className="font-medium text-xs truncate max-w-[200px]">
                                                            {item.name}
                                                        </p>
                                                        <p className="text-xs text-muted-foreground">
                                                            {formatDate(item.date)}
                                                        </p>
                                                    </div>
                                                    <span className="text-xs text-muted-foreground">
                                                        {formatSize(item.size)}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </>
                        )}

                        {!statusQuery.isLoading && !statusQuery.data?.b2?.available && (
                            <p className="text-sm text-muted-foreground text-center py-4">
                                Set the required environment variables to enable B2 backup.
                            </p>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
