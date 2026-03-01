// ---- Settings Page ------------------------------------------------------
// Integration toggles, backup status, LLM provider config, API key status.
"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// ---- Interfaces ---------------------------------------------------------

interface BackupStatus {
    dropbox: { available: boolean };
    b2: { available: boolean };
}

interface ProviderConfig {
    model: string;
    temperature: number;
}

interface ProvidersResponse {
    default_provider: string;
    fallback_provider: string;
    providers: Record<string, ProviderConfig>;
}

interface ApiKeyStatus {
    configured: boolean;
    env_var: string;
}

interface ApiKeysResponse {
    providers: Record<string, ApiKeyStatus>;
}

// ---- Provider metadata --------------------------------------------------

const PROVIDER_META: Record<string, { label: string; description: string; color: string }> = {
    anthropic: {
        label: "Anthropic (Claude)",
        description: "Claude models for analysis and reasoning",
        color: "text-orange-400",
    },
    openai: {
        label: "OpenAI",
        description: "GPT and Whisper models",
        color: "text-emerald-400",
    },
    xai: {
        label: "xAI (Grok)",
        description: "Grok models for analysis",
        color: "text-blue-400",
    },
    google: {
        label: "Google (Gemini)",
        description: "Gemini models",
        color: "text-cyan-400",
    },
};

// ---- SettingRow helper --------------------------------------------------

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

// ---- Component ----------------------------------------------------------

export default function SettingsPage() {
    const { getToken } = useAuth();
    const { canEdit } = useRole();
    const queryClient = useQueryClient();
    const [backingUp, setBackingUp] = useState(false);
    const [savingProvider, setSavingProvider] = useState(false);

    // ---- Queries ----------------------------------------------------------

    const { data: backup, isLoading: backupLoading } = useQuery({
        queryKey: ["backup-status"],
        queryFn: () => api.get<BackupStatus>("/backup/status", { getToken }),
    });

    const { data: providers, isLoading: providersLoading } = useQuery({
        queryKey: ["config-providers"],
        queryFn: () => api.get<ProvidersResponse>("/config/providers", { getToken }),
    });

    const { data: apiKeys, isLoading: keysLoading } = useQuery({
        queryKey: ["config-api-keys"],
        queryFn: () => api.get<ApiKeysResponse>("/config/api-keys", { getToken }),
    });

    // ---- Handlers ---------------------------------------------------------

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

    const handleSetProvider = async (role: "default_provider" | "fallback_provider", provider: string) => {
        setSavingProvider(true);
        try {
            await api.put("/config/providers", { [role]: provider }, { getToken });
            queryClient.invalidateQueries({ queryKey: ["config-providers"] });
            toast.success(`${role === "default_provider" ? "Default" : "Fallback"} provider set to ${provider}`);
        } catch {
            toast.error("Failed to update provider");
        } finally {
            setSavingProvider(false);
        }
    };

    // ---- Derived values ---------------------------------------------------

    const configuredProviders = providers?.providers ?? {};
    const allProviderKeys = Object.keys(PROVIDER_META);
    const keyStatuses = apiKeys?.providers ?? {};

    const configuredCount = Object.values(keyStatuses).filter((k) => k.configured).length;
    const totalProviders = allProviderKeys.length;

    return (
        <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Manage AI providers, integrations, backups, and system preferences
                </p>
            </div>

            <Tabs defaultValue="ai">
                <TabsList>
                    <TabsTrigger value="ai">AI Providers</TabsTrigger>
                    <TabsTrigger value="integrations">Integrations</TabsTrigger>
                    <TabsTrigger value="backup">Backup</TabsTrigger>
                    <TabsTrigger value="system">System</TabsTrigger>
                </TabsList>

                {/* ---- AI Providers Tab ---- */}
                <TabsContent value="ai" className="space-y-6 mt-4">
                    {/* API Key Status */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center justify-between">
                                API Key Status
                                <Badge
                                    variant="outline"
                                    className={configuredCount > 0
                                        ? "text-emerald-400 border-emerald-500/30"
                                        : "text-red-400 border-red-500/30"
                                    }
                                >
                                    {configuredCount}/{totalProviders} Configured
                                </Badge>
                            </CardTitle>
                            <CardDescription>
                                Shows which LLM provider API keys are available. Keys are set via environment variables.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-0">
                            {keysLoading ? (
                                <div className="space-y-3 py-2">
                                    {Array.from({ length: 4 }).map((_, i) => (
                                        <Skeleton key={i} className="h-12 w-full" />
                                    ))}
                                </div>
                            ) : (
                                allProviderKeys.map((key) => {
                                    const meta = PROVIDER_META[key];
                                    const status = keyStatuses[key];
                                    const provConfig = configuredProviders[key];
                                    const isConfigured = status?.configured ?? false;

                                    return (
                                        <div key={key} className="flex items-center justify-between py-3 border-b last:border-0">
                                            <div className="flex items-center gap-3">
                                                {/* Status indicator */}
                                                <div className={`h-3 w-3 rounded-full ${isConfigured ? "bg-emerald-500" : "bg-red-500/60"}`} />
                                                <div>
                                                    <p className={`text-sm font-medium ${meta.color}`}>{meta.label}</p>
                                                    <p className="text-xs text-muted-foreground">{meta.description}</p>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-3">
                                                {provConfig && (
                                                    <Badge variant="outline" className="text-xs font-mono">
                                                        {provConfig.model}
                                                    </Badge>
                                                )}
                                                <Badge
                                                    variant={isConfigured ? "default" : "secondary"}
                                                    className={`text-xs ${isConfigured
                                                        ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                                                        : "text-muted-foreground"
                                                    }`}
                                                >
                                                    {isConfigured ? "Configured" : "Not Set"}
                                                </Badge>
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </CardContent>
                    </Card>

                    {/* Provider Configuration */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">LLM Provider Configuration</CardTitle>
                            <CardDescription>
                                Select the default and fallback providers for AI analysis
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {providersLoading ? (
                                <div className="space-y-3 py-2">
                                    <Skeleton className="h-16 w-full" />
                                    <Skeleton className="h-16 w-full" />
                                </div>
                            ) : (
                                <>
                                    {/* Default Provider Selector */}
                                    <div className="rounded-lg border p-4">
                                        <div className="flex items-center justify-between mb-3">
                                            <div>
                                                <p className="text-sm font-medium">Default Provider</p>
                                                <p className="text-xs text-muted-foreground">
                                                    Primary model used for all case analysis
                                                </p>
                                            </div>
                                            <Badge variant="outline" className="text-sm font-mono">
                                                {providers?.default_provider ?? "anthropic"}
                                            </Badge>
                                        </div>
                                        {canEdit && (
                                            <div className="flex gap-2 flex-wrap">
                                                {Object.keys(configuredProviders).map((provKey) => (
                                                    <Button
                                                        key={provKey}
                                                        size="sm"
                                                        variant={providers?.default_provider === provKey ? "default" : "outline"}
                                                        onClick={() => handleSetProvider("default_provider", provKey)}
                                                        disabled={savingProvider || providers?.default_provider === provKey}
                                                        className="text-xs"
                                                    >
                                                        {PROVIDER_META[provKey]?.label ?? provKey}
                                                        {providers?.default_provider === provKey && " (active)"}
                                                    </Button>
                                                ))}
                                            </div>
                                        )}
                                    </div>

                                    {/* Fallback Provider Selector */}
                                    <div className="rounded-lg border p-4">
                                        <div className="flex items-center justify-between mb-3">
                                            <div>
                                                <p className="text-sm font-medium">Fallback Provider</p>
                                                <p className="text-xs text-muted-foreground">
                                                    Used when the default provider fails or is rate-limited
                                                </p>
                                            </div>
                                            <Badge variant="outline" className="text-sm font-mono">
                                                {providers?.fallback_provider ?? "xai"}
                                            </Badge>
                                        </div>
                                        {canEdit && (
                                            <div className="flex gap-2 flex-wrap">
                                                {Object.keys(configuredProviders).map((provKey) => (
                                                    <Button
                                                        key={provKey}
                                                        size="sm"
                                                        variant={providers?.fallback_provider === provKey ? "default" : "outline"}
                                                        onClick={() => handleSetProvider("fallback_provider", provKey)}
                                                        disabled={savingProvider || providers?.fallback_provider === provKey}
                                                        className="text-xs"
                                                    >
                                                        {PROVIDER_META[provKey]?.label ?? provKey}
                                                        {providers?.fallback_provider === provKey && " (active)"}
                                                    </Button>
                                                ))}
                                            </div>
                                        )}
                                    </div>

                                    {/* Model Details Table */}
                                    {Object.keys(configuredProviders).length > 0 && (
                                        <div className="rounded-lg border">
                                            <div className="grid grid-cols-4 gap-2 px-4 py-2 border-b bg-muted/30 text-xs font-medium text-muted-foreground uppercase">
                                                <span>Provider</span>
                                                <span>Model</span>
                                                <span>Temperature</span>
                                                <span>Role</span>
                                            </div>
                                            {Object.entries(configuredProviders).map(([provKey, config]) => (
                                                <div key={provKey} className="grid grid-cols-4 gap-2 px-4 py-2.5 border-b last:border-0 items-center">
                                                    <span className={`text-sm font-medium ${PROVIDER_META[provKey]?.color ?? ""}`}>
                                                        {PROVIDER_META[provKey]?.label ?? provKey}
                                                    </span>
                                                    <span className="text-sm font-mono text-muted-foreground">
                                                        {config.model}
                                                    </span>
                                                    <span className="text-sm text-muted-foreground">
                                                        {config.temperature}
                                                    </span>
                                                    <div className="flex gap-1">
                                                        {providers?.default_provider === provKey && (
                                                            <Badge variant="default" className="text-[10px] bg-primary/20 text-primary">
                                                                Default
                                                            </Badge>
                                                        )}
                                                        {providers?.fallback_provider === provKey && (
                                                            <Badge variant="secondary" className="text-[10px]">
                                                                Fallback
                                                            </Badge>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ---- Integrations Tab ---- */}
                <TabsContent value="integrations" className="space-y-6 mt-4">
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

                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">OCR Engine</CardTitle>
                            <CardDescription>Text extraction from scanned documents</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-0">
                            <SettingRow label="Primary Engine" description="Local OCR processing">
                                <Badge variant="outline" className="text-xs">Tesseract (local)</Badge>
                            </SettingRow>
                            <SettingRow label="AI Vision Fallback" description="For low-quality scans, uses AI vision model">
                                <Badge variant="outline" className="text-xs font-mono">
                                    {providers?.default_provider ?? "anthropic"}
                                </Badge>
                            </SettingRow>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ---- Backup Tab ---- */}
                <TabsContent value="backup" className="space-y-6 mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Cloud Backup</CardTitle>
                            <CardDescription>Backup and restore case data</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-0">
                            {backupLoading ? (
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
                </TabsContent>

                {/* ---- System Tab ---- */}
                <TabsContent value="system" className="space-y-6 mt-4">
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
                            <SettingRow label="Max Upload Size" description="Per-request upload limit">
                                <Badge variant="outline" className="text-xs font-mono">20 GB</Badge>
                            </SettingRow>
                            <SettingRow label="Application" description="Project name and version">
                                <Badge variant="outline" className="text-xs font-mono">Project Mushroom Cloud v1.0.0</Badge>
                            </SettingRow>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}
