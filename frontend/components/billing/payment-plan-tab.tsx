// ---- Payment Plan Tab ----------------------------------------------------
// Shows ALL payment plans for a client (active + completed).
// Each plan is an expandable card. "New Plan" is always available.
"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { toast } from "sonner";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PaymentSchedule } from "./payment-schedule";
import { RecordPaymentDialog, type PaymentInput } from "./record-payment-dialog";
import { AIPlanGenerator } from "./ai-plan-generator";
import type { PaymentPlan, PaymentPlanStatus, StripeConfig, StripePaymentLink } from "@/types/api";

// ---- Manual Create Plan Schema ------------------------------------------

const createPlanSchema = z.object({
    total_amount: z.number().min(1, "Total required"),
    down_payment: z.number().min(0).optional().default(0),
    recurring_amount: z.number().min(1, "Recurring amount required"),
    frequency: z.string().min(1, "Frequency required"),
    start_date: z.string().min(1, "Start date required"),
    client_name: z.string().max(400).optional().default(""),
    notes: z.string().max(5000).optional().default(""),
});
type CreatePlanInput = z.infer<typeof createPlanSchema>;

const createPlanFields: FieldConfig<CreatePlanInput>[] = [
    { name: "total_amount", label: "Total Amount ($)", type: "number", required: true, placeholder: "5000" },
    { name: "down_payment", label: "Down Payment ($)", type: "number", placeholder: "1000" },
    { name: "recurring_amount", label: "Recurring Amount ($)", type: "number", required: true, placeholder: "200" },
    {
        name: "frequency", label: "Frequency", type: "select", required: true, options: [
            { value: "weekly", label: "Weekly" },
            { value: "biweekly", label: "Bi-Weekly" },
            { value: "monthly", label: "Monthly" },
        ],
    },
    { name: "start_date", label: "Start Date", required: true, placeholder: "2026-03-10" },
    { name: "client_name", label: "Client Name", placeholder: "Jane Doe" },
    { name: "notes", label: "Notes", type: "textarea", placeholder: "Client prefers Friday payments" },
];

// ---- Status Badge -------------------------------------------------------

const STATUS_COLORS: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
    on_track: "default",
    ahead: "default",
    behind: "destructive",
    completed: "secondary",
    paused: "outline",
    cancelled: "outline",
    no_plan: "outline",
    active: "default",
};

const STATUS_LABELS: Record<string, string> = {
    on_track: "On Track",
    ahead: "Ahead",
    behind: "Behind",
    completed: "Completed",
    paused: "Paused",
    cancelled: "Cancelled",
    no_plan: "No Plan",
    active: "Active",
};

// ---- Component ----------------------------------------------------------

interface PaymentPlanTabProps {
    clientId: string;
    clientName?: string;
}

export function PaymentPlanTab({ clientId, clientName }: PaymentPlanTabProps) {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const { canEdit } = useRole();
    const [createOpen, setCreateOpen] = useState(false);
    const [showAI, setShowAI] = useState(false);
    const [expandedPlan, setExpandedPlan] = useState<string | null>(null);
    const [recordPlanId, setRecordPlanId] = useState<string | null>(null);
    const [deletePlanId, setDeletePlanId] = useState<string | null>(null);

    const plansKey = ["payment-plans", clientId];

    // Fetch all plans
    const plansQuery = useQuery({
        queryKey: plansKey,
        queryFn: () => api.get<{ plans: PaymentPlan[] }>(`/crm/clients/${clientId}/payment-plan`, { getToken }),
    });

    const plans = plansQuery.data?.plans ?? [];

    const invalidateAll = () => {
        queryClient.invalidateQueries({ queryKey: plansKey });
    };

    // Create plan mutation
    const createPlan = useMutationWithToast<CreatePlanInput>({
        mutationFn: (data) => api.post(`/crm/clients/${clientId}/payment-plan`, data, { getToken }),
        successMessage: "Payment plan created",
        invalidateKeys: [plansKey],
        onSuccess: () => {
            setCreateOpen(false);
            setShowAI(false);
        },
    });

    // Handle AI-parsed plan creation
    const handleAIParsed = (params: {
        total_amount: number;
        down_payment: number;
        recurring_amount: number;
        frequency: string;
        start_date: string;
        notes?: string;
    }) => {
        createPlan.mutate({
            total_amount: params.total_amount,
            down_payment: params.down_payment,
            recurring_amount: params.recurring_amount,
            frequency: params.frequency,
            start_date: params.start_date,
            client_name: clientName || "",
            notes: params.notes || "",
        });
    };

    // Loading state
    if (plansQuery.isLoading) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-20 rounded-lg" />
                <Skeleton className="h-48 rounded-lg" />
            </div>
        );
    }

    // Sort: active first, then by created_at desc
    const sortedPlans = [...plans].sort((a, b) => {
        const order: Record<string, number> = { active: 0, paused: 1, behind: 1, completed: 2, cancelled: 3 };
        const aOrder = order[a.status] ?? 1;
        const bOrder = order[b.status] ?? 1;
        if (aOrder !== bOrder) return aOrder - bOrder;
        return (b.created_at || "").localeCompare(a.created_at || "");
    });

    // Auto-expand the first plan if only one exists
    const effectiveExpanded = expandedPlan ?? (sortedPlans.length === 1 ? sortedPlans[0].id : null);

    return (
        <div className="space-y-4">
            {/* Header with New Plan button */}
            {canEdit && (
                <div className="flex items-center gap-2">
                    <Button size="sm" onClick={() => setShowAI(!showAI)}>
                        {showAI ? "Cancel" : "New Plan"}
                    </Button>
                    {!showAI && (
                        <Button variant="outline" size="sm" onClick={() => setCreateOpen(true)}>
                            Create Manually
                        </Button>
                    )}
                </div>
            )}

            {/* AI Plan Generator */}
            {showAI && canEdit && (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">Create Plan with AI</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <p className="text-xs text-muted-foreground">
                            Describe the payment arrangement in plain English.
                        </p>
                        <AIPlanGenerator
                            clientId={clientId}
                            clientName={clientName}
                            onPlanParsed={handleAIParsed}
                        />
                    </CardContent>
                </Card>
            )}

            {/* No plans message */}
            {sortedPlans.length === 0 && !showAI && (
                <Card className="border-dashed">
                    <CardContent className="py-8 text-center text-muted-foreground text-sm">
                        No payment plans yet. Create one to get started.
                    </CardContent>
                </Card>
            )}

            {/* Plan Cards */}
            {sortedPlans.map((plan) => (
                <PlanCard
                    key={plan.id}
                    plan={plan}
                    clientId={clientId}
                    clientName={clientName}
                    expanded={effectiveExpanded === plan.id}
                    onToggle={() => setExpandedPlan(effectiveExpanded === plan.id ? null : plan.id)}
                    onRecordPayment={() => setRecordPlanId(plan.id)}
                    onDelete={() => setDeletePlanId(plan.id)}
                    canEdit={canEdit}
                />
            ))}

            {/* Manual Create Dialog */}
            {canEdit && (
                <FormDialog
                    open={createOpen}
                    onOpenChange={setCreateOpen}
                    title="Create Payment Plan"
                    description="Set up a structured payment arrangement."
                    schema={createPlanSchema}
                    defaultValues={{
                        total_amount: 0,
                        down_payment: 0,
                        recurring_amount: 0,
                        frequency: "monthly",
                        start_date: new Date().toISOString().split("T")[0],
                        client_name: clientName || "",
                        notes: "",
                    }}
                    fields={createPlanFields}
                    onSubmit={(data) => createPlan.mutate(data)}
                    submitLabel="Create Plan"
                    isLoading={createPlan.isPending}
                />
            )}

            {/* Record Payment Dialog (shared, opens for whichever plan) */}
            {recordPlanId && (
                <RecordPaymentDialogWrapper
                    clientId={clientId}
                    planId={recordPlanId}
                    invalidateKey={plansKey}
                    onClose={() => setRecordPlanId(null)}
                />
            )}

            {/* Delete Confirm (shared) */}
            {deletePlanId && (
                <DeletePlanDialog
                    clientId={clientId}
                    planId={deletePlanId}
                    invalidateKey={plansKey}
                    onClose={() => setDeletePlanId(null)}
                />
            )}
        </div>
    );
}

// ---- Inline Record Payment Wrapper --------------------------------------

function RecordPaymentDialogWrapper({
    clientId,
    planId,
    invalidateKey,
    onClose,
}: {
    clientId: string;
    planId: string;
    invalidateKey: string[];
    onClose: () => void;
}) {
    const { getToken } = useAuth();

    const recordPayment = useMutationWithToast<PaymentInput>({
        mutationFn: (data) =>
            api.post(`/crm/clients/${clientId}/payment-plan/${planId}/payments`, data, { getToken }),
        successMessage: "Payment recorded",
        invalidateKeys: [invalidateKey],
        onSuccess: onClose,
    });

    return (
        <RecordPaymentDialog
            open
            onOpenChange={(open) => !open && onClose()}
            onSubmit={(data) => recordPayment.mutate(data)}
            isLoading={recordPayment.isPending}
        />
    );
}

// ---- Inline Delete Plan Dialog ------------------------------------------

function DeletePlanDialog({
    clientId,
    planId,
    invalidateKey,
    onClose,
}: {
    clientId: string;
    planId: string;
    invalidateKey: string[];
    onClose: () => void;
}) {
    const { getToken } = useAuth();

    const deletePlan = useMutationWithToast<void>({
        mutationFn: () =>
            api.delete(`/crm/clients/${clientId}/payment-plan/${planId}`, { getToken }),
        successMessage: "Payment plan deleted",
        invalidateKeys: [invalidateKey],
        onSuccess: onClose,
    });

    return (
        <ConfirmDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title="Delete Payment Plan"
            description="This will permanently delete this payment plan and all its payment history. This cannot be undone."
            onConfirm={() => deletePlan.mutate()}
            isLoading={deletePlan.isPending}
        />
    );
}

// ---- Individual Plan Card -----------------------------------------------

function PlanCard({
    plan,
    clientId,
    clientName,
    expanded,
    onToggle,
    onRecordPayment,
    onDelete,
    canEdit,
}: {
    plan: PaymentPlan;
    clientId: string;
    clientName?: string;
    expanded: boolean;
    onToggle: () => void;
    onRecordPayment: () => void;
    onDelete: () => void;
    canEdit: boolean;
}) {
    const { getToken } = useAuth();

    const stripeConfigQuery = useQuery({
        queryKey: ["stripe-config"],
        queryFn: () => api.get<StripeConfig>("/stripe/config", { getToken }),
        staleTime: 60_000,
    });

    const stripeLinksQuery = useQuery({
        queryKey: ["stripe-links", clientId, plan.id],
        queryFn: () => api.get<{ items: StripePaymentLink[] }>(`/stripe/payment-links?client_id=${clientId}`, { getToken }),
        enabled: expanded && !!stripeConfigQuery.data?.configured,
    });

    const createLinkMut = useMutation({
        mutationFn: (vars: { amount: number; description: string }) =>
            api.post<StripePaymentLink>("/stripe/payment-link", {
                client_id: clientId,
                plan_id: plan.id,
                amount: vars.amount,
                description: vars.description,
                client_name: clientName || "",
            }, { getToken }),
        onSuccess: (data) => {
            toast.success("Payment link created");
            // Copy to clipboard
            navigator.clipboard.writeText(data.url).then(() => {
                toast.info("Link copied to clipboard");
            }).catch(() => {});
            stripeLinksQuery.refetch();
        },
        onError: () => toast.error("Failed to create payment link"),
    });

    const statusQuery = useQuery({
        queryKey: ["payment-plan-status", clientId, plan.id],
        queryFn: () =>
            api.get<PaymentPlanStatus>(
                `/crm/clients/${clientId}/payment-plan/${plan.id}/status`,
                { getToken },
            ),
        enabled: expanded,
    });

    const updatePlanStatus = useMutationWithToast<{ status: string }>({
        mutationFn: (data) =>
            api.put(`/crm/clients/${clientId}/payment-plan/${plan.id}`, data, { getToken }),
        successMessage: "Plan updated",
        invalidateKeys: [["payment-plans", clientId], ["payment-plan-status", clientId, plan.id]],
    });

    const status = statusQuery.data;
    const displayStatus = status?.status || plan.status;
    const statusLabel = STATUS_LABELS[displayStatus] || displayStatus;
    const statusVariant = STATUS_COLORS[displayStatus] || "outline";

    // Quick summary for collapsed state
    const totalPaid = plan.payments.reduce((s, p) => s + p.amount, 0);
    const pctDone = plan.total_amount > 0 ? Math.round((totalPaid / plan.total_amount) * 100) : 0;

    const isTerminal = plan.status === "completed" || plan.status === "cancelled";

    return (
        <Card className={isTerminal ? "opacity-75" : ""}>
            {/* Collapsed Header — always visible */}
            <CardHeader
                className="pb-2 cursor-pointer hover:bg-accent/30 transition-colors rounded-t-lg"
                onClick={onToggle}
            >
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <span className="text-xs text-muted-foreground">
                            {expanded ? "▼" : "▶"}
                        </span>
                        <div>
                            <CardTitle className="text-sm font-medium">
                                ${plan.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                <span className="text-muted-foreground font-normal ml-2 text-xs capitalize">
                                    {plan.frequency} &middot; ${plan.recurring_amount.toLocaleString()}/payment
                                </span>
                            </CardTitle>
                            <p className="text-[10px] text-muted-foreground mt-0.5">
                                {plan.start_date}
                                {plan.notes && ` — ${plan.notes.slice(0, 60)}${plan.notes.length > 60 ? "..." : ""}`}
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="text-right">
                            <p className="text-xs font-medium text-emerald-500">
                                ${totalPaid.toLocaleString(undefined, { minimumFractionDigits: 2 })} paid
                            </p>
                            <p className="text-[10px] text-muted-foreground">{pctDone}%</p>
                        </div>
                        <Badge variant={statusVariant} className="text-[10px]">
                            {statusLabel}
                        </Badge>
                    </div>
                </div>
                {/* Mini progress bar */}
                {pctDone > 0 && (
                    <div className="w-full bg-accent rounded-full h-1 mt-2">
                        <div
                            className="bg-emerald-500 h-1 rounded-full transition-all duration-500"
                            style={{ width: `${Math.min(pctDone, 100)}%` }}
                        />
                    </div>
                )}
            </CardHeader>

            {/* Expanded Details */}
            {expanded && (
                <CardContent className="space-y-4 pt-2">
                    {/* Status Cards */}
                    {status && (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <div className="rounded-lg border p-3">
                                <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Paid</p>
                                <p className="text-lg font-bold text-emerald-500">
                                    ${status.total_paid.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                </p>
                                <p className="text-[10px] text-muted-foreground">{status.percent_complete}%</p>
                            </div>
                            <div className="rounded-lg border p-3">
                                <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Remaining</p>
                                <p className="text-lg font-bold">
                                    ${status.remaining.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                </p>
                            </div>
                            <div className={`rounded-lg border p-3 ${status.overdue_count > 0 ? "border-red-500/30 bg-red-500/5" : ""}`}>
                                <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Overdue</p>
                                <p className={`text-lg font-bold ${status.overdue_count > 0 ? "text-destructive" : ""}`}>
                                    ${status.overdue_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                </p>
                                {status.overdue_count > 0 && (
                                    <p className="text-[10px] text-destructive">{status.overdue_count} payment(s)</p>
                                )}
                            </div>
                            <div className="rounded-lg border p-3">
                                <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Next Due</p>
                                <p className="text-sm font-bold mt-1">
                                    {status.next_due_date || "—"}
                                </p>
                                {status.next_due_amount > 0 && (
                                    <p className="text-[10px] text-muted-foreground">
                                        ${status.next_due_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                    </p>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Schedule Table */}
                    <div>
                        <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">
                            Payment Schedule
                        </p>
                        <PaymentSchedule schedule={plan.scheduled_payments} />
                    </div>

                    {/* Actions */}
                    {canEdit && (
                        <div className="flex flex-wrap items-center gap-2 pt-2 border-t">
                            {plan.status === "active" && (
                                <>
                                    <Button size="sm" onClick={onRecordPayment}>
                                        Record Payment
                                    </Button>
                                    {stripeConfigQuery.data?.configured && status && status.next_due_amount > 0 && (
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => createLinkMut.mutate({
                                                amount: status.next_due_amount,
                                                description: `Payment — ${clientName || "Client"} — $${status.next_due_amount.toLocaleString()}`,
                                            })}
                                            disabled={createLinkMut.isPending}
                                        >
                                            {createLinkMut.isPending ? "Creating..." : "💳 Send Payment Link"}
                                        </Button>
                                    )}
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => updatePlanStatus.mutate({ status: "paused" })}
                                    >
                                        Pause
                                    </Button>
                                </>
                            )}
                            {plan.status === "paused" && (
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => updatePlanStatus.mutate({ status: "active" })}
                                >
                                    Resume
                                </Button>
                            )}
                            {!isTerminal && (
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => updatePlanStatus.mutate({ status: "cancelled" })}
                                >
                                    Cancel Plan
                                </Button>
                            )}
                            <Button
                                size="sm"
                                variant="ghost"
                                className="text-destructive hover:text-destructive"
                                onClick={onDelete}
                            >
                                Delete
                            </Button>
                        </div>
                    )}

                    {/* Stripe Payment Links */}
                    {stripeConfigQuery.data?.configured && (stripeLinksQuery.data?.items?.length ?? 0) > 0 && (
                        <div className="pt-2 border-t">
                            <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">
                                Payment Links
                            </p>
                            <div className="divide-y">
                                {stripeLinksQuery.data!.items
                                    .filter((l) => l.plan_id === plan.id)
                                    .map((link) => (
                                    <div key={link.id} className="flex items-center justify-between py-2">
                                        <div>
                                            <p className="text-sm font-medium">
                                                ${link.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                                <Badge
                                                    variant={link.status === "paid" ? "default" : "outline"}
                                                    className="ml-2 text-[10px]"
                                                >
                                                    {link.status}
                                                </Badge>
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                {new Date(link.created_at).toLocaleDateString()}
                                                {" · "}
                                                {link.description}
                                            </p>
                                        </div>
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            className="text-xs"
                                            onClick={() => {
                                                navigator.clipboard.writeText(link.url);
                                                toast.success("Link copied to clipboard");
                                            }}
                                        >
                                            Copy Link
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Payment History */}
                    {plan.payments.length > 0 && (
                        <div className="pt-2 border-t">
                            <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">
                                Payment History ({plan.payments.length})
                            </p>
                            <div className="divide-y">
                                {plan.payments.slice().reverse().map((p) => (
                                    <div key={p.id} className="flex items-center justify-between py-2">
                                        <div>
                                            <p className="text-sm font-medium">
                                                ${p.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                                {p.method && (
                                                    <span className="text-muted-foreground text-xs ml-2 capitalize">
                                                        via {p.method}
                                                    </span>
                                                )}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                {p.date}
                                                {p.payer_name && ` — ${p.payer_name}`}
                                                {p.note && ` — ${p.note}`}
                                            </p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </CardContent>
            )}
        </Card>
    );
}
