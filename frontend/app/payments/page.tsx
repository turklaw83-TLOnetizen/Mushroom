// ---- Payments Page --------------------------------------------------------
// Payment Feed ingestion, Stripe integration, and Accounts Receivable overview.
"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { routes } from "@/lib/api-routes";
import { queryKeys } from "@/lib/query-keys";
import { formatCurrency } from "@/lib/constants";
import { StatusBadge } from "@/components/shared/status-badge";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import type {
    FeedTransaction,
    StripePaymentLink,
    StripeCheckoutSession,
    StripeConfig,
    AROverview,
    PaymentPlanSummary,
    Client,
} from "@/types/api";

// ---- Constants & Helpers ------------------------------------------------

const PLATFORM_COLORS: Record<string, string> = {
    venmo: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
    cashapp: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    chime: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    generic: "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300",
};

function ConfidenceBar({ confidence }: { confidence: number }) {
    const pct = Math.round(confidence * 100);
    const color =
        confidence > 0.7
            ? "bg-green-500"
            : confidence > 0.4
              ? "bg-yellow-500"
              : "bg-red-500";

    return (
        <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden max-w-[80px]">
                <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
            </div>
            <span className="text-[10px] text-muted-foreground tabular-nums">{pct}%</span>
        </div>
    );
}

// ---- Main Component -----------------------------------------------------

export default function PaymentsPage() {
    const { getToken } = useAuth();
    const qc = useQueryClient();
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Payment Feed state
    const [feedFilter, setFeedFilter] = useState<string>("all");
    const [emailSubject, setEmailSubject] = useState("");
    const [emailBody, setEmailBody] = useState("");
    const [emailSender, setEmailSender] = useState("");
    const [csvPlatform, setCsvPlatform] = useState("generic");
    const [dismissingId, setDismissingId] = useState<string | null>(null);
    const [dismissReason, setDismissReason] = useState("");

    // Stripe state
    const [linkAmount, setLinkAmount] = useState("");
    const [linkDescription, setLinkDescription] = useState("");
    const [linkClientId, setLinkClientId] = useState("");
    const [linkClientName, setLinkClientName] = useState("");
    const [linkClientEmail, setLinkClientEmail] = useState("");

    // ---- Queries ----

    const feedQuery = useQuery({
        queryKey: ["payment-feed", feedFilter],
        queryFn: () =>
            api.get<{ items: FeedTransaction[] }>(
                feedFilter === "pending"
                    ? "/payment-feed/pending"
                    : `/payment-feed/all${feedFilter !== "all" ? `?status=${feedFilter}` : ""}`,
                { getToken },
            ),
    });

    const stripeConfigQuery = useQuery({
        queryKey: [...queryKeys.stripe.config],
        queryFn: () => api.get<StripeConfig>(routes.stripe.config, { getToken }),
    });

    const paymentLinksQuery = useQuery({
        queryKey: [...queryKeys.stripe.paymentLinks],
        queryFn: () => api.get<{ items: StripePaymentLink[] }>(routes.stripe.paymentLinks, { getToken }),
    });

    const checkoutSessionsQuery = useQuery({
        queryKey: [...queryKeys.stripe.checkoutSessions],
        queryFn: () => api.get<{ items: StripeCheckoutSession[] }>(routes.stripe.checkoutSessions, { getToken }),
    });

    const arQuery = useQuery({
        queryKey: [...queryKeys.billing.arOverview],
        queryFn: () => api.get<AROverview>(routes.billing.arOverview, { getToken }),
    });

    const clientsQuery = useQuery({
        queryKey: [...queryKeys.crm.clients],
        queryFn: () => api.get<{ items: Client[] }>(routes.crm.clients, { getToken }),
    });

    // ---- Derived data ----
    const feedItems = feedQuery.data?.items ?? [];
    const stripeConfig = stripeConfigQuery.data;
    const paymentLinks = paymentLinksQuery.data?.items ?? [];
    const checkoutSessions = checkoutSessionsQuery.data?.items ?? [];
    const ar = arQuery.data;
    const plans = ar?.plans ?? [];

    // ---- Feed invalidation helper ----
    const invalidateFeed = () => {
        qc.invalidateQueries({ queryKey: ["payment-feed"] });
    };

    // ---- Mutations: Payment Feed ----

    const ingestEmailMut = useMutation({
        mutationFn: (vars: { subject: string; body: string; sender_email: string }) =>
            api.post<{ status: string; transaction?: FeedTransaction; classified?: boolean; suggested_client?: string; message?: string }>(
                routes.paymentFeed.ingestEmail,
                vars,
                { getToken },
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
                setEmailSender("");
            }
            invalidateFeed();
        },
        onError: () => toast.error("Failed to process email"),
    });

    const uploadCsvMut = useMutation({
        mutationFn: async (file: File) => {
            const formData = new FormData();
            formData.append("file", file);
            formData.append("platform", csvPlatform);
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
            return res.json() as Promise<{ status: string; total: number; classified: number; unclassified: number; transactions: FeedTransaction[] }>;
        },
        onSuccess: (data) => {
            toast.success(`Imported ${data.total} transactions (${data.classified} classified, ${data.unclassified} unclassified)`);
            invalidateFeed();
        },
        onError: () => toast.error("CSV upload failed"),
    });

    const classifyMut = useMutation({
        mutationFn: (vars: { txn_id: string; client_id: string; plan_id: string }) =>
            api.post(routes.paymentFeed.confirm(vars.txn_id), {
                client_id: vars.client_id,
                plan_id: vars.plan_id,
            }, { getToken }),
        onSuccess: () => {
            toast.success("Payment recorded");
            invalidateFeed();
        },
        onError: () => toast.error("Failed to record payment"),
    });

    const dismissTxnMut = useMutation({
        mutationFn: (vars: { txn_id: string; reason: string }) =>
            api.post(routes.paymentFeed.dismiss(vars.txn_id), { reason: vars.reason }, { getToken }),
        onSuccess: () => {
            toast.success("Transaction dismissed");
            setDismissingId(null);
            setDismissReason("");
            invalidateFeed();
        },
        onError: () => toast.error("Failed to dismiss transaction"),
    });

    // ---- Mutations: Stripe ----

    const createPaymentLinkMut = useMutationWithToast<{
        client_id: string;
        plan_id: string;
        amount: number;
        description: string;
        client_name: string;
        client_email: string;
    }>({
        mutationFn: (input) => api.post(routes.stripe.paymentLink, input, { getToken }),
        successMessage: "Payment link created",
        invalidateKeys: [[...queryKeys.stripe.paymentLinks]],
        onSuccess: () => {
            setLinkAmount("");
            setLinkDescription("");
            setLinkClientId("");
            setLinkClientName("");
            setLinkClientEmail("");
        },
    });

    // ---- Handlers ----

    const handleFileUpload = () => {
        const file = fileInputRef.current?.files?.[0];
        if (file) uploadCsvMut.mutate(file);
    };

    const handleCreateLink = () => {
        const amount = parseFloat(linkAmount);
        if (isNaN(amount) || amount <= 0) {
            toast.error("Please enter a valid amount");
            return;
        }
        createPaymentLinkMut.mutate({
            client_id: linkClientId,
            plan_id: "",
            amount,
            description: linkDescription,
            client_name: linkClientName,
            client_email: linkClientEmail,
        });
    };

    const copyToClipboard = async (text: string) => {
        try {
            await navigator.clipboard.writeText(text);
            toast.success("Copied to clipboard");
        } catch {
            toast.error("Failed to copy");
        }
    };

    // ---- Filter buttons for feed ----
    const filterOptions = [
        { key: "all", label: "All" },
        { key: "pending", label: "Pending" },
        { key: "recorded", label: "Recorded" },
        { key: "dismissed", label: "Dismissed" },
    ] as const;

    return (
        <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Payments</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Payment feed, Stripe integration, and accounts receivable
                </p>
            </div>

            {/* Tabs */}
            <Tabs defaultValue="feed">
                <TabsList>
                    <TabsTrigger value="feed">
                        Payment Feed
                        {feedItems.length > 0 && (
                            <Badge variant="secondary" className="ml-1 text-[10px] px-1.5">
                                {feedItems.length}
                            </Badge>
                        )}
                    </TabsTrigger>
                    <TabsTrigger value="stripe">Stripe</TabsTrigger>
                    <TabsTrigger value="ar">AR Overview</TabsTrigger>
                </TabsList>

                {/* ================================================================
                    TAB 1: PAYMENT FEED
                ================================================================ */}
                <TabsContent value="feed" className="space-y-6">
                    {/* Ingest Email Section */}
                    <Card className="glass-card">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium">Ingest Email</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <p className="text-xs text-muted-foreground">
                                Paste a payment notification email to auto-detect platform and classify the transaction.
                            </p>
                            <div className="space-y-2">
                                <div className="space-y-1">
                                    <Label htmlFor="email-subject" className="text-xs">Subject</Label>
                                    <Input
                                        id="email-subject"
                                        placeholder="e.g. John Smith paid you $150.00"
                                        value={emailSubject}
                                        onChange={(e) => setEmailSubject(e.target.value)}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <Label htmlFor="email-body" className="text-xs">Body</Label>
                                    <Textarea
                                        id="email-body"
                                        placeholder="Paste the full email body here..."
                                        value={emailBody}
                                        onChange={(e) => setEmailBody(e.target.value)}
                                        rows={4}
                                        className="font-mono text-xs"
                                    />
                                </div>
                                <div className="space-y-1">
                                    <Label htmlFor="email-sender" className="text-xs">Sender Email</Label>
                                    <Input
                                        id="email-sender"
                                        placeholder="e.g. venmo@venmo.com"
                                        value={emailSender}
                                        onChange={(e) => setEmailSender(e.target.value)}
                                    />
                                </div>
                                <Button
                                    size="sm"
                                    onClick={() =>
                                        ingestEmailMut.mutate({
                                            subject: emailSubject,
                                            body: emailBody,
                                            sender_email: emailSender,
                                        })
                                    }
                                    disabled={
                                        !emailSubject.trim() ||
                                        !emailBody.trim() ||
                                        ingestEmailMut.isPending
                                    }
                                >
                                    {ingestEmailMut.isPending ? "Processing..." : "Ingest"}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Upload CSV Section */}
                    <Card className="glass-card">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium">Upload CSV</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="flex items-center gap-3">
                                <Select value={csvPlatform} onValueChange={setCsvPlatform}>
                                    <SelectTrigger className="w-36">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="generic">Generic</SelectItem>
                                        <SelectItem value="venmo">Venmo</SelectItem>
                                        <SelectItem value="cashapp">Cash App</SelectItem>
                                        <SelectItem value="chime">Chime</SelectItem>
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
                                    disabled={uploadCsvMut.isPending}
                                >
                                    {uploadCsvMut.isPending ? "Uploading..." : "Upload"}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Filter Buttons */}
                    <div className="flex items-center gap-2">
                        {filterOptions.map((opt) => (
                            <Button
                                key={opt.key}
                                size="sm"
                                variant={feedFilter === opt.key ? "default" : "outline"}
                                onClick={() => setFeedFilter(opt.key)}
                                className="text-xs"
                            >
                                {opt.label}
                            </Button>
                        ))}
                    </div>

                    {/* Transaction List */}
                    {feedQuery.isLoading ? (
                        <div className="space-y-3">
                            {Array.from({ length: 4 }).map((_, i) => (
                                <Skeleton key={i} className="h-24 w-full rounded-lg" />
                            ))}
                        </div>
                    ) : feedQuery.error ? (
                        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
                            Failed to load transactions:{" "}
                            {feedQuery.error instanceof Error ? feedQuery.error.message : "Unknown error"}
                        </div>
                    ) : feedItems.length === 0 ? (
                        <Card>
                            <CardContent className="py-12 text-center text-muted-foreground">
                                {feedFilter === "all"
                                    ? "No transactions yet. Ingest an email or upload a CSV to get started."
                                    : `No ${feedFilter} transactions found.`}
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="space-y-3">
                            {feedItems.map((txn) => (
                                <Card key={txn.id} className="hover:border-primary/20 transition-colors">
                                    <CardContent className="py-4">
                                        <div className="flex items-start justify-between gap-4">
                                            <div className="flex-1 min-w-0 space-y-1.5">
                                                {/* Top row: platform, amount, sender, date */}
                                                <div className="flex items-center gap-2 flex-wrap">
                                                    <span
                                                        className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium capitalize ${PLATFORM_COLORS[txn.platform] || PLATFORM_COLORS.generic}`}
                                                    >
                                                        {txn.platform}
                                                    </span>
                                                    <span className="text-sm font-bold text-green-600 dark:text-green-400">
                                                        {formatCurrency(txn.amount)}
                                                    </span>
                                                    <span className="text-sm text-foreground">
                                                        from <span className="font-medium">{txn.sender || "Unknown"}</span>
                                                    </span>
                                                    <span className="text-xs text-muted-foreground">{txn.date}</span>
                                                </div>

                                                {/* Note */}
                                                {txn.note && (
                                                    <p className="text-xs text-muted-foreground truncate">
                                                        {txn.note}
                                                    </p>
                                                )}

                                                {/* Confidence bar + suggested client */}
                                                {txn.confidence > 0 && (
                                                    <div className="flex items-center gap-2">
                                                        <ConfidenceBar confidence={txn.confidence} />
                                                        {txn.suggested_client_name && (
                                                            <Badge variant="secondary" className="text-[10px]">
                                                                {txn.suggested_client_name}
                                                            </Badge>
                                                        )}
                                                    </div>
                                                )}

                                                {/* Status badge */}
                                                <div>
                                                    <StatusBadge status={txn.status} domain="feed_tx" size="sm" />
                                                </div>
                                            </div>

                                            {/* Action buttons */}
                                            <div className="flex flex-col gap-1.5 shrink-0">
                                                {txn.status !== "recorded" &&
                                                    txn.status !== "dismissed" &&
                                                    txn.suggested_client_id &&
                                                    txn.suggested_plan_id && (
                                                        <Button
                                                            size="sm"
                                                            className="text-xs"
                                                            onClick={() =>
                                                                classifyMut.mutate({
                                                                    txn_id: txn.id,
                                                                    client_id: txn.suggested_client_id!,
                                                                    plan_id: txn.suggested_plan_id!,
                                                                })
                                                            }
                                                            disabled={classifyMut.isPending}
                                                        >
                                                            Record
                                                        </Button>
                                                    )}
                                                {txn.status !== "recorded" && txn.status !== "dismissed" && (
                                                    <>
                                                        {dismissingId === txn.id ? (
                                                            <div className="flex flex-col gap-1">
                                                                <Input
                                                                    placeholder="Reason (optional)"
                                                                    value={dismissReason}
                                                                    onChange={(e) => setDismissReason(e.target.value)}
                                                                    className="text-xs h-7 w-32"
                                                                />
                                                                <div className="flex gap-1">
                                                                    <Button
                                                                        size="sm"
                                                                        variant="destructive"
                                                                        className="text-xs h-7 flex-1"
                                                                        onClick={() =>
                                                                            dismissTxnMut.mutate({
                                                                                txn_id: txn.id,
                                                                                reason: dismissReason,
                                                                            })
                                                                        }
                                                                        disabled={dismissTxnMut.isPending}
                                                                    >
                                                                        Confirm
                                                                    </Button>
                                                                    <Button
                                                                        size="sm"
                                                                        variant="ghost"
                                                                        className="text-xs h-7"
                                                                        onClick={() => {
                                                                            setDismissingId(null);
                                                                            setDismissReason("");
                                                                        }}
                                                                    >
                                                                        Cancel
                                                                    </Button>
                                                                </div>
                                                            </div>
                                                        ) : (
                                                            <Button
                                                                size="sm"
                                                                variant="ghost"
                                                                className="text-xs text-destructive hover:text-destructive"
                                                                onClick={() => setDismissingId(txn.id)}
                                                            >
                                                                Dismiss
                                                            </Button>
                                                        )}
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </TabsContent>

                {/* ================================================================
                    TAB 2: STRIPE
                ================================================================ */}
                <TabsContent value="stripe" className="space-y-6">
                    {/* Stripe Config Card */}
                    <Card className="glass-card">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium">Stripe Configuration</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {stripeConfigQuery.isLoading ? (
                                <Skeleton className="h-12 w-full rounded-lg" />
                            ) : stripeConfig ? (
                                <div className="flex items-center gap-4 flex-wrap">
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs text-muted-foreground">Status:</span>
                                        <Badge
                                            variant={stripeConfig.configured ? "default" : "destructive"}
                                            className="text-[10px]"
                                        >
                                            {stripeConfig.configured ? "Configured" : "Not Configured"}
                                        </Badge>
                                    </div>
                                    {stripeConfig.public_key && (
                                        <div className="flex items-center gap-2">
                                            <span className="text-xs text-muted-foreground">Key:</span>
                                            <span className="text-xs font-mono text-muted-foreground">
                                                {stripeConfig.public_key.slice(0, 12)}...{stripeConfig.public_key.slice(-4)}
                                            </span>
                                        </div>
                                    )}
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs text-muted-foreground">Webhook:</span>
                                        <Badge
                                            variant={stripeConfig.webhook_configured ? "default" : "outline"}
                                            className="text-[10px]"
                                        >
                                            {stripeConfig.webhook_configured ? "Active" : "Inactive"}
                                        </Badge>
                                    </div>
                                </div>
                            ) : (
                                <p className="text-xs text-muted-foreground">Unable to load Stripe configuration.</p>
                            )}
                        </CardContent>
                    </Card>

                    {/* Create Payment Link */}
                    <Card className="glass-card">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium">Create Payment Link</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <Label htmlFor="link-amount" className="text-xs">Amount ($)</Label>
                                    <Input
                                        id="link-amount"
                                        type="number"
                                        min="0"
                                        step="0.01"
                                        placeholder="0.00"
                                        value={linkAmount}
                                        onChange={(e) => setLinkAmount(e.target.value)}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <Label htmlFor="link-description" className="text-xs">Description</Label>
                                    <Input
                                        id="link-description"
                                        placeholder="e.g. Monthly retainer payment"
                                        value={linkDescription}
                                        onChange={(e) => setLinkDescription(e.target.value)}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <Label htmlFor="link-client-name" className="text-xs">Client Name</Label>
                                    <Input
                                        id="link-client-name"
                                        placeholder="e.g. John Smith"
                                        value={linkClientName}
                                        onChange={(e) => setLinkClientName(e.target.value)}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <Label htmlFor="link-client-email" className="text-xs">Client Email</Label>
                                    <Input
                                        id="link-client-email"
                                        placeholder="e.g. john@example.com"
                                        value={linkClientEmail}
                                        onChange={(e) => setLinkClientEmail(e.target.value)}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <Label htmlFor="link-client-id" className="text-xs">Client ID (optional)</Label>
                                    <Input
                                        id="link-client-id"
                                        placeholder="Client UUID"
                                        value={linkClientId}
                                        onChange={(e) => setLinkClientId(e.target.value)}
                                    />
                                </div>
                            </div>
                            <Button
                                size="sm"
                                onClick={handleCreateLink}
                                disabled={
                                    !linkAmount ||
                                    !linkClientName.trim() ||
                                    createPaymentLinkMut.isPending
                                }
                            >
                                {createPaymentLinkMut.isPending ? "Creating..." : "Create Payment Link"}
                            </Button>
                        </CardContent>
                    </Card>

                    {/* Payment Links List */}
                    <Card className="glass-card">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium">
                                Payment Links
                                {paymentLinks.length > 0 && (
                                    <Badge variant="secondary" className="ml-2 text-[10px]">
                                        {paymentLinks.length}
                                    </Badge>
                                )}
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {paymentLinksQuery.isLoading ? (
                                <div className="space-y-3">
                                    {Array.from({ length: 3 }).map((_, i) => (
                                        <Skeleton key={i} className="h-16 w-full rounded-lg" />
                                    ))}
                                </div>
                            ) : paymentLinks.length === 0 ? (
                                <p className="text-sm text-muted-foreground text-center py-8">
                                    No payment links created yet.
                                </p>
                            ) : (
                                <div className="space-y-2">
                                    {paymentLinks.map((link) => (
                                        <div
                                            key={link.id}
                                            className="flex items-center justify-between gap-4 py-3 border-b last:border-0"
                                        >
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-0.5">
                                                    <span className="text-sm font-medium">
                                                        {formatCurrency(link.amount)}
                                                    </span>
                                                    <StatusBadge status={link.status} domain="stripe" size="sm" />
                                                </div>
                                                <p className="text-xs text-muted-foreground truncate">
                                                    {link.client_name}
                                                    {link.description ? ` — ${link.description}` : ""}
                                                </p>
                                                <p className="text-[10px] text-muted-foreground">
                                                    Created {new Date(link.created_at).toLocaleDateString()}
                                                    {link.paid_at ? ` · Paid ${new Date(link.paid_at).toLocaleDateString()}` : ""}
                                                </p>
                                            </div>
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                className="text-xs shrink-0"
                                                onClick={() => copyToClipboard(link.url)}
                                            >
                                                Copy URL
                                            </Button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Checkout Sessions List */}
                    <Card className="glass-card">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium">
                                Checkout Sessions
                                {checkoutSessions.length > 0 && (
                                    <Badge variant="secondary" className="ml-2 text-[10px]">
                                        {checkoutSessions.length}
                                    </Badge>
                                )}
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {checkoutSessionsQuery.isLoading ? (
                                <div className="space-y-3">
                                    {Array.from({ length: 3 }).map((_, i) => (
                                        <Skeleton key={i} className="h-16 w-full rounded-lg" />
                                    ))}
                                </div>
                            ) : checkoutSessions.length === 0 ? (
                                <p className="text-sm text-muted-foreground text-center py-8">
                                    No checkout sessions yet.
                                </p>
                            ) : (
                                <div className="space-y-2">
                                    {checkoutSessions.map((session) => (
                                        <div
                                            key={session.id}
                                            className="flex items-center justify-between gap-4 py-3 border-b last:border-0"
                                        >
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-0.5">
                                                    <span className="text-sm font-medium">
                                                        {formatCurrency(session.amount)}
                                                    </span>
                                                    <StatusBadge status={session.status} domain="stripe" size="sm" />
                                                </div>
                                                <p className="text-xs text-muted-foreground truncate">
                                                    {session.client_name}
                                                    {session.description ? ` — ${session.description}` : ""}
                                                </p>
                                                <p className="text-[10px] text-muted-foreground">
                                                    Created {new Date(session.created_at).toLocaleDateString()}
                                                    {session.paid_at ? ` · Paid ${new Date(session.paid_at).toLocaleDateString()}` : ""}
                                                </p>
                                            </div>
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                className="text-xs shrink-0"
                                                onClick={() => copyToClipboard(session.url)}
                                            >
                                                Copy URL
                                            </Button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ================================================================
                    TAB 3: AR OVERVIEW
                ================================================================ */}
                <TabsContent value="ar" className="space-y-6">
                    {arQuery.isLoading ? (
                        <div className="space-y-6">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                {Array.from({ length: 4 }).map((_, i) => (
                                    <Skeleton key={i} className="h-24 w-full rounded-lg" />
                                ))}
                            </div>
                            <Skeleton className="h-64 w-full rounded-lg" />
                        </div>
                    ) : arQuery.error ? (
                        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
                            Failed to load AR overview:{" "}
                            {arQuery.error instanceof Error ? arQuery.error.message : "Unknown error"}
                        </div>
                    ) : ar ? (
                        <>
                            {/* Stat Cards */}
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <Card className="glass-card">
                                    <CardContent className="pt-4 pb-3 px-4">
                                        <p className="text-xs text-muted-foreground uppercase tracking-wider">
                                            Total Receivable
                                        </p>
                                        <p className="text-2xl font-bold mt-1">
                                            {formatCurrency(ar.total_receivable)}
                                        </p>
                                    </CardContent>
                                </Card>
                                <Card className="glass-card">
                                    <CardContent className="pt-4 pb-3 px-4">
                                        <p className="text-xs text-muted-foreground uppercase tracking-wider">
                                            Total Collected
                                        </p>
                                        <p className="text-2xl font-bold mt-1 text-green-600 dark:text-green-400">
                                            {formatCurrency(ar.total_collected)}
                                        </p>
                                    </CardContent>
                                </Card>
                                <Card className="glass-card">
                                    <CardContent className="pt-4 pb-3 px-4">
                                        <p className="text-xs text-muted-foreground uppercase tracking-wider">
                                            Total Overdue
                                        </p>
                                        <p className="text-2xl font-bold mt-1 text-red-600 dark:text-red-400">
                                            {formatCurrency(ar.total_overdue)}
                                        </p>
                                        {ar.overdue_count > 0 && (
                                            <p className="text-[10px] text-muted-foreground mt-0.5">
                                                {ar.overdue_count} overdue payment{ar.overdue_count !== 1 ? "s" : ""}
                                            </p>
                                        )}
                                    </CardContent>
                                </Card>
                                <Card className="glass-card">
                                    <CardContent className="pt-4 pb-3 px-4">
                                        <p className="text-xs text-muted-foreground uppercase tracking-wider">
                                            Active Plans
                                        </p>
                                        <p className="text-2xl font-bold mt-1 text-blue-600 dark:text-blue-400">
                                            {ar.active_plans}
                                        </p>
                                        <p className="text-[10px] text-muted-foreground mt-0.5">
                                            of {ar.total_plans} total
                                        </p>
                                    </CardContent>
                                </Card>
                            </div>

                            {/* Plans Table */}
                            <Card className="glass-card">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm font-medium">Payment Plans</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    {plans.length === 0 ? (
                                        <p className="text-sm text-muted-foreground text-center py-8">
                                            No payment plans found.
                                        </p>
                                    ) : (
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-sm">
                                                <thead className="sticky top-0 z-10 bg-background">
                                                    <tr className="border-b text-left">
                                                        <th className="pb-2 pr-4 text-xs font-medium text-muted-foreground">
                                                            Client
                                                        </th>
                                                        <th className="pb-2 pr-4 text-xs font-medium text-muted-foreground text-right">
                                                            Total
                                                        </th>
                                                        <th className="pb-2 pr-4 text-xs font-medium text-muted-foreground text-right">
                                                            Paid
                                                        </th>
                                                        <th className="pb-2 pr-4 text-xs font-medium text-muted-foreground text-right">
                                                            Remaining
                                                        </th>
                                                        <th className="pb-2 pr-4 text-xs font-medium text-muted-foreground">
                                                            Next Due
                                                        </th>
                                                        <th className="pb-2 pr-4 text-xs font-medium text-muted-foreground">
                                                            Status
                                                        </th>
                                                        <th className="pb-2 text-xs font-medium text-muted-foreground">
                                                            Health
                                                        </th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {plans.map((plan) => {
                                                        const health = deriveHealth(plan);
                                                        return (
                                                            <tr
                                                                key={plan.plan_id}
                                                                className="border-b last:border-0 hover:bg-muted/50 transition-colors"
                                                            >
                                                                <td className="py-3 pr-4 font-medium">
                                                                    {plan.client_name}
                                                                </td>
                                                                <td className="py-3 pr-4 text-right tabular-nums">
                                                                    {formatCurrency(plan.total_amount)}
                                                                </td>
                                                                <td className="py-3 pr-4 text-right tabular-nums text-green-600 dark:text-green-400">
                                                                    {formatCurrency(plan.total_paid)}
                                                                </td>
                                                                <td className="py-3 pr-4 text-right tabular-nums">
                                                                    {formatCurrency(plan.remaining)}
                                                                </td>
                                                                <td className="py-3 pr-4 text-xs text-muted-foreground">
                                                                    {plan.next_due_date
                                                                        ? new Date(plan.next_due_date).toLocaleDateString()
                                                                        : "---"}
                                                                </td>
                                                                <td className="py-3 pr-4">
                                                                    <StatusBadge status={plan.status} domain="generic" size="sm" />
                                                                </td>
                                                                <td className="py-3">
                                                                    <StatusBadge status={health} domain="plan_health" size="sm" />
                                                                </td>
                                                            </tr>
                                                        );
                                                    })}
                                                </tbody>
                                            </table>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </>
                    ) : null}
                </TabsContent>
            </Tabs>
        </div>
    );
}

// ---- Health derivation helper -------------------------------------------
// Derives a health label from the plan summary data for the AR table.

function deriveHealth(plan: PaymentPlanSummary): string {
    if (plan.status === "completed") return "completed";
    if (plan.status === "paused") return "paused";
    if (plan.status === "cancelled") return "cancelled";
    if ((plan.overdue_amount ?? 0) > 0) {
        // More than 20% overdue of total is at_risk, otherwise behind
        const ratio = (plan.overdue_amount ?? 0) / (plan.total_amount || 1);
        return ratio > 0.2 ? "at_risk" : "behind";
    }
    if (plan.total_paid > 0 && plan.remaining <= 0) return "completed";
    if (plan.total_paid >= plan.total_amount * 0.5 && plan.remaining > 0) return "ahead";
    return "on_track";
}
