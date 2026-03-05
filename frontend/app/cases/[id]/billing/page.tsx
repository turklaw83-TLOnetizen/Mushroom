// ---- Billing Tab (with detail panels) -----------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { DetailPanel, type DetailField } from "@/components/shared/detail-panel";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PaymentPlanTab } from "@/components/billing/payment-plan-tab";

interface TimeEntry {
    id: string;
    date: string;
    hours: number;
    description: string;
    attorney: string;
    rate: number;
    billable: boolean;
}

interface Expense {
    id: string;
    date: string;
    amount: number;
    description: string;
    category: string;
}

// Time entry schema
const timeSchema = z.object({
    date: z.string().min(1, "Date is required"),
    hours: z.number().min(0.1, "Min 0.1h").max(24),
    description: z.string().min(1, "Description required").max(2000),
    rate: z.number().min(0).optional().default(0),
});
type TimeInput = z.infer<typeof timeSchema>;

const timeFields: FieldConfig<TimeInput>[] = [
    { name: "date", label: "Date", required: true, placeholder: "2024-01-15" },
    { name: "hours", label: "Hours", type: "number", required: true, placeholder: "1.5" },
    { name: "description", label: "Description", type: "textarea", required: true },
    { name: "rate", label: "Rate ($/hr)", type: "number", placeholder: "350" },
];

const timeDetailFields: DetailField<TimeInput>[] = [
    { name: "date", label: "Date" },
    { name: "hours", label: "Hours", type: "number" },
    { name: "description", label: "Description", type: "textarea" },
    { name: "rate", label: "Rate ($/hr)", type: "number" },
];

// Expense schema
const expenseSchema = z.object({
    date: z.string().min(1, "Date is required"),
    amount: z.number().min(0.01, "Amount required"),
    description: z.string().min(1, "Description required").max(2000),
    category: z.string().max(100).optional().default(""),
});
type ExpenseInput = z.infer<typeof expenseSchema>;

const expenseFields: FieldConfig<ExpenseInput>[] = [
    { name: "date", label: "Date", required: true, placeholder: "2024-01-15" },
    { name: "amount", label: "Amount ($)", type: "number", required: true, placeholder: "250.00" },
    { name: "description", label: "Description", type: "textarea", required: true },
    {
        name: "category", label: "Category", type: "select", options: [
            { value: "", label: "None" },
            { value: "filing", label: "Filing Fees" },
            { value: "travel", label: "Travel" },
            { value: "expert", label: "Expert Witness" },
            { value: "deposition", label: "Deposition" },
            { value: "copies", label: "Copies/Printing" },
            { value: "other", label: "Other" },
        ],
    },
];

const expenseDetailFields: DetailField<ExpenseInput>[] = [
    { name: "date", label: "Date" },
    { name: "amount", label: "Amount ($)", type: "number" },
    { name: "description", label: "Description", type: "textarea" },
    {
        name: "category", label: "Category", type: "select", options: [
            { value: "", label: "None" },
            { value: "filing", label: "Filing Fees" },
            { value: "travel", label: "Travel" },
            { value: "expert", label: "Expert Witness" },
            { value: "deposition", label: "Deposition" },
            { value: "copies", label: "Copies/Printing" },
            { value: "other", label: "Other" },
        ],
    },
];

export default function BillingPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { canEdit, canDelete } = useRole();
    const [timeDialogOpen, setTimeDialogOpen] = useState(false);
    const [expenseDialogOpen, setExpenseDialogOpen] = useState(false);
    const [detailTime, setDetailTime] = useState<TimeEntry | null>(null);
    const [detailExpense, setDetailExpense] = useState<Expense | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<{ type: "time" | "expense"; item: TimeEntry | Expense } | null>(null);

    const billingKeys = {
        time: ["billing", "time", caseId],
        expenses: ["billing", "expenses", caseId],
        summary: ["billing", "summary", caseId],
    };

    const timeQuery = useQuery({
        queryKey: billingKeys.time,
        queryFn: () => api.get<TimeEntry[]>(`/billing/time/${caseId}`, { getToken }),
    });

    const expenseQuery = useQuery({
        queryKey: billingKeys.expenses,
        queryFn: () => api.get<Expense[]>(`/billing/expenses/${caseId}`, { getToken }),
    });

    const summaryQuery = useQuery({
        queryKey: billingKeys.summary,
        queryFn: () => api.get<Record<string, number>>(`/billing/summary/${caseId}`, { getToken }),
    });

    const timeEntries = timeQuery.data ?? [];
    const expenses = expenseQuery.data ?? [];
    const summary = summaryQuery.data;

    // Mutations using the centralized wrapper
    const createTime = useMutationWithToast<TimeInput>({
        mutationFn: (data) => api.post(`/billing/time/${caseId}`, data, { getToken }),
        successMessage: "Time entry added",
        invalidateKeys: [billingKeys.time, billingKeys.summary],
        onSuccess: () => setTimeDialogOpen(false),
    });

    const createExpense = useMutationWithToast<ExpenseInput>({
        mutationFn: (data) => api.post(`/billing/expenses/${caseId}`, data, { getToken }),
        successMessage: "Expense added",
        invalidateKeys: [billingKeys.expenses, billingKeys.summary],
        onSuccess: () => setExpenseDialogOpen(false),
    });

    const updateTime = useMutationWithToast<TimeInput>({
        mutationFn: (data) => {
            if (!detailTime) throw new Error("No entry");
            return api.put(`/billing/time/${caseId}/${detailTime.id}`, data, { getToken });
        },
        successMessage: "Time entry updated",
        invalidateKeys: [billingKeys.time, billingKeys.summary],
        onSuccess: () => setDetailTime(null),
    });

    const updateExpense = useMutationWithToast<ExpenseInput>({
        mutationFn: (data) => {
            if (!detailExpense) throw new Error("No expense");
            return api.put(`/billing/expenses/${caseId}/${detailExpense.id}`, data, { getToken });
        },
        successMessage: "Expense updated",
        invalidateKeys: [billingKeys.expenses, billingKeys.summary],
        onSuccess: () => setDetailExpense(null),
    });

    const handleDelete = useMutationWithToast<void>({
        mutationFn: async () => {
            if (!deleteTarget) throw new Error("Nothing to delete");
            const { type, item } = deleteTarget;
            await api.delete(`/billing/${type === "time" ? "time" : "expenses"}/${caseId}/${item.id}`, { getToken });
        },
        successMessage: "Deleted",
        invalidateKeys: [billingKeys.time, billingKeys.expenses, billingKeys.summary],
        onSuccess: () => setDeleteTarget(null),
    });

    return (
        <div className="space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Total Hours</p>
                        <p className="text-2xl font-bold mt-1">
                            {summary ? summary.total_hours?.toFixed(1) : <Skeleton className="h-8 w-16 inline-block" />}
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Billable Amount</p>
                        <p className="text-2xl font-bold mt-1">
                            {summary ? `$${(summary.total_billable || 0).toLocaleString()}` : <Skeleton className="h-8 w-20 inline-block" />}
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Expenses</p>
                        <p className="text-2xl font-bold mt-1">
                            {summary ? `$${(summary.total_expenses || 0).toLocaleString()}` : <Skeleton className="h-8 w-20 inline-block" />}
                        </p>
                    </CardContent>
                </Card>
            </div>

            <Tabs defaultValue="time">
                <TabsList>
                    <TabsTrigger value="time">Time Entries ({timeEntries.length})</TabsTrigger>
                    <TabsTrigger value="expenses">Expenses ({expenses.length})</TabsTrigger>
                    <TabsTrigger value="payment-plan">Payment Plan</TabsTrigger>
                </TabsList>

                <TabsContent value="time" className="space-y-2 mt-4">
                    {canEdit && (
                        <div className="flex justify-end">
                            <Button size="sm" className="gap-1.5" onClick={() => setTimeDialogOpen(true)}>
                                <span>+</span> Add Time
                            </Button>
                        </div>
                    )}
                    {timeEntries.length === 0 ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No time entries yet.
                            </CardContent>
                        </Card>
                    ) : (
                        timeEntries.map((entry, i) => (
                            <Card
                                key={entry.id || i}
                                className="hover:bg-accent/30 transition-colors cursor-pointer group"
                                onClick={() => setDetailTime(entry)}
                            >
                                <CardContent className="flex items-center justify-between py-3">
                                    <div>
                                        <p className="text-sm font-medium">{entry.description}</p>
                                        <p className="text-xs text-muted-foreground">{entry.date} · {entry.attorney}</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <div className="text-right">
                                            <p className="text-sm font-bold">{entry.hours}h</p>
                                            {entry.rate > 0 && (
                                                <p className="text-xs text-muted-foreground">${(entry.hours * entry.rate).toFixed(2)}</p>
                                            )}
                                        </div>
                                        {canDelete && (
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive"
                                                aria-label={`Delete ${entry.description}`}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    setDeleteTarget({ type: "time", item: entry });
                                                }}
                                            >
                                                ✕
                                            </Button>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>
                        ))
                    )}
                </TabsContent>

                <TabsContent value="expenses" className="space-y-2 mt-4">
                    {canEdit && (
                        <div className="flex justify-end">
                            <Button size="sm" className="gap-1.5" onClick={() => setExpenseDialogOpen(true)}>
                                <span>+</span> Add Expense
                            </Button>
                        </div>
                    )}
                    {expenses.length === 0 ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No expenses yet.
                            </CardContent>
                        </Card>
                    ) : (
                        expenses.map((exp, i) => (
                            <Card
                                key={exp.id || i}
                                className="hover:bg-accent/30 transition-colors cursor-pointer group"
                                onClick={() => setDetailExpense(exp)}
                            >
                                <CardContent className="flex items-center justify-between py-3">
                                    <div>
                                        <p className="text-sm font-medium">{exp.description}</p>
                                        <p className="text-xs text-muted-foreground">
                                            {exp.date}{exp.category && ` · ${exp.category}`}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <p className="text-sm font-bold">${exp.amount.toFixed(2)}</p>
                                        {canDelete && (
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive"
                                                aria-label={`Delete ${exp.description}`}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    setDeleteTarget({ type: "expense", item: exp });
                                                }}
                                            >
                                                ✕
                                            </Button>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>
                        ))
                    )}
                </TabsContent>

                <TabsContent value="payment-plan">
                    <PaymentPlanTab caseId={caseId} />
                </TabsContent>
            </Tabs>

            {/* Dialogs */}
            {canEdit && (
                <>
                    <FormDialog
                        open={timeDialogOpen}
                        onOpenChange={setTimeDialogOpen}
                        title="Add Time Entry"
                        schema={timeSchema}
                        defaultValues={{ date: new Date().toISOString().split("T")[0], hours: 0, description: "", rate: 0 }}
                        fields={timeFields}
                        onSubmit={(data) => createTime.mutate(data)}
                        submitLabel="Add Entry"
                        isLoading={createTime.isPending}
                    />
                    <FormDialog
                        open={expenseDialogOpen}
                        onOpenChange={setExpenseDialogOpen}
                        title="Add Expense"
                        schema={expenseSchema}
                        defaultValues={{ date: new Date().toISOString().split("T")[0], amount: 0, description: "", category: "" }}
                        fields={expenseFields}
                        onSubmit={(data) => createExpense.mutate(data)}
                        submitLabel="Add Expense"
                        isLoading={createExpense.isPending}
                    />
                </>
            )}

            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
                title={`Delete ${deleteTarget?.type === "time" ? "Time Entry" : "Expense"}`}
                description="This cannot be undone."
                onConfirm={() => handleDelete.mutate()}
                isLoading={handleDelete.isPending}
            />

            {/* Time detail panel */}
            {detailTime && (
                <DetailPanel
                    open={!!detailTime}
                    onOpenChange={(open) => !open && setDetailTime(null)}
                    title="Time Entry"
                    description={`${detailTime.date} · ${detailTime.hours}h`}
                    schema={timeSchema}
                    values={detailTime as TimeInput}
                    fields={timeDetailFields}
                    onSave={(data) => updateTime.mutate(data)}
                    readOnly={!canEdit}
                    isLoading={updateTime.isPending}
                    onDelete={canDelete ? () => {
                        setDeleteTarget({ type: "time", item: detailTime });
                        setDetailTime(null);
                    } : undefined}
                />
            )}

            {/* Expense detail panel */}
            {detailExpense && (
                <DetailPanel
                    open={!!detailExpense}
                    onOpenChange={(open) => !open && setDetailExpense(null)}
                    title="Expense"
                    description={`${detailExpense.date} · $${detailExpense.amount.toFixed(2)}`}
                    schema={expenseSchema}
                    values={detailExpense as ExpenseInput}
                    fields={expenseDetailFields}
                    onSave={(data) => updateExpense.mutate(data)}
                    readOnly={!canEdit}
                    isLoading={updateExpense.isPending}
                    onDelete={canDelete ? () => {
                        setDeleteTarget({ type: "expense", item: detailExpense });
                        setDetailExpense(null);
                    } : undefined}
                />
            )}
        </div>
    );
}
