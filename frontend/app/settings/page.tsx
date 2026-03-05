// ---- Settings Page ------------------------------------------------------
// Integration management, backup status, and system preferences.
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    useGoogleCalStatus,
    useGoogleCalendars,
    useConnectGoogleCal,
    useGoogleCalCallback,
    useDisconnectGoogleCal,
    useSaveCalendarChoice,
    useSyncGoogleCal,
} from "@/hooks/use-settings";

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

// ---- Google Calendar Settings Section -----------------------------------

function GoogleCalendarSection() {
    const { data: status, isLoading: statusLoading } = useGoogleCalStatus();
    const { data: calendarsData } = useGoogleCalendars(!!status?.connected);
    const connectMutation = useConnectGoogleCal();
    const callbackMutation = useGoogleCalCallback();
    const disconnectMutation = useDisconnectGoogleCal();
    const saveCalendarMutation = useSaveCalendarChoice();
    const syncMutation = useSyncGoogleCal();

    const [showAuthCodeInput, setShowAuthCodeInput] = useState(false);
    const [authCode, setAuthCode] = useState("");
    const [authUrl, setAuthUrl] = useState("");

    const handleConnect = async () => {
        try {
            const result = await connectMutation.mutateAsync();
            if (result.auth_url) {
                setAuthUrl(result.auth_url);
                setShowAuthCodeInput(true);
                window.open(result.auth_url, "_blank");
            }
        } catch {
            toast.error("Failed to start OAuth flow");
        }
    };

    const handleCallback = async () => {
        if (!authCode.trim()) return;
        try {
            await callbackMutation.mutateAsync({ auth_code: authCode.trim() });
            toast.success("Google Calendar connected");
            setShowAuthCodeInput(false);
            setAuthCode("");
            setAuthUrl("");
        } catch {
            toast.error("Failed to connect. Check the auth code and try again.");
        }
    };

    const handleDisconnect = async () => {
        try {
            await disconnectMutation.mutateAsync();
            toast.success("Google Calendar disconnected");
        } catch {
            toast.error("Failed to disconnect");
        }
    };

    const handleCalendarChange = async (calendarId: string) => {
        const cal = calendarsData?.items?.find((c) => c.id === calendarId);
        try {
            await saveCalendarMutation.mutateAsync({
                calendar_id: calendarId,
                calendar_name: cal?.summary ?? "",
            });
            toast.success(`Calendar set to "${cal?.summary || calendarId}"`);
        } catch {
            toast.error("Failed to save calendar selection");
        }
    };

    const handleSync = async () => {
        try {
            const result = await syncMutation.mutateAsync({});
            const r = result.result;
            toast.success(
                `Synced: ${r.pushed} pushed, ${r.skipped} skipped, ${r.failed} failed`,
            );
        } catch {
            toast.error("Sync failed");
        }
    };

    if (statusLoading) {
        return <Skeleton className="h-24 w-full" />;
    }

    // Not connected
    if (!status?.connected) {
        return (
            <div className="space-y-3 py-2">
                <SettingRow
                    label="Google Calendar"
                    description="Sync case events and deadlines to Google Calendar"
                >
                    {!status?.has_credentials ? (
                        <Badge variant="secondary" className="text-xs">
                            Not configured (set GOOGLE_CLIENT_ID)
                        </Badge>
                    ) : showAuthCodeInput ? (
                        <div className="flex items-center gap-2">
                            <Input
                                placeholder="Paste auth code"
                                value={authCode}
                                onChange={(e) => setAuthCode(e.target.value)}
                                className="w-48 h-8 text-xs"
                            />
                            <Button
                                size="sm"
                                onClick={handleCallback}
                                disabled={callbackMutation.isPending || !authCode.trim()}
                            >
                                {callbackMutation.isPending ? "Connecting..." : "Submit"}
                            </Button>
                            <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => {
                                    setShowAuthCodeInput(false);
                                    setAuthCode("");
                                }}
                            >
                                Cancel
                            </Button>
                        </div>
                    ) : (
                        <Button
                            size="sm"
                            onClick={handleConnect}
                            disabled={connectMutation.isPending}
                        >
                            {connectMutation.isPending ? "Starting..." : "Connect"}
                        </Button>
                    )}
                </SettingRow>
                {showAuthCodeInput && authUrl && (
                    <p className="text-xs text-muted-foreground pl-1">
                        A Google authorization page opened in a new tab. Grant access, then
                        paste the code here.
                    </p>
                )}
            </div>
        );
    }

    // Connected
    const calendars = calendarsData?.items ?? [];

    return (
        <div className="space-y-0">
            <SettingRow
                label="Google Calendar"
                description={`Connected as ${status.email || "unknown"}`}
            >
                <div className="flex items-center gap-2">
                    <Badge variant="default" className="text-xs">Connected</Badge>
                    <Button
                        size="sm"
                        variant="outline"
                        onClick={handleSync}
                        disabled={syncMutation.isPending}
                    >
                        {syncMutation.isPending ? "Syncing..." : "Sync Now"}
                    </Button>
                    <Button
                        size="sm"
                        variant="ghost"
                        className="text-destructive"
                        onClick={handleDisconnect}
                        disabled={disconnectMutation.isPending}
                    >
                        Disconnect
                    </Button>
                </div>
            </SettingRow>
            {calendars.length > 0 && (
                <SettingRow
                    label="Target Calendar"
                    description="Select which Google Calendar to sync events to"
                >
                    <Select
                        value={status.calendar_id || "primary"}
                        onValueChange={handleCalendarChange}
                    >
                        <SelectTrigger className="w-56 h-8 text-xs">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {calendars.map((cal) => (
                                <SelectItem key={cal.id} value={cal.id}>
                                    {cal.summary}{cal.primary ? " (Primary)" : ""}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </SettingRow>
            )}
        </div>
    );
}

// ---- Main Settings Page -------------------------------------------------

export default function SettingsPage() {
    const { getToken } = useAuth();

    const { data: backup, isLoading } = useQuery({
        queryKey: ["backup-status"],
        queryFn: () => api.get<BackupStatus>("/backup/status", { getToken }),
    });

    const backupMutation = useMutationWithToast<string>({
        mutationFn: (target) => api.post("/backup/run", { target }, { getToken }),
        successMessage: "Backup complete",
    });

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
                        <Badge variant="secondary" className="text-xs">Coming soon</Badge>
                    </SettingRow>
                    <GoogleCalendarSection />
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
                                            onClick={() => backupMutation.mutate("dropbox")}
                                            disabled={backupMutation.isPending}
                                        >
                                            {backupMutation.isPending ? "Running..." : "Backup Now"}
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
                                            onClick={() => backupMutation.mutate("b2")}
                                            disabled={backupMutation.isPending}
                                        >
                                            {backupMutation.isPending ? "Running..." : "Backup Now"}
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
