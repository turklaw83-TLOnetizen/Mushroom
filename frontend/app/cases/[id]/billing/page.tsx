// ---- Enhanced Billing Tab ------------------------------------------------
// Time entries, expenses, invoices, retainer tracking, trust ledger, aging.
"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { DetailPanel, type DetailField } from "@/components/shared/detail-panel";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// ---- Interfaces ---------------------------------------------------------

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

interface Invoice {
    id: string;
    case_id: string;
    case_name: string;
    client_name: string;
    date_created: string;
    due_date: string;
    status: string;
    total_hours: number;
    subtotal_fees: number;
    subtotal_expenses: number;
    total: number;
    amount_paid: number;
    notes: string;
    time_entry_ids?: string[];
    expense_ids?: string[];
}

interface RetainerEntry {
    id: string;
    type: string;
    amount: number;
    date: string;
    note: string;
    invoice_id?: string;
}

interface RetainerData {
    balance: number;
    history: RetainerEntry[];
}

interface TrustEntry {
    id: string;
    date: string;
    amount: number;
    type: string;
    description: string;
}

interface AgingBucket {
    id: string;
    case_name: string;
    client_name: string;
    total: number;
    balance: number;
    days_outstanding: number;
    status: string;
}

interface AgingReport {
    current: AgingBucket[];
    "30_days": AgingBucket[];
    "60_days": AgingBucket[];
    "90_plus": AgingBucket[];
}

// ---- Schemas & Fields ---------------------------------------------------

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

// ---- Status helpers -----------------------------------------------------

function invoiceStatusColor(status: string): string {
    switch (status) {
        case "paid": return "text-emerald-400 border-emerald-500/30";
        case "sent": return "text-blue-400 border-blue-500/30";
        case "draft": return "text-muted-foreground border-border";
        case "overdue": return "text-red-400 border-red-500/30";
        case "void": return "text-muted-foreground/50 border-border line-through";
        default: return "text-muted-foreground border-border";
    }
}

function agingBucketColor(bucket: string): string {
    switch (bucket) {
        case "current": return "text-emerald-400";
        case "30_days": return "text-amber-400";
        case "60_days": return "text-orange-400";
        case "90_plus": return "text-red-400";
        default: return "text-muted-foreground";
    }
}

function agingBucketLabel(bucket: string): string {
    switch (bucket) {
        case "current": return "Current (0-30 days)";
        case "30_days": return "31-60 Days";
        case "60_days": return "61-90 Days";
        case "90_plus": return "90+ Days";
        default: return bucket;
    }
}

// ---- Component ----------------------------------------------------------

export default function BillingPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { canEdit, canDelete } = useRole();

    // Dialog state
    const [timeDialogOpen, setTimeDialogOpen] = useState(false);
    const [expenseDialogOpen, setExpenseDialogOpen] = useState(false);
    const [detailTime, setDetailTime] = useState<TimeEntry | null>(null);
    const [detailExpense, setDetailExpense] = useState<Expense | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<{ type: "time" | "expense"; item: TimeEntry | Expense } | null>(null);

    // Retainer form state
    const [retainerAmount, setRetainerAmount] = useState("");
    const [retainerNote, setRetainerNote] = useState("");
    const [drawAmount, setDrawAmount] = useState("");
    const [drawNote, setDrawNote] = useState("");

    // ---- Query keys -------------------------------------------------------
    const billingKeys = {
        time: ["billing", "time", caseId],
        expenses: ["billing", "expenses", caseId],
        summary: ["billing", "summary", caseId],
        invoices: ["billing", "invoices", caseId],
        retainer: ["billing", "retainer", caseId],
        trust: ["compliance", "trust", caseId],
        aging: ["billing", "aging"],
    };

    // ---- Queries ----------------------------------------------------------

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

    const invoicesQuery = useQuery({
        queryKey: billingKeys.invoices,
        queryFn: () => api.get<Invoice[]>(`/billing/invoices/${caseId}`, { getToken }),
    });

    const retainerQuery = useQuery({
        queryKey: billingKeys.retainer,
        queryFn: () => api.get<RetainerData>(`/billing/retainer/${caseId}`, { getToken }),
    });

    const trustQuery = useQuery({
        queryKey: billingKeys.trust,
        queryFn: () => api.get<TrustEntry[]>(`/compliance/trust/${caseId}`, { getToken }),
    });

    const agingQuery = useQuery({
        queryKey: billingKeys.aging,
        queryFn: () => api.get<AgingReport>(`/billing/aging`, { getToken }),
    });

    const timeEntries = timeQuery.data ?? [];
    const expenses = expenseQuery.data ?? [];
    const summary = summaryQuery.data;
    const invoices = invoicesQuery.data ?? [];
    const retainer = retainerQuery.data ?? { balance: 0, history: [] };
    const trust = trustQuery.data ?? [];
    const aging = agingQuery.data;

    // ---- Derived: trust balance -------------------------------------------
    const trustBalance = trust.reduce((sum, e) => {
        return sum + (e.type === "deposit" ? e.amount : -e.amount);
    }, 0);

    // ---- Derived: retainer progress ---------------------------------------
    const retainerDeposits = retainer.history
        .filter((e) => e.type === "deposit")
        .reduce((sum, e) => sum + e.amount, 0);
    const retainerProgress = retainerDeposits > 0
        ? Math.max(0, Math.min(100, (retainer.balance / retainerDeposits) * 100))
        : 0;

    // ---- Derived: aging totals -------------------------------------------
    const agingTotals = useMemo(() => {
        if (!aging) return { current: 0, thirty: 0, sixty: 0, ninety: 0, total: 0 };
        const current = aging.current.reduce((s, i) => s + i.balance, 0);
        const thirty = aging["30_days"].reduce((s, i) => s + i.balance, 0);
        const sixty = aging["60_days"].reduce((s, i) => s + i.balance, 0);
        const ninety = aging["90_plus"].reduce((s, i) => s + i.balance, 0);
        return { current, thirty, sixty, ninety, total: current + thirty + sixty + ninety };
    }, [aging]);

    // ---- Mutations: time & expense ----------------------------------------

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

    // ---- Mutations: invoices ----------------------------------------------

    const createInvoice = useMutationWithToast<void>({
        mutationFn: async () => {
            // Auto-select all unbilled time entries and expenses
            const unbilledTime = timeEntries.filter((t) => t.billable).map((t) => t.id);
            const unbilledExpenses = expenses.map((e) => e.id);
            if (unbilledTime.length === 0 && unbilledExpenses.length === 0) {
                throw new Error("No unbilled time entries or expenses");
            }
            await api.post(`/billing/invoices/${caseId}`, {
                time_entry_ids: unbilledTime,
                expense_ids: unbilledExpenses,
            }, { getToken });
        },
        successMessage: "Invoice created",
        invalidateKeys: [billingKeys.invoices, billingKeys.time, billingKeys.expenses, billingKeys.summary],
    });

    const updateInvoiceStatus = useMutationWithToast<{ invoiceId: string; status: string }>({
        mutationFn: ({ invoiceId, status }) =>
            api.patch(`/billing/invoices/${invoiceId}/status`, { status }, { getToken }),
        successMessage: "Invoice status updated",
        invalidateKeys: [billingKeys.invoices, billingKeys.summary, billingKeys.aging],
    });

    // ---- Mutations: retainer ----------------------------------------------

    const addDeposit = useMutationWithToast<void>({
        mutationFn: async () => {
            const amt = parseFloat(retainerAmount);
            if (isNaN(amt) || amt <= 0) throw new Error("Enter a valid amount");
            await api.post(`/billing/retainer/${caseId}/deposit`, {
                amount: amt,
                note: retainerNote,
            }, { getToken });
        },
        successMessage: "Retainer deposit recorded",
        invalidateKeys: [billingKeys.retainer],
        onSuccess: () => { setRetainerAmount(""); setRetainerNote(""); },
    });

    const addDraw = useMutationWithToast<void>({
        mutationFn: async () => {
            const amt = parseFloat(drawAmount);
            if (isNaN(amt) || amt <= 0) throw new Error("Enter a valid amount");
            await api.post(`/billing/retainer/${caseId}/draw`, {
                amount: amt,
                note: drawNote,
            }, { getToken });
        },
        successMessage: "Retainer draw recorded",
        invalidateKeys: [billingKeys.retainer],
        onSuccess: () => { setDrawAmount(""); setDrawNote(""); },
    });

    // ---- Render -----------------------------------------------------------
    return (
        <div className="space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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
                            {summary ? `$${(summary.total_billable || summary.billable_amount || 0).toLocaleString()}` : <Skeleton className="h-8 w-20 inline-block" />}
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Retainer Balance</p>
                        <p className={`text-2xl font-bold mt-1 ${retainer.balance < 0 ? "text-red-400" : ""}`}>
                            {retainerQuery.isLoading
                                ? <Skeleton className="h-8 w-20 inline-block" />
                                : `$${retainer.balance.toLocaleString()}`
                            }
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Invoices</p>
                        <p className="text-2xl font-bold mt-1">
                            {invoicesQuery.isLoading
                                ? <Skeleton className="h-8 w-8 inline-block" />
                                : invoices.length
                            }
                        </p>
                    </CardContent>
                </Card>
            </div>

            {/* Main Tabs */}
            <Tabs defaultValue="time">
                <TabsList className="flex-wrap">
                    <TabsTrigger value="time">Time ({timeEntries.length})</TabsTrigger>
                    <TabsTrigger value="expenses">Expenses ({expenses.length})</TabsTrigger>
                    <TabsTrigger value="invoices">Invoices ({invoices.length})</TabsTrigger>
                    <TabsTrigger value="retainer">Retainer</TabsTrigger>
                    <TabsTrigger value="trust">Trust Ledger</TabsTrigger>
                    <TabsTrigger value="aging">Aging Report</TabsTrigger>
                </TabsList>

                {/* ---- Time Entries Tab ---- */}
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
                                                &#x2715;
                                            </Button>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>
                        ))
                    )}
                </TabsContent>

                {/* ---- Expenses Tab ---- */}
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
                                            {exp.date}{exp.category && ` \u00b7 ${exp.category}`}
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
                                                &#x2715;
                                            </Button>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>
                        ))
                    )}
                </TabsContent>

                {/* ---- Invoices Tab ---- */}
                <TabsContent value="invoices" className="space-y-4 mt-4">
                    {canEdit && (
                        <div className="flex justify-end">
                            <Button
                                size="sm"
                                className="gap-1.5"
                                onClick={() => createInvoice.mutate()}
                                disabled={createInvoice.isPending}
                            >
                                {createInvoice.isPending ? "Creating..." : "+ Create Invoice"}
                            </Button>
                        </div>
                    )}

                    {invoicesQuery.isLoading ? (
                        <div className="space-y-2">
                            {Array.from({ length: 3 }).map((_, i) => (
                                <Skeleton key={i} className="h-16 w-full" />
                            ))}
                        </div>
                    ) : invoices.length === 0 ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No invoices yet. Create one from unbilled time entries and expenses.
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="rounded-lg border">
                            {/* Table header */}
                            <div className="grid grid-cols-6 gap-2 px-4 py-2 border-b bg-muted/30 text-xs font-medium text-muted-foreground uppercase">
                                <span>Invoice #</span>
                                <span>Date</span>
                                <span>Due Date</span>
                                <span>Status</span>
                                <span className="text-right">Total</span>
                                <span className="text-right">Actions</span>
                            </div>
                            {invoices.map((inv) => (
                                <div key={inv.id} className="grid grid-cols-6 gap-2 px-4 py-3 border-b last:border-0 items-center">
                                    <span className="text-sm font-mono font-medium">{inv.id}</span>
                                    <span className="text-sm text-muted-foreground">{inv.date_created}</span>
                                    <span className="text-sm text-muted-foreground">{inv.due_date}</span>
                                    <span>
                                        <Badge variant="outline" className={`text-xs ${invoiceStatusColor(inv.status)}`}>
                                            {inv.status.toUpperCase()}
                                        </Badge>
                                    </span>
                                    <span className="text-sm font-bold text-right">${inv.total.toLocaleString()}</span>
                                    <div className="flex justify-end gap-1">
                                        {canEdit && inv.status === "draft" && (
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="text-xs h-7"
                                                onClick={() => updateInvoiceStatus.mutate({ invoiceId: inv.id, status: "sent" })}
                                            >
                                                Send
                                            </Button>
                                        )}
                                        {canEdit && (inv.status === "sent" || inv.status === "overdue") && (
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="text-xs h-7 text-emerald-400"
                                                onClick={() => updateInvoiceStatus.mutate({ invoiceId: inv.id, status: "paid" })}
                                            >
                                                Mark Paid
                                            </Button>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </TabsContent>

                {/* ---- Retainer Tab ---- */}
                <TabsContent value="retainer" className="space-y-4 mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center justify-between">
                                Retainer Account
                                <Badge
                                    variant="outline"
                                    className={`text-lg ${retainer.balance >= 0 ? "text-emerald-400 border-emerald-500/30" : "text-red-400 border-red-500/30"}`}
                                >
                                    ${retainer.balance.toLocaleString()}
                                </Badge>
                            </CardTitle>
                            <CardDescription>
                                Track retainer deposits and drawdowns for billable work
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {/* Retainer progress bar */}
                            <div>
                                <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                                    <span>Remaining Balance</span>
                                    <span>{retainerProgress.toFixed(0)}%</span>
                                </div>
                                <div className="h-3 w-full rounded-full bg-muted">
                                    <div
                                        className={`h-3 rounded-full transition-all duration-300 ${
                                            retainerProgress > 50 ? "bg-emerald-500" :
                                            retainerProgress > 25 ? "bg-amber-500" : "bg-red-500"
                                        }`}
                                        style={{ width: `${retainerProgress}%` }}
                                    />
                                </div>
                            </div>

                            {/* Deposit / Draw forms */}
                            {canEdit && (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="rounded-lg border p-3 space-y-2">
                                        <p className="text-xs font-medium text-muted-foreground uppercase">Record Deposit</p>
                                        <div className="flex gap-2">
                                            <Input
                                                type="number"
                                                placeholder="Amount"
                                                value={retainerAmount}
                                                onChange={(e) => setRetainerAmount(e.target.value)}
                                                className="flex-1"
                                            />
                                            <Input
                                                placeholder="Note (optional)"
                                                value={retainerNote}
                                                onChange={(e) => setRetainerNote(e.target.value)}
                                                className="flex-1"
                                            />
                                        </div>
                                        <Button
                                            size="sm"
                                            onClick={() => addDeposit.mutate()}
                                            disabled={addDeposit.isPending || !retainerAmount}
                                            className="w-full"
                                        >
                                            {addDeposit.isPending ? "Recording..." : "Add Deposit"}
                                        </Button>
                                    </div>
                                    <div className="rounded-lg border p-3 space-y-2">
                                        <p className="text-xs font-medium text-muted-foreground uppercase">Record Draw</p>
                                        <div className="flex gap-2">
                                            <Input
                                                type="number"
                                                placeholder="Amount"
                                                value={drawAmount}
                                                onChange={(e) => setDrawAmount(e.target.value)}
                                                className="flex-1"
                                            />
                                            <Input
                                                placeholder="Note (optional)"
                                                value={drawNote}
                                                onChange={(e) => setDrawNote(e.target.value)}
                                                className="flex-1"
                                            />
                                        </div>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => addDraw.mutate()}
                                            disabled={addDraw.isPending || !drawAmount}
                                            className="w-full"
                                        >
                                            {addDraw.isPending ? "Recording..." : "Record Draw"}
                                        </Button>
                                    </div>
                                </div>
                            )}

                            {/* Transaction history */}
                            <div>
                                <p className="text-xs font-medium text-muted-foreground mb-2">Transaction History</p>
                                {retainer.history.length === 0 ? (
                                    <p className="text-sm text-muted-foreground text-center py-4">No retainer transactions.</p>
                                ) : (
                                    <div className="space-y-1">
                                        {[...retainer.history].reverse().map((entry, i) => (
                                            <div key={entry.id || i} className="flex items-center justify-between py-2 border-b last:border-0">
                                                <div>
                                                    <p className="text-sm">
                                                        {entry.type === "deposit" ? "Deposit" : "Draw"}
                                                        {entry.note && ` \u2014 ${entry.note}`}
                                                    </p>
                                                    <p className="text-xs text-muted-foreground">{entry.date}</p>
                                                </div>
                                                <span className={`text-sm font-bold ${entry.type === "deposit" ? "text-emerald-400" : "text-red-400"}`}>
                                                    {entry.type === "deposit" ? "+" : "\u2212"}${entry.amount.toFixed(2)}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ---- Trust Ledger Tab ---- */}
                <TabsContent value="trust" className="space-y-4 mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center justify-between">
                                Trust Account Ledger
                                <div className="flex items-center gap-2">
                                    <Badge variant="secondary">{trust.length} entries</Badge>
                                    <Badge
                                        variant="outline"
                                        className={trustBalance >= 0
                                            ? "text-emerald-400 border-emerald-500/30"
                                            : "text-red-400 border-red-500/30"
                                        }
                                    >
                                        Balance: ${trustBalance.toLocaleString()}
                                    </Badge>
                                </div>
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {trust.length === 0 ? (
                                <p className="text-sm text-muted-foreground text-center py-6">
                                    No trust account entries.
                                </p>
                            ) : (
                                <div className="space-y-2">
                                    {trust.map((entry, i) => (
                                        <div
                                            key={entry.id || i}
                                            className="flex items-center justify-between py-2 border-b border-border last:border-0"
                                        >
                                            <div>
                                                <p className="text-sm">{entry.description}</p>
                                                <p className="text-xs text-muted-foreground">{entry.date}</p>
                                            </div>
                                            <span className={`text-sm font-bold ${entry.type === "deposit" ? "text-emerald-400" : "text-red-400"}`}>
                                                {entry.type === "deposit" ? "+" : "\u2212"}${Math.abs(entry.amount).toFixed(2)}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ---- Aging Report Tab ---- */}
                <TabsContent value="aging" className="space-y-4 mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Payment Aging Report</CardTitle>
                            <CardDescription>
                                Unpaid invoices grouped by age across all cases
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {agingQuery.isLoading ? (
                                <div className="space-y-2">
                                    {Array.from({ length: 4 }).map((_, i) => (
                                        <Skeleton key={i} className="h-12 w-full" />
                                    ))}
                                </div>
                            ) : (
                                <>
                                    {/* Aging summary bars */}
                                    <div className="grid grid-cols-4 gap-3">
                                        {[
                                            { key: "current", label: "Current", amount: agingTotals.current, count: aging?.current.length ?? 0 },
                                            { key: "30_days", label: "30 Days", amount: agingTotals.thirty, count: aging?.["30_days"].length ?? 0 },
                                            { key: "60_days", label: "60 Days", amount: agingTotals.sixty, count: aging?.["60_days"].length ?? 0 },
                                            { key: "90_plus", label: "90+ Days", amount: agingTotals.ninety, count: aging?.["90_plus"].length ?? 0 },
                                        ].map((bucket) => (
                                            <div key={bucket.key} className="rounded-lg border p-3 text-center">
                                                <p className="text-xs text-muted-foreground uppercase">{bucket.label}</p>
                                                <p className={`text-lg font-bold mt-1 ${agingBucketColor(bucket.key)}`}>
                                                    ${bucket.amount.toLocaleString()}
                                                </p>
                                                <p className="text-xs text-muted-foreground">{bucket.count} invoice(s)</p>
                                            </div>
                                        ))}
                                    </div>

                                    {/* Detailed breakdown */}
                                    {aging && (["current", "30_days", "60_days", "90_plus"] as const).map((bucketKey) => {
                                        const items = aging[bucketKey];
                                        if (items.length === 0) return null;
                                        return (
                                            <div key={bucketKey}>
                                                <p className={`text-sm font-medium mb-2 ${agingBucketColor(bucketKey)}`}>
                                                    {agingBucketLabel(bucketKey)} ({items.length})
                                                </p>
                                                <div className="rounded-lg border">
                                                    {items.map((inv) => (
                                                        <div key={inv.id} className="flex items-center justify-between px-4 py-2 border-b last:border-0">
                                                            <div>
                                                                <p className="text-sm font-medium">{inv.id}</p>
                                                                <p className="text-xs text-muted-foreground">
                                                                    {inv.client_name || inv.case_name || "N/A"} &middot; {inv.days_outstanding} days
                                                                </p>
                                                            </div>
                                                            <div className="text-right">
                                                                <p className="text-sm font-bold">${inv.balance.toLocaleString()}</p>
                                                                <Badge variant="outline" className={`text-[10px] ${invoiceStatusColor(inv.status)}`}>
                                                                    {inv.status}
                                                                </Badge>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        );
                                    })}

                                    {agingTotals.total === 0 && (
                                        <p className="text-sm text-muted-foreground text-center py-6">
                                            No outstanding invoices. All accounts are current.
                                        </p>
                                    )}
                                </>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            {/* ---- Dialogs ---- */}
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
                    description={`${detailTime.date} \u00b7 ${detailTime.hours}h`}
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
                    description={`${detailExpense.date} \u00b7 $${detailExpense.amount.toFixed(2)}`}
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
