// ---- Client Portal Page (Rewrite) ----------------------------------------
// Full client dashboard with case status, deadlines, documents, invoices,
// messages, and payment summary. Staff can view portal as any client.
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { routes } from "@/lib/api-routes";
import { queryKeys } from "@/lib/query-keys";
import {
    formatDate,
    formatRelativeTime,
    formatCurrency,
    PORTAL_INVOICE_COLORS,
} from "@/lib/constants";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type {
    PortalDocument,
    PortalInvoice,
    PortalMessage,
    PortalDeadline,
    PortalPaymentPlan,
} from "@/types/api";

// ---- Types --------------------------------------------------------------

interface ClientItem {
    id: string;
    name: string;
    first_name: string;
    last_name: string;
    email: string;
}

interface PortalStatus {
    client_id: string;
    client_name: string;
    cases: Array<{
        id: string;
        name: string;
        phase: string;
        sub_phase: string;
        case_type: string;
        last_updated: string;
        next_court_date: { date: string; title: string } | null;
    }>;
    payment_summary: {
        plan_id: string;
        total_amount: number;
        total_paid: number;
        remaining: number;
        status: string;
        next_due_date: string | null;
        next_due_amount: number;
    } | null;
    recent_communications: Array<{
        subject: string;
        channel: string;
        sent_at: string;
        status: string;
    }>;
}

// ---- Phase color helper -------------------------------------------------

function phaseColor(phase: string): string {
    switch (phase?.toLowerCase()) {
        case "active": return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
        case "closed": return "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";
        case "archived": return "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";
        default: return "bg-blue-500/15 text-blue-400 border-blue-500/30";
    }
}

function daysUntilColor(days: number): string {
    if (days <= 3) return "text-red-400";
    if (days <= 7) return "text-amber-400";
    if (days <= 14) return "text-blue-400";
    return "text-muted-foreground";
}

// ---- Client Selector ----------------------------------------------------

function ClientSelector({
    onSelect,
}: {
    onSelect: (clientId: string) => void;
}) {
    const { getToken } = useAuth();
    const [searchQ, setSearchQ] = useState("");

    const clientsQuery = useQuery({
        queryKey: queryKeys.crm.clients,
        queryFn: () => api.get<{ items: ClientItem[] }>(routes.crm.clients, { getToken }),
    });

    const clients = clientsQuery.data?.items ?? [];
    const filtered = searchQ
        ? clients.filter((c) => {
            const name = c.name || `${c.first_name} ${c.last_name}`;
            return (
                name.toLowerCase().includes(searchQ.toLowerCase()) ||
                (c.email || "").toLowerCase().includes(searchQ.toLowerCase())
            );
        })
        : clients;

    return (
        <div className="space-y-4">
            <Input
                placeholder="Search clients by name or email..."
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                className="max-w-sm"
            />
            {clientsQuery.isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-16 w-full rounded-lg" />
                    ))}
                </div>
            ) : filtered.length === 0 ? (
                <Card className="border-dashed">
                    <CardContent className="py-8 text-center text-muted-foreground">
                        {searchQ ? "No clients match your search" : "No clients found"}
                    </CardContent>
                </Card>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {filtered.map((c) => (
                        <Card
                            key={c.id}
                            className="cursor-pointer hover:border-primary/40 transition-colors"
                            onClick={() => onSelect(c.id)}
                        >
                            <CardContent className="py-3 flex items-center justify-between">
                                <div>
                                    <p className="text-sm font-medium">
                                        {c.name || `${c.first_name} ${c.last_name}`.trim()}
                                    </p>
                                    {c.email && (
                                        <p className="text-xs text-muted-foreground">{c.email}</p>
                                    )}
                                </div>
                                <Badge variant="outline" className="text-xs">View Portal</Badge>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}

// ---- Case Status Cards --------------------------------------------------

function CaseStatusCards({ cases }: { cases: PortalStatus["cases"] }) {
    if (cases.length === 0) {
        return (
            <Card className="border-dashed">
                <CardContent className="py-6 text-center text-muted-foreground text-sm">
                    No linked cases
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {cases.map((c) => (
                <Card key={c.id}>
                    <CardContent className="py-3">
                        <div className="flex items-center justify-between mb-2">
                            <p className="text-sm font-medium truncate">{c.name}</p>
                            <Badge className={cn("text-[10px] shrink-0", phaseColor(c.phase))}>
                                {c.phase}
                            </Badge>
                        </div>
                        <div className="flex items-center gap-2">
                            {c.case_type && (
                                <Badge variant="secondary" className="text-[10px]">{c.case_type}</Badge>
                            )}
                            {c.sub_phase && (
                                <span className="text-[10px] text-muted-foreground">{c.sub_phase}</span>
                            )}
                        </div>
                        {c.next_court_date && (
                            <div className="mt-2 pt-2 border-t text-xs">
                                <span className="text-muted-foreground">Next: </span>
                                <span className="font-medium">{c.next_court_date.title}</span>
                                <span className="text-muted-foreground"> on </span>
                                <span>{formatDate(c.next_court_date.date)}</span>
                            </div>
                        )}
                        {c.last_updated && (
                            <p className="text-[10px] text-muted-foreground mt-1">
                                Updated {formatRelativeTime(c.last_updated)}
                            </p>
                        )}
                    </CardContent>
                </Card>
            ))}
        </div>
    );
}

// ---- Deadlines Section --------------------------------------------------

function DeadlinesSection({ clientId }: { clientId: string }) {
    const { getToken } = useAuth();

    const deadlinesQuery = useQuery({
        queryKey: [...queryKeys.portal.deadlines(clientId)],
        queryFn: () =>
            api.get<{ deadlines: PortalDeadline[]; total: number }>(
                routes.portal.deadlines(clientId),
                { getToken },
            ),
    });

    const deadlines = deadlinesQuery.data?.deadlines ?? [];

    if (deadlinesQuery.isLoading) {
        return <Skeleton className="h-32 w-full" />;
    }

    if (deadlines.length === 0) {
        return (
            <Card className="border-dashed">
                <CardContent className="py-6 text-center text-muted-foreground text-sm">
                    No upcoming deadlines
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-base">Upcoming Deadlines</CardTitle>
                <CardDescription className="text-xs">
                    {deadlines.length} upcoming event{deadlines.length !== 1 ? "s" : ""}
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="space-y-2">
                    {deadlines.slice(0, 10).map((dl) => (
                        <div
                            key={dl.id}
                            className="flex items-center gap-3 py-2 border-b last:border-0"
                        >
                            {/* Date column */}
                            <div className="w-16 text-center shrink-0">
                                <p className={cn("text-sm font-bold tabular-nums", daysUntilColor(dl.days_until))}>
                                    {dl.days_until <= 0 ? "Today" : `${dl.days_until}d`}
                                </p>
                                <p className="text-[10px] text-muted-foreground">{formatDate(dl.date)}</p>
                            </div>

                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium truncate">{dl.title}</p>
                                <div className="flex items-center gap-2 mt-0.5">
                                    <Badge variant="secondary" className="text-[10px]">
                                        {dl.event_type}
                                    </Badge>
                                    {dl.time && (
                                        <span className="text-[10px] text-muted-foreground">{dl.time}</span>
                                    )}
                                    {dl.location && (
                                        <span className="text-[10px] text-muted-foreground truncate">
                                            {dl.location}
                                        </span>
                                    )}
                                </div>
                            </div>

                            <Badge variant="outline" className="text-[10px] shrink-0">
                                {dl.status}
                            </Badge>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

// ---- Documents Section --------------------------------------------------

function DocumentsSection({ clientId }: { clientId: string }) {
    const { getToken } = useAuth();

    const docsQuery = useQuery({
        queryKey: [...queryKeys.portal.documents(clientId)],
        queryFn: () =>
            api.get<{ documents: PortalDocument[]; total: number }>(
                routes.portal.documents(clientId),
                { getToken },
            ),
    });

    const documents = docsQuery.data?.documents ?? [];

    if (docsQuery.isLoading) {
        return <Skeleton className="h-32 w-full" />;
    }

    if (documents.length === 0) {
        return (
            <Card className="border-dashed">
                <CardContent className="py-6 text-center text-muted-foreground text-sm">
                    No client-visible documents
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-base">Documents</CardTitle>
                <CardDescription className="text-xs">
                    {documents.length} document{documents.length !== 1 ? "s" : ""} available
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="space-y-2">
                    {documents.map((doc, i) => (
                        <div
                            key={i}
                            className="flex items-center gap-3 py-2 border-b last:border-0"
                        >
                            <div className="flex h-8 w-8 items-center justify-center rounded bg-muted text-xs font-mono shrink-0">
                                {doc.filename.split(".").pop()?.toUpperCase()?.slice(0, 3) || "DOC"}
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm truncate">{doc.filename}</p>
                                <div className="flex items-center gap-2 mt-0.5">
                                    <span className="text-[10px] text-muted-foreground">
                                        {doc.case_name}
                                    </span>
                                    {doc.tags?.map((tag) => (
                                        <Badge key={tag} variant="secondary" className="text-[10px]">
                                            {tag}
                                        </Badge>
                                    ))}
                                </div>
                            </div>
                            <span className="text-[10px] text-muted-foreground shrink-0">
                                {formatDate(doc.uploaded_at)}
                            </span>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

// ---- Invoices Section ---------------------------------------------------

function InvoicesSection({ clientId }: { clientId: string }) {
    const { getToken } = useAuth();

    const invoicesQuery = useQuery({
        queryKey: [...queryKeys.portal.invoices(clientId)],
        queryFn: () =>
            api.get<{
                invoices: PortalInvoice[];
                payment_plans: PortalPaymentPlan[];
                total_invoices: number;
            }>(
                routes.portal.invoices(clientId),
                { getToken },
            ),
    });

    const invoices = invoicesQuery.data?.invoices ?? [];
    const paymentPlans = invoicesQuery.data?.payment_plans ?? [];

    if (invoicesQuery.isLoading) {
        return <Skeleton className="h-32 w-full" />;
    }

    return (
        <div className="space-y-4">
            {/* Payment plan summary */}
            {paymentPlans.length > 0 && (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Payment Plan</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {paymentPlans.map((plan) => {
                            const pct = plan.total_amount > 0
                                ? Math.round((plan.total_paid / plan.total_amount) * 100)
                                : 0;

                            return (
                                <div key={plan.id} className="space-y-3">
                                    <div className="grid grid-cols-3 gap-4">
                                        <div>
                                            <p className="text-xs text-muted-foreground">Total</p>
                                            <p className="text-lg font-bold">{formatCurrency(plan.total_amount)}</p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-muted-foreground">Paid</p>
                                            <p className="text-lg font-bold text-emerald-400">
                                                {formatCurrency(plan.total_paid)}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-muted-foreground">Remaining</p>
                                            <p className="text-lg font-bold">{formatCurrency(plan.remaining)}</p>
                                        </div>
                                    </div>

                                    <div>
                                        <div className="flex items-center justify-between text-xs mb-1">
                                            <span className="text-muted-foreground">Progress</span>
                                            <span className="font-medium">{pct}%</span>
                                        </div>
                                        <Progress value={pct} className="h-2" />
                                    </div>

                                    {plan.upcoming_payments.length > 0 && (
                                        <>
                                            <Separator />
                                            <div className="space-y-1">
                                                <p className="text-xs text-muted-foreground font-medium">
                                                    Upcoming Payments
                                                </p>
                                                {plan.upcoming_payments.map((up, i) => (
                                                    <div
                                                        key={i}
                                                        className="flex items-center justify-between text-xs"
                                                    >
                                                        <span>{formatDate(up.due_date)}</span>
                                                        <div className="flex items-center gap-2">
                                                            <span className="font-medium tabular-nums">
                                                                {formatCurrency(up.amount)}
                                                            </span>
                                                            <Badge
                                                                className={cn(
                                                                    "text-[10px]",
                                                                    PORTAL_INVOICE_COLORS[up.status] || PORTAL_INVOICE_COLORS.draft,
                                                                )}
                                                            >
                                                                {up.status}
                                                            </Badge>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </>
                                    )}
                                </div>
                            );
                        })}
                    </CardContent>
                </Card>
            )}

            {/* Invoices list */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base">Invoices</CardTitle>
                    <CardDescription className="text-xs">
                        {invoices.length} invoice{invoices.length !== 1 ? "s" : ""}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {invoices.length === 0 ? (
                        <p className="text-sm text-muted-foreground text-center py-4">
                            No invoices found
                        </p>
                    ) : (
                        <div className="space-y-2">
                            {invoices.map((inv) => (
                                <div
                                    key={inv.id}
                                    className="flex items-center gap-3 py-2 border-b last:border-0"
                                >
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <p className="text-sm font-medium">
                                                {inv.invoice_number || inv.id.slice(0, 8)}
                                            </p>
                                            <Badge
                                                className={cn(
                                                    "text-[10px]",
                                                    PORTAL_INVOICE_COLORS[inv.status] || PORTAL_INVOICE_COLORS.draft,
                                                )}
                                            >
                                                {inv.status}
                                            </Badge>
                                        </div>
                                        <p className="text-[10px] text-muted-foreground mt-0.5">
                                            Due {formatDate(inv.due_date)}
                                        </p>
                                    </div>
                                    <div className="text-right shrink-0">
                                        <p className="text-sm font-bold tabular-nums">
                                            {formatCurrency(inv.balance_due)}
                                        </p>
                                        {inv.amount_paid > 0 && (
                                            <p className="text-[10px] text-emerald-400">
                                                Paid: {formatCurrency(inv.amount_paid)}
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

// ---- Messages Section ---------------------------------------------------

function MessagesSection({ clientId }: { clientId: string }) {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [subject, setSubject] = useState("");
    const [message, setMessage] = useState("");

    const messagesQuery = useQuery({
        queryKey: [...queryKeys.portal.messages(clientId)],
        queryFn: () =>
            api.get<{ messages: PortalMessage[]; total: number }>(
                routes.portal.messages(clientId),
                { getToken },
            ),
    });

    const sendMutation = useMutation({
        mutationFn: () =>
            api.post(
                routes.portal.messages(clientId),
                { subject, message },
                { getToken },
            ),
        onSuccess: () => {
            toast.success("Message sent");
            setSubject("");
            setMessage("");
            queryClient.invalidateQueries({
                queryKey: [...queryKeys.portal.messages(clientId)],
            });
        },
        onError: () => toast.error("Failed to send message"),
    });

    const messages = messagesQuery.data?.messages ?? [];

    if (messagesQuery.isLoading) {
        return <Skeleton className="h-48 w-full" />;
    }

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-base">Messages</CardTitle>
                <CardDescription className="text-xs">
                    {messages.length} message{messages.length !== 1 ? "s" : ""}
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Message thread */}
                <div className="space-y-3 max-h-[400px] overflow-y-auto">
                    {messages.length === 0 ? (
                        <p className="text-sm text-muted-foreground text-center py-4">
                            No messages yet
                        </p>
                    ) : (
                        messages.map((msg) => {
                            const isInbound = msg.direction === "client_to_firm";
                            return (
                                <div
                                    key={msg.id}
                                    className={cn(
                                        "rounded-lg p-3 max-w-[85%]",
                                        isInbound
                                            ? "bg-primary/10 ml-auto"
                                            : "bg-muted mr-auto",
                                    )}
                                >
                                    <div className="flex items-center gap-2 mb-1">
                                        <Badge
                                            variant="outline"
                                            className="text-[10px]"
                                        >
                                            {isInbound ? "You" : "Firm"}
                                        </Badge>
                                        <span className="text-[10px] text-muted-foreground">
                                            {formatRelativeTime(msg.sent_at)}
                                        </span>
                                    </div>
                                    {msg.subject && (
                                        <p className="text-xs font-medium">{msg.subject}</p>
                                    )}
                                    <p className="text-sm mt-1 whitespace-pre-wrap">{msg.body}</p>
                                </div>
                            );
                        })
                    )}
                </div>

                <Separator />

                {/* Message input */}
                <div className="space-y-3">
                    <Input
                        placeholder="Subject..."
                        value={subject}
                        onChange={(e) => setSubject(e.target.value)}
                    />
                    <Textarea
                        placeholder="Type your message..."
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        rows={3}
                    />
                    <div className="flex justify-end">
                        <Button
                            onClick={() => sendMutation.mutate()}
                            disabled={sendMutation.isPending || !subject.trim() || !message.trim()}
                            size="sm"
                        >
                            {sendMutation.isPending ? "Sending..." : "Send Message"}
                        </Button>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

// ---- Portal Detail View -------------------------------------------------

function PortalDetail({
    clientId,
    onBack,
}: {
    clientId: string;
    onBack: () => void;
}) {
    const { getToken } = useAuth();

    // Fetch portal status (cases + payment summary + recent comms)
    const portalQuery = useQuery({
        queryKey: [...queryKeys.portal.status(clientId)],
        queryFn: () =>
            api.get<PortalStatus>(
                routes.portal.clientStatus(clientId),
                { getToken },
            ),
    });

    const portal = portalQuery.data;

    if (portalQuery.isLoading) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-8 w-48" />
                <Skeleton className="h-32 w-full" />
                <Skeleton className="h-48 w-full" />
            </div>
        );
    }

    if (!portal) {
        return (
            <Card>
                <CardContent className="py-8 text-center text-muted-foreground">
                    Failed to load portal data.
                    <Button variant="ghost" size="sm" className="ml-2" onClick={onBack}>
                        Go back
                    </Button>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center gap-3">
                <Button variant="ghost" size="sm" onClick={onBack}>
                    &larr; Back
                </Button>
                <div>
                    <h2 className="text-lg font-semibold">{portal.client_name}</h2>
                    <p className="text-xs text-muted-foreground">
                        {portal.cases.length} case{portal.cases.length !== 1 ? "s" : ""} linked
                    </p>
                </div>
            </div>

            {/* Case Status Cards */}
            <div>
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                    Case Status
                </h3>
                <CaseStatusCards cases={portal.cases} />
            </div>

            {/* Tabbed sections */}
            <Tabs defaultValue="deadlines" className="space-y-4">
                <TabsList variant="line">
                    <TabsTrigger value="deadlines">Deadlines</TabsTrigger>
                    <TabsTrigger value="documents">Documents</TabsTrigger>
                    <TabsTrigger value="invoices">Invoices</TabsTrigger>
                    <TabsTrigger value="messages">Messages</TabsTrigger>
                </TabsList>

                <TabsContent value="deadlines">
                    <DeadlinesSection clientId={clientId} />
                </TabsContent>

                <TabsContent value="documents">
                    <DocumentsSection clientId={clientId} />
                </TabsContent>

                <TabsContent value="invoices">
                    <InvoicesSection clientId={clientId} />
                </TabsContent>

                <TabsContent value="messages">
                    <MessagesSection clientId={clientId} />
                </TabsContent>
            </Tabs>

            {/* Payment Summary (always visible at bottom) */}
            {portal.payment_summary && (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Payment Overview</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div>
                                <p className="text-xs text-muted-foreground">Total</p>
                                <p className="text-lg font-bold">
                                    {formatCurrency(portal.payment_summary.total_amount)}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-muted-foreground">Paid</p>
                                <p className="text-lg font-bold text-emerald-400">
                                    {formatCurrency(portal.payment_summary.total_paid)}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-muted-foreground">Remaining</p>
                                <p className="text-lg font-bold">
                                    {formatCurrency(portal.payment_summary.remaining)}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-muted-foreground">Status</p>
                                <Badge variant="outline" className="mt-1">
                                    {portal.payment_summary.status}
                                </Badge>
                            </div>
                        </div>
                        {portal.payment_summary.next_due_date && (
                            <div className="mt-3 pt-3 border-t flex justify-between text-sm">
                                <span className="text-muted-foreground">Next payment due</span>
                                <span>
                                    {formatCurrency(portal.payment_summary.next_due_amount)} on{" "}
                                    {formatDate(portal.payment_summary.next_due_date)}
                                </span>
                            </div>
                        )}
                        {portal.payment_summary.total_amount > 0 && (
                            <Progress
                                value={Math.round(
                                    (portal.payment_summary.total_paid / portal.payment_summary.total_amount) * 100,
                                )}
                                className="h-2 mt-3"
                            />
                        )}
                    </CardContent>
                </Card>
            )}
        </div>
    );
}

// ---- Main Page ----------------------------------------------------------

export default function ClientPortalPage() {
    const [selectedClientId, setSelectedClientId] = useState<string | null>(null);

    return (
        <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Client Portal</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Case status, deadlines, documents, invoices, and messaging
                </p>
            </div>

            {!selectedClientId ? (
                <ClientSelector onSelect={setSelectedClientId} />
            ) : (
                <PortalDetail
                    clientId={selectedClientId}
                    onBack={() => setSelectedClientId(null)}
                />
            )}
        </div>
    );
}
