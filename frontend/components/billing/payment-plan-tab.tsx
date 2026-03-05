// ---- Payment Plan Tab ----------------------------------------------------
// Main tab content for payment plan management within a client's page.
"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
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
import type { PaymentPlan, PaymentPlanStatus } from "@/types/api";

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
};

const STATUS_LABELS: Record<string, string> = {
    on_track: "On Track",
    ahead: "Ahead",
    behind: "Behind",
    completed: "Completed",
    paused: "Paused",
    cancelled: "Cancelled",
    no_plan: "No Plan",
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
    const [recordOpen, setRecordOpen] = useState(false);
    const [deleteOpen, setDeleteOpen] = useState(false);

    const planKeys = {
        plan: ["payment-plan", clientId],
        status: ["payment-plan-status", clientId],
    };

    // Fetch plan
    const planQuery = useQuery({
        queryKey: planKeys.plan,
        queryFn: () => api.get<{ plan: PaymentPlan | null }>(`/crm/clients/${clientId}/payment-plan`, { getToken }),
    });

    // Fetch status
    const statusQuery = useQuery({
        queryKey: planKeys.status,
        queryFn: () => api.get<PaymentPlanStatus>(`/crm/clients/${clientId}/payment-plan/status`, { getToken }),
    });

    const plan = planQuery.data?.plan ?? null;
    const status = statusQuery.data;

    const invalidateAll = () => {
        queryClient.invalidateQueries({ queryKey: planKeys.plan });
        queryClient.invalidateQueries({ queryKey: planKeys.status });
    };

    // Create plan mutation
    const createPlan = useMutationWithToast<CreatePlanInput>({
        mutationFn: (data) => api.post(`/crm/clients/${clientId}/payment-plan`, data, { getToken }),
        successMessage: "Payment plan created",
        invalidateKeys: [planKeys.plan, planKeys.status],
        onSuccess: () => setCreateOpen(false),
    });

    // Record payment mutation
    const recordPayment = useMutationWithToast<PaymentInput>({
        mutationFn: (data) => api.post(`/crm/clients/${clientId}/payment-plan/payments`, data, { getToken }),
        successMessage: "Payment recorded",
        invalidateKeys: [planKeys.plan, planKeys.status],
        onSuccess: () => setRecordOpen(false),
    });

    // Update plan status (pause/resume/cancel)
    const updatePlanStatus = useMutationWithToast<{ status: string }>({
        mutationFn: (data) => api.put(`/crm/clients/${clientId}/payment-plan`, data, { getToken }),
        successMessage: "Plan updated",
        invalidateKeys: [planKeys.plan, planKeys.status],
    });

    // Delete plan mutation
    const deletePlan = useMutationWithToast<void>({
        mutationFn: () => api.delete(`/crm/clients/${clientId}/payment-plan`, { getToken }),
        successMessage: "Payment plan deleted",
        invalidateKeys: [planKeys.plan, planKeys.status],
        onSuccess: () => setDeleteOpen(false),
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
    if (planQuery.isLoading) {
        return (
            <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-20 rounded-lg" />
                    ))}
                </div>
                <Skeleton className="h-48 rounded-lg" />
            </div>
        );
    }

    // No plan yet — show creation UI
    if (!plan) {
        return (
            <div className="space-y-4">
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Create Payment Plan</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <p className="text-sm text-muted-foreground">
                            Describe the payment arrangement in plain English, or create one manually.
                        </p>

                        {canEdit && (
                            <>
                                <AIPlanGenerator
                                    clientId={clientId}
                                    clientName={clientName}
                                    onPlanParsed={handleAIParsed}
                                />
                                <div className="flex items-center gap-3">
                                    <div className="flex-1 border-t" />
                                    <span className="text-xs text-muted-foreground">or</span>
                                    <div className="flex-1 border-t" />
                                </div>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setCreateOpen(true)}
                                >
                                    Create Manually
                                </Button>
                            </>
                        )}
                    </CardContent>
                </Card>

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
            </div>
        );
    }

    // Plan exists — show status + schedule + actions
    const statusLabel = STATUS_LABELS[status?.status || plan.status] || plan.status;
    const statusVariant = STATUS_COLORS[status?.status || plan.status] || "outline";

    return (
        <div className="space-y-4">
            {/* Status Cards */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Total</p>
                        <p className="text-xl font-bold mt-1">
                            ${plan.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </p>
                    </CardContent>
                </Card>
                <Card className={status && status.total_paid > 0 ? "border-emerald-500/30 bg-emerald-500/5" : ""}>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Paid</p>
                        <p className="text-xl font-bold mt-1 text-emerald-500">
                            ${(status?.total_paid ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </p>
                        {status && status.percent_complete > 0 && (
                            <p className="text-[10px] text-muted-foreground mt-0.5">{status.percent_complete}%</p>
                        )}
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Remaining</p>
                        <p className="text-xl font-bold mt-1">
                            ${(status?.remaining ?? plan.total_amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </p>
                    </CardContent>
                </Card>
                <Card className={status && status.overdue_count > 0 ? "border-red-500/30 bg-red-500/5" : ""}>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Overdue</p>
                        <p className={`text-xl font-bold mt-1 ${status && status.overdue_count > 0 ? "text-destructive" : ""}`}>
                            ${(status?.overdue_amount ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </p>
                        {status && status.overdue_count > 0 && (
                            <p className="text-[10px] text-destructive mt-0.5">{status.overdue_count} payment(s)</p>
                        )}
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Status</p>
                        <div className="mt-2">
                            <Badge variant={statusVariant} className="text-xs">
                                {statusLabel}
                            </Badge>
                        </div>
                        {status?.next_due_date && (
                            <p className="text-[10px] text-muted-foreground mt-1">
                                Next: {status.next_due_date}
                            </p>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Progress Bar */}
            {status && status.percent_complete > 0 && (
                <div className="w-full bg-accent rounded-full h-2">
                    <div
                        className="bg-emerald-500 h-2 rounded-full transition-all duration-500"
                        style={{ width: `${Math.min(status.percent_complete, 100)}%` }}
                    />
                </div>
            )}

            {/* Plan Details */}
            <Card>
                <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-sm font-medium">Payment Schedule</CardTitle>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span className="capitalize">{plan.frequency}</span>
                            <span>&#183;</span>
                            <span>${plan.recurring_amount.toLocaleString()}/payment</span>
                            {plan.client_name && (
                                <>
                                    <span>&#183;</span>
                                    <span>{plan.client_name}</span>
                                </>
                            )}
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    <PaymentSchedule schedule={plan.scheduled_payments} />
                </CardContent>
            </Card>

            {/* Actions */}
            {canEdit && (
                <div className="flex flex-wrap items-center gap-2">
                    {plan.status === "active" && (
                        <>
                            <Button size="sm" onClick={() => setRecordOpen(true)}>
                                Record Payment
                            </Button>
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
                    {plan.status !== "cancelled" && plan.status !== "completed" && (
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
                        onClick={() => setDeleteOpen(true)}
                    >
                        Delete Plan
                    </Button>
                </div>
            )}

            {/* Payment History */}
            {plan.payments.length > 0 && (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">
                            Payment History ({plan.payments.length})
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
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
                                            {p.payer_name && ` - ${p.payer_name}`}
                                            {p.note && ` - ${p.note}`}
                                        </p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Dialogs */}
            <RecordPaymentDialog
                open={recordOpen}
                onOpenChange={setRecordOpen}
                onSubmit={(data) => recordPayment.mutate(data)}
                isLoading={recordPayment.isPending}
            />
            <ConfirmDialog
                open={deleteOpen}
                onOpenChange={setDeleteOpen}
                title="Delete Payment Plan"
                description="This will permanently delete the payment plan and all recorded payment history. This cannot be undone."
                onConfirm={() => deletePlan.mutate()}
                isLoading={deletePlan.isPending}
            />
        </div>
    );
}
