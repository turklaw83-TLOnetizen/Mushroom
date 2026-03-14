// ---- Client Communications Page ------------------------------------------
// Review queue, log, templates, settings, and payment feed.
"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { routes } from "@/lib/api-routes";
import { queryKeys } from "@/lib/query-keys";
import { formatDate, COMM_STATUS_COLORS, getStatusColor } from "@/lib/constants";
import { StatusBadge } from "@/components/shared/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { EditCommDialog } from "@/components/comms/edit-comm-dialog";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import type {
    CommQueueItem,
    CommTemplate,
    CommLogEntry,
    CommSettings,
    CommQueueStats,
    FeedTransaction,
} from "@/types/api";

// ---- Trigger badge colors ----
const TRIGGER_COLORS: Record<string, string> = {
    payment_reminder: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
    payment_overdue: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    court_prep: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    intake_followup: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    phase_change: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
    custom: "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300",
};

function TriggerBadge({ type }: { type: string }) {
    const label = type.replace(/_/g, " ");
    return (
        <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium capitalize ${TRIGGER_COLORS[type] || TRIGGER_COLORS.custom}`}>
            {label}
        </span>
    );
}

export default function CommsPage() {
    const { getToken } = useAuth();
    const qc = useQueryClient();
    const fileInputRef = useRef<HTMLInputElement>(null);

    const [editItem, setEditItem] = useState<CommQueueItem | null>(null);
    const [editOpen, setEditOpen] = useState(false);
    const [dismissId, setDismissId] = useState<string | null>(null);
    const [platform, setPlatform] = useState("generic");
    const [emailSubject, setEmailSubject] = useState("");
    const [emailBody, setEmailBody] = useState("");
    const [showCSVFallback, setShowCSVFallback] = useState(false);
    const [showSendPreview, setShowSendPreview] = useState(false);

    // ---- Queries ----
    const { data: statsData } = useQuery({
        queryKey: [...queryKeys.comms.stats],
        queryFn: () => api.get<CommQueueStats>(routes.comms.stats, { getToken }),
    });

    const { data: queueData, isLoading: queueLoading } = useQuery({
        queryKey: [...queryKeys.comms.queue, "pending"],
        queryFn: () => api.get<{ items: CommQueueItem[] }>(`${routes.comms.queue}?status=pending`, { getToken }),
    });

    const { data: approvedData } = useQuery({
        queryKey: [...queryKeys.comms.queue, "approved"],
        queryFn: () => api.get<{ items: CommQueueItem[] }>(`${routes.comms.queue}?status=approved`, { getToken }),
    });

    const { data: logData, isLoading: logLoading } = useQuery({
        queryKey: [...queryKeys.comms.log],
        queryFn: () => api.get<{ items: CommLogEntry[] }>(routes.comms.log, { getToken }),
    });

    const { data: templatesData, isLoading: templatesLoading } = useQuery({
        queryKey: [...queryKeys.comms.templates],
        queryFn: () => api.get<{ items: CommTemplate[] }>(routes.comms.templates, { getToken }),
    });

    const { data: settingsData } = useQuery({
        queryKey: [...queryKeys.comms.settings],
        queryFn: () => api.get<CommSettings>(routes.comms.settings, { getToken }),
    });

    const { data: feedData, isLoading: feedLoading } = useQuery({
        queryKey: [...queryKeys.paymentFeed.transactions],
        queryFn: () => api.get<{ items: FeedTransaction[] }>(routes.paymentFeed.transactions, { getToken }),
    });

    // ---- Mutations ----
    const invalidateAll = () => {
        qc.invalidateQueries({ queryKey: [...queryKeys.comms.queue] });
        qc.invalidateQueries({ queryKey: [...queryKeys.comms.stats] });
        qc.invalidateQueries({ queryKey: [...queryKeys.comms.log] });
        qc.invalidateQueries({ queryKey: [...queryKeys.paymentFeed.transactions] });
    };

    const approveMut = useMutation({
        mutationFn: (vars: { comm_id: string; edited_body?: string; edited_sms?: string }) =>
            api.post(routes.comms.approve(vars.comm_id), {
                edited_body: vars.edited_body ?? null,
                edited_sms: vars.edited_sms ?? null,
            }, { getToken }),
        onSuccess: () => { toast.success("Communication approved"); invalidateAll(); },
        onError: () => toast.error("Failed to approve"),
    });

    const dismissMut = useMutation({
        mutationFn: (comm_id: string) =>
            api.post(routes.comms.dismiss(comm_id), { reason: "" }, { getToken }),
        onSuccess: () => { toast.success("Communication dismissed"); invalidateAll(); },
        onError: () => toast.error("Failed to dismiss"),
    });

    const scanMut = useMutation({
        mutationFn: () => api.post<{ new_drafts: number }>("/comms/scan", {}, { getToken }),
        onSuccess: (data) => {
            toast.success(`Scan complete: ${data.new_drafts} new drafts`);
            invalidateAll();
        },
        onError: () => toast.error("Scan failed"),
    });

    const sendMut = useMutation({
        mutationFn: () => api.post<{ sent: number; failed: number }>("/comms/send", {}, { getToken }),
        onSuccess: (data) => {
            toast.success(`Sent ${data.sent} messages${data.failed > 0 ? `, ${data.failed} failed` : ""}`);
            invalidateAll();
        },
        onError: () => toast.error("Send failed"),
    });

    const uploadMut = useMutation({
        mutationFn: async (file: File) => {
            const formData = new FormData();
            formData.append("file", file);
            formData.append("platform", platform);
            const token = await getToken();
            const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const csrfMatch = document.cookie.match(/(?:^|;\s*)mc-csrf=([^;]*)/);
            const csrfToken = csrfMatch ? decodeURIComponent(csrfMatch[1]) : "";
            const headers: Record<string, string> = {};
            if (token) headers["Authorization"] = `Bearer ${token}`;
            if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
            const res = await fetch(`${baseUrl}/api/v1${routes.paymentFeed.upload}`, {
                method: "POST",
                headers,
                credentials: "include",
                body: formData,
            });
            if (!res.ok) throw new Error("Upload failed");
            return res.json();
        },
        onSuccess: (data) => {
            toast.success(`Imported ${data.total} transactions (${data.classified} classified)`);
            invalidateAll();
        },
        onError: () => toast.error("Upload failed"),
    });

    const ingestEmailMut = useMutation({
        mutationFn: (vars: { subject: string; body: string; sender_email?: string }) =>
            api.post<{ status: string; transaction?: FeedTransaction; classified?: boolean; suggested_client?: string; message?: string }>(
                routes.paymentFeed.ingestEmail, vars, { getToken },
            ),
        onSuccess: (data) => {
            if (data.status === "no_payment_found") {
                toast.error(data.message || "No payment found in email");
            } else {
                const msg = data.classified
                    ? `Payment detected — suggested match: ${data.suggested_client}`
                    : "Payment imported — needs classification";
                toast.success(msg);
                setEmailSubject("");
                setEmailBody("");
            }
            invalidateAll();
        },
        onError: () => toast.error("Failed to process email"),
    });

    const classifyMut = useMutation({
        mutationFn: (vars: { txn_id: string; client_id: string; plan_id: string }) =>
            api.post(`/payment-feed/${vars.txn_id}/classify`, {
                client_id: vars.client_id,
                plan_id: vars.plan_id,
            }, { getToken }),
        onSuccess: () => { toast.success("Payment recorded"); invalidateAll(); },
        onError: () => toast.error("Failed to record"),
    });

    const dismissTxnMut = useMutation({
        mutationFn: (txn_id: string) =>
            api.post(routes.paymentFeed.dismiss(txn_id), { reason: "" }, { getToken }),
        onSuccess: () => { toast.success("Transaction dismissed"); invalidateAll(); },
        onError: () => toast.error("Failed to dismiss"),
    });

    const toggleTemplateMut = useMutation({
        mutationFn: (vars: { id: string; active: boolean }) =>
            api.put(routes.comms.template(vars.id), { active: vars.active }, { getToken }),
        onSuccess: () => {
            toast.success("Template updated");
            qc.invalidateQueries({ queryKey: [...queryKeys.comms.templates] });
        },
    });

    const saveSettingsMut = useMutation({
        mutationFn: (updates: Partial<CommSettings>) =>
            api.put(routes.comms.settings, updates, { getToken }),
        onSuccess: () => {
            toast.success("Settings saved");
            qc.invalidateQueries({ queryKey: [...queryKeys.comms.settings] });
        },
    });

    // ---- Derived data ----
    const queue = queueData?.items ?? [];
    const approvedQueue = approvedData?.items ?? [];
    const log = logData?.items ?? [];
    const templates = templatesData?.items ?? [];
    const feed = feedData?.items ?? [];
    const stats = statsData ?? { pending: 0, approved: 0, sent: 0, failed: 0, dismissed: 0 };
    const settings = settingsData;

    const handleFileUpload = () => {
        const file = fileInputRef.current?.files?.[0];
        if (file) uploadMut.mutate(file);
    };

    return (
        <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Client Communications</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Review, approve, and send automated client messages
                </p>
            </div>

            {/* Stats Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs text-muted-foreground">Pending</p>
                        <p className="text-2xl font-bold text-amber-600">{stats.pending}</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs text-muted-foreground">Approved</p>
                        <p className="text-2xl font-bold text-blue-600">{stats.approved}</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs text-muted-foreground">Sent</p>
                        <p className="text-2xl font-bold text-green-600">{stats.sent}</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs text-muted-foreground">Feed Items</p>
                        <p className="text-2xl font-bold text-violet-600">{feed.length}</p>
                    </CardContent>
                </Card>
            </div>

            {/* Tabs */}
            <Tabs defaultValue="queue">
                <TabsList>
                    <TabsTrigger value="queue">
                        Queue {stats.pending > 0 && <Badge variant="secondary" className="ml-1 text-[10px] px-1.5">{stats.pending}</Badge>}
                    </TabsTrigger>
                    <TabsTrigger value="feed">
                        Payment Feed {feed.length > 0 && <Badge variant="secondary" className="ml-1 text-[10px] px-1.5">{feed.length}</Badge>}
                    </TabsTrigger>
                    <TabsTrigger value="log">Log</TabsTrigger>
                    <TabsTrigger value="templates">Templates</TabsTrigger>
                    <TabsTrigger value="settings">Settings</TabsTrigger>
                </TabsList>

                {/* ---- QUEUE TAB ---- */}
                <TabsContent value="queue" className="space-y-4">
                    <div className="flex items-center gap-2">
                        <Button
                            size="sm"
                            variant="outline"
                            onClick={() => scanMut.mutate()}
                            disabled={scanMut.isPending}
                        >
                            {scanMut.isPending ? "Scanning..." : "Scan Now"}
                        </Button>
                        {stats.approved > 0 && (
                            <Button
                                size="sm"
                                onClick={() => setShowSendPreview(true)}
                                disabled={sendMut.isPending}
                            >
                                {sendMut.isPending ? "Sending..." : `Send ${stats.approved} Approved`}
                            </Button>
                        )}
                    </div>

                    {queueLoading ? (
                        <div className="space-y-3">
                            {Array.from({ length: 3 }).map((_, i) => (
                                <Skeleton key={i} className="h-24 w-full rounded-lg" />
                            ))}
                        </div>
                    ) : queue.length === 0 ? (
                        <Card>
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No pending communications. Click &quot;Scan Now&quot; to check for triggers.
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="space-y-3">
                            {queue.map((item) => (
                                <Card key={item.id} className="hover:border-primary/20 transition-colors">
                                    <CardContent className="py-4">
                                        <div className="flex items-start justify-between gap-4">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className="text-sm font-medium truncate">
                                                        {item.metadata?.client_name || "Client"}
                                                    </span>
                                                    <TriggerBadge type={item.trigger_type} />
                                                    <Badge variant="outline" className="text-[10px]">
                                                        {item.channel}
                                                    </Badge>
                                                </div>
                                                <p className="text-sm font-medium text-foreground mb-1">
                                                    {item.subject}
                                                </p>
                                                <p className="text-xs text-muted-foreground line-clamp-2">
                                                    {item.body_html?.replace(/<[^>]*>/g, "").slice(0, 200)}
                                                </p>
                                                {item.metadata?.due_date && (
                                                    <p className="text-[10px] text-muted-foreground mt-1">
                                                        Due: {item.metadata.due_date}
                                                        {item.metadata.amount_due ? ` · $${item.metadata.amount_due.toLocaleString()}` : ""}
                                                    </p>
                                                )}
                                            </div>
                                            <div className="flex gap-1.5 shrink-0">
                                                <Button
                                                    size="sm"
                                                    variant="default"
                                                    className="text-xs"
                                                    onClick={() => approveMut.mutate({ comm_id: item.id })}
                                                    disabled={approveMut.isPending}
                                                >
                                                    Approve
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    className="text-xs"
                                                    onClick={() => { setEditItem(item); setEditOpen(true); }}
                                                >
                                                    Edit
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    className="text-xs text-destructive hover:text-destructive"
                                                    onClick={() => setDismissId(item.id)}
                                                >
                                                    Dismiss
                                                </Button>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </TabsContent>

                {/* ---- PAYMENT FEED TAB ---- */}
                <TabsContent value="feed" className="space-y-4">
                    {/* Email Ingest — Primary Input */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium">
                                📧 Forward Payment Email
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <p className="text-xs text-muted-foreground">
                                Paste the subject and body of a Venmo, Cash App, or Chime notification email.
                                The platform is auto-detected.
                            </p>
                            <div className="space-y-2">
                                <Input
                                    placeholder="Email subject (e.g. 'John Smith paid you $150.00')"
                                    value={emailSubject}
                                    onChange={(e) => setEmailSubject(e.target.value)}
                                />
                                <textarea
                                    placeholder="Paste the full email body here..."
                                    value={emailBody}
                                    onChange={(e) => setEmailBody(e.target.value)}
                                    rows={5}
                                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                />
                                <div className="flex items-center gap-2">
                                    <Button
                                        size="sm"
                                        onClick={() => ingestEmailMut.mutate({
                                            subject: emailSubject,
                                            body: emailBody,
                                        })}
                                        disabled={!emailSubject.trim() || !emailBody.trim() || ingestEmailMut.isPending}
                                    >
                                        {ingestEmailMut.isPending ? "Processing..." : "Process Email"}
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="text-xs"
                                        onClick={() => setShowCSVFallback(!showCSVFallback)}
                                    >
                                        {showCSVFallback ? "Hide CSV Upload" : "Upload CSV Instead"}
                                    </Button>
                                </div>
                            </div>

                            {/* CSV Upload — Secondary/Fallback */}
                            {showCSVFallback && (
                                <div className="flex items-center gap-3 pt-2 border-t">
                                    <Select value={platform} onValueChange={setPlatform}>
                                        <SelectTrigger className="w-36">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="venmo">Venmo</SelectItem>
                                            <SelectItem value="cashapp">Cash App</SelectItem>
                                            <SelectItem value="chime">Chime</SelectItem>
                                            <SelectItem value="generic">Other Bank</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <input
                                        ref={fileInputRef}
                                        type="file"
                                        accept=".csv"
                                        className="hidden"
                                        onChange={handleFileUpload}
                                    />
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => fileInputRef.current?.click()}
                                        disabled={uploadMut.isPending}
                                    >
                                        {uploadMut.isPending ? "Uploading..." : "Upload CSV"}
                                    </Button>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {feedLoading ? (
                        <div className="space-y-3">
                            {Array.from({ length: 3 }).map((_, i) => (
                                <Skeleton key={i} className="h-20 w-full rounded-lg" />
                            ))}
                        </div>
                    ) : feed.length === 0 ? (
                        <Card>
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No pending transactions. Paste a forwarded payment email above to get started.
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="space-y-3">
                            {feed.map((txn) => (
                                <Card key={txn.id} className="hover:border-primary/20 transition-colors">
                                    <CardContent className="py-4">
                                        <div className="flex items-center justify-between gap-4">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className="text-sm font-bold text-green-600">
                                                        +${txn.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                                    </span>
                                                    <Badge variant="outline" className="text-[10px]">
                                                        {txn.platform}
                                                    </Badge>
                                                    <span className="text-xs text-muted-foreground">{txn.date}</span>
                                                </div>
                                                <p className="text-sm">
                                                    From: <span className="font-medium">{txn.sender || "Unknown"}</span>
                                                </p>
                                                {txn.note && (
                                                    <p className="text-xs text-muted-foreground truncate">{txn.note}</p>
                                                )}
                                                {txn.suggested_client_name && (
                                                    <div className="flex items-center gap-1 mt-1">
                                                        <span className="text-[10px] text-muted-foreground">Suggested:</span>
                                                        <Badge variant="secondary" className="text-[10px]">
                                                            {txn.suggested_client_name}
                                                        </Badge>
                                                        <span className="text-[10px] text-muted-foreground">
                                                            ({Math.round(txn.confidence * 100)}% confidence)
                                                        </span>
                                                    </div>
                                                )}
                                            </div>
                                            <div className="flex gap-1.5 shrink-0">
                                                {txn.suggested_client_id && txn.suggested_plan_id && (
                                                    <Button
                                                        size="sm"
                                                        className="text-xs"
                                                        onClick={() => classifyMut.mutate({
                                                            txn_id: txn.id,
                                                            client_id: txn.suggested_client_id!,
                                                            plan_id: txn.suggested_plan_id!,
                                                        })}
                                                        disabled={classifyMut.isPending}
                                                    >
                                                        Confirm
                                                    </Button>
                                                )}
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    className="text-xs text-destructive hover:text-destructive"
                                                    onClick={() => dismissTxnMut.mutate(txn.id)}
                                                    disabled={dismissTxnMut.isPending}
                                                >
                                                    Dismiss
                                                </Button>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </TabsContent>

                {/* ---- LOG TAB ---- */}
                <TabsContent value="log" className="space-y-4">
                    {logLoading ? (
                        <div className="space-y-3">
                            {Array.from({ length: 5 }).map((_, i) => (
                                <Skeleton key={i} className="h-16 w-full rounded-lg" />
                            ))}
                        </div>
                    ) : log.length === 0 ? (
                        <Card>
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No communications sent yet.
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="space-y-2">
                            {log.map((entry) => (
                                <Card key={entry.id}>
                                    <CardContent className="py-3">
                                        <div className="flex items-center justify-between">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-0.5">
                                                    <span className="text-sm font-medium truncate">{entry.subject}</span>
                                                    <TriggerBadge type={entry.trigger_type} />
                                                </div>
                                                <p className="text-xs text-muted-foreground">
                                                    Sent to {entry.sent_to} · {formatDate(entry.sent_at)} · Approved by {entry.approved_by || "—"}
                                                </p>
                                            </div>
                                            <StatusBadge status={entry.status} domain="comm" size="sm" />
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </TabsContent>

                {/* ---- TEMPLATES TAB ---- */}
                <TabsContent value="templates" className="space-y-4">
                    {templatesLoading ? (
                        <div className="space-y-3">
                            {Array.from({ length: 4 }).map((_, i) => (
                                <Skeleton key={i} className="h-16 w-full rounded-lg" />
                            ))}
                        </div>
                    ) : templates.length === 0 ? (
                        <Card>
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No templates configured.
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="space-y-2">
                            {templates.map((tpl) => (
                                <Card key={tpl.id} className={!tpl.active ? "opacity-50" : ""}>
                                    <CardContent className="py-3">
                                        <div className="flex items-center justify-between">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-0.5">
                                                    <span className="text-sm font-medium">{tpl.name}</span>
                                                    <TriggerBadge type={tpl.trigger_type} />
                                                    {tpl.ai_enhance && (
                                                        <Badge variant="outline" className="text-[10px]">AI</Badge>
                                                    )}
                                                </div>
                                                <p className="text-xs text-muted-foreground truncate">
                                                    {tpl.subject_template}
                                                </p>
                                            </div>
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                className="text-xs"
                                                onClick={() => toggleTemplateMut.mutate({
                                                    id: tpl.id,
                                                    active: !tpl.active,
                                                })}
                                            >
                                                {tpl.active ? "Disable" : "Enable"}
                                            </Button>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </TabsContent>

                {/* ---- SETTINGS TAB ---- */}
                <TabsContent value="settings" className="space-y-4">
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium">Firm Information</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <label className="text-xs font-medium text-muted-foreground">Firm Name</label>
                                    <Input
                                        defaultValue={settings?.firm_name || ""}
                                        placeholder="e.g. Law Offices of Smith & Associates"
                                        onBlur={(e) => {
                                            if (e.target.value !== (settings?.firm_name || "")) {
                                                saveSettingsMut.mutate({ firm_name: e.target.value });
                                            }
                                        }}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-xs font-medium text-muted-foreground">Default Sender Name</label>
                                    <Input
                                        defaultValue={settings?.default_sender_name || ""}
                                        placeholder="e.g. Legal Team"
                                        onBlur={(e) => {
                                            if (e.target.value !== (settings?.default_sender_name || "")) {
                                                saveSettingsMut.mutate({ default_sender_name: e.target.value });
                                            }
                                        }}
                                    />
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium">Trigger Configuration</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {settings?.triggers && Object.entries(settings.triggers).map(([key, config]) => (
                                <div key={key} className="flex items-center justify-between py-2 border-b last:border-0">
                                    <div>
                                        <p className="text-sm font-medium capitalize">{key.replace(/_/g, " ")}</p>
                                        <p className="text-xs text-muted-foreground">
                                            {config.days_before ? `${config.days_before.join(", ")} days before` : ""}
                                            {config.days_after ? `${config.days_after.join(", ")} days after` : ""}
                                            {config.days_after_intake ? `${config.days_after_intake.join(", ")} days after intake` : ""}
                                            {config.use_event_reminder_days ? "Uses event reminder days" : ""}
                                            {" · "}
                                            {config.channels?.join(", ")}
                                        </p>
                                    </div>
                                    <Button
                                        size="sm"
                                        variant={config.active ? "default" : "outline"}
                                        className="text-xs"
                                        onClick={() => {
                                            const updated = { ...settings.triggers };
                                            updated[key] = { ...config, active: !config.active };
                                            saveSettingsMut.mutate({ triggers: updated });
                                        }}
                                    >
                                        {config.active ? "Active" : "Inactive"}
                                    </Button>
                                </div>
                            ))}
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            {/* Edit Dialog */}
            <EditCommDialog
                open={editOpen}
                onOpenChange={setEditOpen}
                item={editItem}
                onApprove={(commId, editedBody, editedSms) => {
                    approveMut.mutate({ comm_id: commId, edited_body: editedBody, edited_sms: editedSms });
                    setEditOpen(false);
                }}
                isLoading={approveMut.isPending}
            />

            {/* Dismiss Confirm */}
            <ConfirmDialog
                open={!!dismissId}
                onOpenChange={(open) => { if (!open) setDismissId(null); }}
                title="Dismiss Communication"
                description="This will remove the communication from the queue. The trigger may re-fire on the next scan."
                onConfirm={() => {
                    if (dismissId) {
                        dismissMut.mutate(dismissId);
                        setDismissId(null);
                    }
                }}
                isLoading={dismissMut.isPending}
            />

            {/* Send Preview Dialog */}
            <Dialog open={showSendPreview} onOpenChange={setShowSendPreview}>
                <DialogContent className="sm:max-w-lg max-h-[80vh] flex flex-col">
                    <DialogHeader>
                        <DialogTitle>Confirm Send</DialogTitle>
                        <DialogDescription>
                            Review the {approvedQueue.length} approved communication{approvedQueue.length !== 1 ? "s" : ""} below before sending.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="flex-1 overflow-y-auto space-y-3 py-2">
                        {approvedQueue.length === 0 ? (
                            <p className="text-sm text-muted-foreground text-center py-4">
                                No approved communications to send.
                            </p>
                        ) : (
                            approvedQueue.map((item) => (
                                <Card key={item.id} className="border">
                                    <CardContent className="py-3">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="text-sm font-medium truncate">
                                                {item.subject}
                                            </span>
                                            <Badge variant="outline" className="text-[10px] shrink-0">
                                                {item.channel}
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-muted-foreground mb-1">
                                            To: {item.metadata?.client_email || item.metadata?.client_phone || item.metadata?.client_name || "Unknown recipient"}
                                        </p>
                                        <p className="text-xs text-muted-foreground line-clamp-2">
                                            {item.body_html?.replace(/<[^>]*>/g, "").slice(0, 100)}
                                            {(item.body_html?.replace(/<[^>]*>/g, "").length ?? 0) > 100 ? "..." : ""}
                                        </p>
                                    </CardContent>
                                </Card>
                            ))
                        )}
                    </div>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setShowSendPreview(false)}
                            disabled={sendMut.isPending}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={() => {
                                sendMut.mutate(undefined, {
                                    onSettled: () => setShowSendPreview(false),
                                });
                            }}
                            disabled={sendMut.isPending || approvedQueue.length === 0}
                        >
                            {sendMut.isPending ? "Sending..." : `Confirm Send (${approvedQueue.length})`}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
