// ---- Settings Page ------------------------------------------------------
// Integration toggles, backup status, and system preferences.
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

interface BackupStatus {
    dropbox: { available: boolean };
    b2: { available: boolean };
}

function SettingRow({ label, description, children }: {
    label: string;
    description: string;
    children: React.ReactNode;
}) {
    return (
        <div className="flex items-center justify-between py-3 border-b last:border-0">
            <div>
                <p className="text-sm font-medium">{label}</p>
                <p className="text-xs text-muted-foreground">{description}</p>
            </div>
            {children}
        </div>
    );
}

export default function SettingsPage() {
    const { getToken } = useAuth();
    const [backingUp, setBackingUp] = useState(false);

    const { data: backup, isLoading } = useQuery({
        queryKey: ["backup-status"],
        queryFn: () => api.get<BackupStatus>("/backup/status", { getToken }),
    });

    const handleBackup = async (target: string) => {
        setBackingUp(true);
        try {
            await api.post("/backup/run", { target }, { getToken });
            toast.success(`${target} backup complete`);
        } catch {
            toast.error("Backup failed");
        } finally {
            setBackingUp(false);
        }
    };

    return (
        <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Manage integrations, backups, and preferences
                </p>
            </div>

            {/* Integrations */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Integrations</CardTitle>
                    <CardDescription>External service connections</CardDescription>
                </CardHeader>
                <CardContent className="space-y-0">
                    <SettingRow label="Dropbox Sign (E-Signature)" description="Send documents for electronic signature">
                        <Badge variant="outline" className="text-xs">Configured via API Key</Badge>
                    </SettingRow>
                    <SettingRow label="Gmail Integration" description="Import and classify emails to cases">
                        <Badge variant="outline" className="text-xs">Configured via OAuth</Badge>
                    </SettingRow>
                    <SettingRow label="Google Calendar" description="Sync case events and deadlines">
                        <Badge variant="outline" className="text-xs">Configured via OAuth</Badge>
                    </SettingRow>
                </CardContent>
            </Card>

            {/* Cloud Backup */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Cloud Backup</CardTitle>
                    <CardDescription>Backup and restore case data</CardDescription>
                </CardHeader>
                <CardContent className="space-y-0">
                    {isLoading ? (
                        <div className="space-y-3 py-2">
                            <Skeleton className="h-12 w-full" />
                            <Skeleton className="h-12 w-full" />
                        </div>
                    ) : (
                        <>
                            <SettingRow label="Dropbox Sync" description="Auto-sync case files to Dropbox folder">
                                <div className="flex items-center gap-2">
                                    <Badge variant={backup?.dropbox?.available ? "default" : "secondary"} className="text-xs">
                                        {backup?.dropbox?.available ? "Connected" : "Not configured"}
                                    </Badge>
                                    {backup?.dropbox?.available && (
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => handleBackup("dropbox")}
                                            disabled={backingUp}
                                        >
                                            {backingUp ? "Running..." : "Backup Now"}
                                        </Button>
                                    )}
                                </div>
                            </SettingRow>
                            <SettingRow label="Backblaze B2" description="Encrypted cloud backup to B2 storage">
                                <div className="flex items-center gap-2">
                                    <Badge variant={backup?.b2?.available ? "default" : "secondary"} className="text-xs">
                                        {backup?.b2?.available ? "Connected" : "Not configured"}
                                    </Badge>
                                    {backup?.b2?.available && (
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => handleBackup("b2")}
                                            disabled={backingUp}
                                        >
                                            {backingUp ? "Running..." : "Backup Now"}
                                        </Button>
                                    )}
                                </div>
                            </SettingRow>
                        </>
                    )}
                </CardContent>
            </Card>

            {/* AI Configuration */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">AI Analysis</CardTitle>
                    <CardDescription>LLM provider settings</CardDescription>
                </CardHeader>
                <CardContent className="space-y-0">
                    <SettingRow label="Default LLM Provider" description="Primary model for case analysis">
                        <Badge variant="outline" className="text-xs font-mono">
                            {process.env.NEXT_PUBLIC_LLM_PROVIDER || "anthropic"}
                        </Badge>
                    </SettingRow>
                    <SettingRow label="OCR Engine" description="Text extraction from scanned documents">
                        <Badge variant="outline" className="text-xs">Tesseract (local)</Badge>
                    </SettingRow>
                </CardContent>
            </Card>

            {/* System Info */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">System</CardTitle>
                </CardHeader>
                <CardContent className="space-y-0">
                    <SettingRow label="API Version" description="Backend API prefix">
                        <Badge variant="outline" className="text-xs font-mono">/api/v1</Badge>
                    </SettingRow>
                    <SettingRow label="Rate Limit" description="Requests per minute per IP">
                        <Badge variant="outline" className="text-xs font-mono">120/min</Badge>
                    </SettingRow>
                </CardContent>
            </Card>
        </div>
    );
}
