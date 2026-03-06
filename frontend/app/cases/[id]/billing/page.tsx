// ---- Billing Workspace (6 tabs) ------------------------------------------
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
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

// ---- Types ----------------------------------------------------------------

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
    invoice_number: string;
    case_id: string;
    date: string;
    due_date: string;
    status: "draft" | "sent" | "paid" | "overdue" | "void";
    total: number;
    balance: number;
    notes: string;
    line_items: InvoiceLineItem[];
}

interface InvoiceLineItem {
    id: string;
    type: "time" | "expense";
    description: string;
    quantity: number;
    rate: number;
    amount: number;
}

interface Payment {
    id: string;
    date: string;
    amount: number;
    method: string;
    notes: string;
}

interface RetainerData {
    balance: number;
    history: RetainerTransaction[];
}

interface RetainerTransaction {
    id: string;
    date: string;
    type: "deposit" | "draw";
    amount: number;
    description: string;
}

interface AgingBucket {
    label: string;
    total: number;
    invoices: { invoice_number: string; client: string; amount: number; days: number }[];
}

interface AgingReport {
    current: AgingBucket;
    thirty: AgingBucket;
    sixty: AgingBucket;
    ninety_plus: AgingBucket;
    total_outstanding: number;
}

interface BillingSettings {
    default_rate: number;
    payment_terms_days: number;
    firm_name: string;
    address: string;
    phone: string;
    email: string;
    tax_rate: number;
}

// ---- Schemas --------------------------------------------------------------

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

const EXPENSE_CATEGORIES = [
    { value: "", label: "None" },
    { value: "filing", label: "Filing Fees" },
    { value: "travel", label: "Travel" },
    { value: "expert", label: "Expert Witness" },
    { value: "deposition", label: "Deposition" },
    { value: "copies", label: "Copies/Printing" },
    { value: "other", label: "Other" },
];

const expenseFields: FieldConfig<ExpenseInput>[] = [
    { name: "date", label: "Date", required: true, placeholder: "2024-01-15" },
    { name: "amount", label: "Amount ($)", type: "number", required: true, placeholder: "250.00" },
    { name: "description", label: "Description", type: "textarea", required: true },
    { name: "category", label: "Category", type: "select", options: EXPENSE_CATEGORIES },
];

const expenseDetailFields: DetailField<ExpenseInput>[] = [
    { name: "date", label: "Date" },
    { name: "amount", label: "Amount ($)", type: "number" },
    { name: "description", label: "Description", type: "textarea" },
    { name: "category", label: "Category", type: "select", options: EXPENSE_CATEGORIES },
];

const paymentSchema = z.object({
    date: z.string().min(1, "Date required"),
    amount: z.number().min(0.01, "Amount required"),
    method: z.string().min(1, "Method required"),
    notes: z.string().max(500).optional().default(""),
});
type PaymentInput = z.infer<typeof paymentSchema>;

const paymentFields: FieldConfig<PaymentInput>[] = [
    { name: "date", label: "Date", required: true, placeholder: "2024-01-15" },
    { name: "amount", label: "Amount ($)", type: "number", required: true, placeholder: "500.00" },
    {
        name: "method", label: "Method", type: "select", required: true, options: [
            { value: "check", label: "Check" },
            { value: "credit_card", label: "Credit Card" },
            { value: "wire", label: "Wire Transfer" },
            { value: "cash", label: "Cash" },
            { value: "ach", label: "ACH" },
            { value: "other", label: "Other" },
        ],
    },
    { name: "notes", label: "Notes", type: "textarea" },
];

const retainerSchema = z.object({
    amount: z.number().min(0.01, "Amount required"),
    description: z.string().min(1, "Description required").max(500),
});
type RetainerInput = z.infer<typeof retainerSchema>;

const retainerFields: FieldConfig<RetainerInput>[] = [
    { name: "amount", label: "Amount ($)", type: "number", required: true, placeholder: "5000.00" },
    { name: "description", label: "Description", type: "textarea", required: true },
];

const settingsSchema = z.object({
    default_rate: z.number().min(0, "Must be >= 0"),
    payment_terms_days: z.number().min(1).max(365),
    firm_name: z.string().max(200).optional().default(""),
    address: z.string().max(500).optional().default(""),
    phone: z.string().max(50).optional().default(""),
    email: z.string().max(200).optional().default(""),
    tax_rate: z.number().min(0).max(100).optional().default(0),
});
type SettingsInput = z.infer<typeof settingsSchema>;

// ---- Helpers --------------------------------------------------------------

function fmtCurrency(v: number): string {
    return `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

const INVOICE_STATUS_STYLE: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; className?: string }> = {
    draft: { variant: "secondary" },
    sent: { variant: "default", className: "bg-blue-600 text-white" },
    paid: { variant: "default", className: "bg-green-600 text-white" },
    overdue: { variant: "destructive" },
    void: { variant: "outline", className: "line-through text-muted-foreground" },
};

// ---- Main Component -------------------------------------------------------

export default function BillingPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { canEdit, canDelete, isAdmin, isAttorney } = useRole();

    // -- Tab 1 & 2 state (Time & Expenses) --
    const [timeDialogOpen, setTimeDialogOpen] = useState(false);
    const [expenseDialogOpen, setExpenseDialogOpen] = useState(false);
    const [detailTime, setDetailTime] = useState<TimeEntry | null>(null);
    const [detailExpense, setDetailExpense] = useState<Expense | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<{ type: "time" | "expense"; item: TimeEntry | Expense } | null>(null);

    // -- Tab 3 state (Invoices) --
    const [invoiceCreateOpen, setInvoiceCreateOpen] = useState(false);
    const [selectedTimeIds, setSelectedTimeIds] = useState<Set<string>>(new Set());
    const [selectedExpenseIds, setSelectedExpenseIds] = useState<Set<string>>(new Set());
    const [invoiceNotes, setInvoiceNotes] = useState("");
    const [activeInvoice, setActiveInvoice] = useState<Invoice | null>(null);
    const [paymentDialogOpen, setPaymentDialogOpen] = useState(false);
    const [statusUpdateId, setStatusUpdateId] = useState<string | null>(null);
    const [newStatus, setNewStatus] = useState<string>("");

    // -- Tab 4 state (Retainer) --
    const [depositDialogOpen, setDepositDialogOpen] = useState(false);
    const [drawDialogOpen, setDrawDialogOpen] = useState(false);

    // -- Tab 6 state (Settings) --
    const [settingsEditing, setSettingsEditing] = useState(false);

    // ---- Query Keys -----------------------------------------------------------

    const billingKeys = {
        time: ["billing", "time", caseId],
        expenses: ["billing", "expenses", caseId],
        summary: ["billing", "summary", caseId],
        invoices: ["billing", "invoices"],
        unbilled: ["billing", "unbilled", caseId],
        retainer: ["billing", "retainer", caseId],
        aging: ["billing", "aging"],
        settings: ["billing", "settings"],
    };

    // ---- Queries --------------------------------------------------------------

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

    const invoiceQuery = useQuery({
        queryKey: billingKeys.invoices,
        queryFn: () => api.get<Invoice[]>(`/billing/invoices`, { getToken }),
    });

    const unbilledQuery = useQuery({
        queryKey: billingKeys.unbilled,
        queryFn: () => api.get<{ time_entries: TimeEntry[]; expenses: Expense[] }>(`/billing/unbilled/${caseId}`, { getToken }),
        enabled: invoiceCreateOpen,
    });

    const retainerQuery = useQuery({
        queryKey: billingKeys.retainer,
        queryFn: () => api.get<RetainerData>(`/billing/retainer/${caseId}`, { getToken }),
    });

    const agingQuery = useQuery({
        queryKey: billingKeys.aging,
        queryFn: () => api.get<AgingReport>(`/billing/aging`, { getToken }),
        enabled: isAdmin || isAttorney,
    });

    const settingsQuery = useQuery({
        queryKey: billingKeys.settings,
        queryFn: () => api.get<BillingSettings>(`/billing/settings`, { getToken }),
        enabled: isAdmin,
    });

    const invoicePaymentsQuery = useQuery({
        queryKey: ["billing", "invoices", activeInvoice?.id, "payments"],
        queryFn: () => api.get<Payment[]>(`/billing/invoices/${activeInvoice!.id}/payments`, { getToken }),
        enabled: !!activeInvoice,
    });

    // ---- Derived data ---------------------------------------------------------

    const timeEntries = timeQuery.data ?? [];
    const expenses = expenseQuery.data ?? [];
    const summary = summaryQuery.data;
    const allInvoices = invoiceQuery.data ?? [];
    const caseInvoices = allInvoices.filter((inv) => inv.case_id === caseId);
    const unbilledTime = unbilledQuery.data?.time_entries ?? [];
    const unbilledExpenses = unbilledQuery.data?.expenses ?? [];
    const retainer = retainerQuery.data;
    const aging = agingQuery.data;
    const settings = settingsQuery.data;
    const invoicePayments = invoicePaymentsQuery.data ?? [];

    const invoiceTotals = {
        invoiced: caseInvoices.reduce((s, i) => s + i.total, 0),
        paid: caseInvoices.filter((i) => i.status === "paid").reduce((s, i) => s + i.total, 0),
        outstanding: caseInvoices.filter((i) => i.status !== "paid" && i.status !== "void").reduce((s, i) => s + i.balance, 0),
    };

    // ---- Mutations (Tab 1 & 2) ------------------------------------------------

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

    // ---- Mutations (Tab 3: Invoices) ------------------------------------------

    const createInvoice = useMutationWithToast<{ time_entry_ids: string[]; expense_ids: string[]; notes: string }>({
        mutationFn: (data) => api.post(`/billing/invoices/${caseId}`, data, { getToken }),
        successMessage: "Invoice created",
        invalidateKeys: [billingKeys.invoices, billingKeys.unbilled, billingKeys.summary],
        onSuccess: () => {
            setInvoiceCreateOpen(false);
            setSelectedTimeIds(new Set());
            setSelectedExpenseIds(new Set());
            setInvoiceNotes("");
        },
    });

    const updateInvoiceStatus = useMutationWithToast<{ id: string; status: string }>({
        mutationFn: ({ id, status }) => api.put(`/billing/invoices/${id}/status`, { status }, { getToken }),
        successMessage: "Invoice status updated",
        invalidateKeys: [billingKeys.invoices, billingKeys.summary],
        onSuccess: () => {
            setStatusUpdateId(null);
            setNewStatus("");
        },
    });

    const recordPayment = useMutationWithToast<PaymentInput>({
        mutationFn: (data) => {
            if (!activeInvoice) throw new Error("No invoice selected");
            return api.post(`/billing/invoices/${activeInvoice.id}/payments`, data, { getToken });
        },
        successMessage: "Payment recorded",
        invalidateKeys: [
            billingKeys.invoices,
            billingKeys.summary,
            ["billing", "invoices", activeInvoice?.id, "payments"],
        ],
        onSuccess: () => setPaymentDialogOpen(false),
    });

    const downloadInvoicePdf = useMutationWithToast<string>({
        mutationFn: async (invoiceId) => {
            const token = await getToken();
            const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const res = await fetch(`${API_BASE}/api/v1/billing/invoices/${invoiceId}/pdf`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
            if (!res.ok) throw new Error("Failed to download PDF");
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `invoice-${invoiceId}.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            return {};
        },
        successMessage: "PDF downloaded",
    });

    // ---- Mutations (Tab 4: Retainer) ------------------------------------------

    const addDeposit = useMutationWithToast<RetainerInput>({
        mutationFn: (data) => api.post(`/billing/retainer/${caseId}/deposit`, data, { getToken }),
        successMessage: "Deposit recorded",
        invalidateKeys: [billingKeys.retainer, billingKeys.summary],
        onSuccess: () => setDepositDialogOpen(false),
    });

    const recordDraw = useMutationWithToast<RetainerInput>({
        mutationFn: (data) => api.post(`/billing/retainer/${caseId}/draw`, data, { getToken }),
        successMessage: "Draw recorded",
        invalidateKeys: [billingKeys.retainer, billingKeys.summary],
        onSuccess: () => setDrawDialogOpen(false),
    });

    // ---- Mutations (Tab 6: Settings) ------------------------------------------

    const saveSettings = useMutationWithToast<SettingsInput>({
        mutationFn: (data) => api.put(`/billing/settings`, data, { getToken }),
        successMessage: "Settings saved",
        invalidateKeys: [billingKeys.settings],
        onSuccess: () => setSettingsEditing(false),
    });

    // ---- Checkbox helpers (Invoice create) -------------------------------------

    function toggleTimeId(id: string) {
        setSelectedTimeIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    }

    function toggleExpenseId(id: string) {
        setSelectedExpenseIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    }

    // ===========================================================================
    // RENDER
    // ===========================================================================

    return (
        <div className="space-y-6">
            {/* ---- Summary Cards ---- */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
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
                            {summary ? fmtCurrency(summary.total_billable || 0) : <Skeleton className="h-8 w-20 inline-block" />}
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Expenses</p>
                        <p className="text-2xl font-bold mt-1">
                            {summary ? fmtCurrency(summary.total_expenses || 0) : <Skeleton className="h-8 w-20 inline-block" />}
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Invoiced</p>
                        <p className="text-2xl font-bold mt-1">{fmtCurrency(invoiceTotals.invoiced)}</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Paid</p>
                        <p className="text-2xl font-bold mt-1 text-green-600">{fmtCurrency(invoiceTotals.paid)}</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Outstanding</p>
                        <p className="text-2xl font-bold mt-1 text-red-600">
                            {fmtCurrency(invoiceTotals.outstanding)}
                        </p>
                    </CardContent>
                </Card>
            </div>

            {/* ---- Tabs ---- */}
            <Tabs defaultValue="time">
                <TabsList className="flex-wrap">
                    <TabsTrigger value="time">Time Entries ({timeEntries.length})</TabsTrigger>
                    <TabsTrigger value="expenses">Expenses ({expenses.length})</TabsTrigger>
                    <TabsTrigger value="invoices">Invoices ({caseInvoices.length})</TabsTrigger>
                    <TabsTrigger value="retainer">Retainer</TabsTrigger>
                    {(isAdmin || isAttorney) && <TabsTrigger value="aging">Aging Report</TabsTrigger>}
                    {isAdmin && <TabsTrigger value="settings">Settings</TabsTrigger>}
                </TabsList>

                {/* ================================================================
                   TAB 1: TIME ENTRIES
                   ================================================================ */}
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

                {/* ================================================================
                   TAB 2: EXPENSES
                   ================================================================ */}
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

                {/* ================================================================
                   TAB 3: INVOICES
                   ================================================================ */}
                <TabsContent value="invoices" className="space-y-4 mt-4">
                    {/* Invoice summary row */}
                    <div className="grid grid-cols-3 gap-4">
                        <Card>
                            <CardContent className="pt-3 pb-2">
                                <p className="text-xs text-muted-foreground uppercase">Total Invoiced</p>
                                <p className="text-lg font-bold">{fmtCurrency(invoiceTotals.invoiced)}</p>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardContent className="pt-3 pb-2">
                                <p className="text-xs text-muted-foreground uppercase">Paid</p>
                                <p className="text-lg font-bold text-green-600">{fmtCurrency(invoiceTotals.paid)}</p>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardContent className="pt-3 pb-2">
                                <p className="text-xs text-muted-foreground uppercase">Outstanding</p>
                                <p className="text-lg font-bold text-red-600">{fmtCurrency(invoiceTotals.outstanding)}</p>
                            </CardContent>
                        </Card>
                    </div>

                    {canEdit && (
                        <div className="flex justify-end">
                            <Button size="sm" className="gap-1.5" onClick={() => setInvoiceCreateOpen(true)}>
                                <span>+</span> Create Invoice
                            </Button>
                        </div>
                    )}

                    {/* Invoice list */}
                    {caseInvoices.length === 0 ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No invoices yet. Create one from unbilled time and expenses.
                            </CardContent>
                        </Card>
                    ) : (
                        caseInvoices.map((inv) => {
                            const style = INVOICE_STATUS_STYLE[inv.status] ?? { variant: "secondary" as const };
                            return (
                                <Card
                                    key={inv.id}
                                    className="hover:bg-accent/30 transition-colors cursor-pointer"
                                    onClick={() => setActiveInvoice(inv)}
                                >
                                    <CardContent className="flex items-center justify-between py-3">
                                        <div className="space-y-0.5">
                                            <div className="flex items-center gap-2">
                                                <p className="text-sm font-bold">{inv.invoice_number}</p>
                                                <Badge variant={style.variant} className={style.className}>
                                                    {inv.status}
                                                </Badge>
                                            </div>
                                            <p className="text-xs text-muted-foreground">
                                                {inv.date} · Due {inv.due_date}
                                            </p>
                                        </div>
                                        <div className="text-right">
                                            <p className="text-sm font-bold">{fmtCurrency(inv.total)}</p>
                                            {inv.balance > 0 && inv.balance !== inv.total && (
                                                <p className="text-xs text-muted-foreground">
                                                    Balance: {fmtCurrency(inv.balance)}
                                                </p>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            );
                        })
                    )}
                </TabsContent>

                {/* ================================================================
                   TAB 4: RETAINER
                   ================================================================ */}
                <TabsContent value="retainer" className="space-y-4 mt-4">
                    {/* Balance card */}
                    <Card>
                        <CardContent className="pt-6 pb-4 text-center">
                            <p className="text-xs font-medium text-muted-foreground uppercase mb-1">Retainer Balance</p>
                            {retainer ? (
                                <p className={`text-4xl font-bold ${retainer.balance >= 0 ? "text-green-600" : "text-red-600"}`}>
                                    {fmtCurrency(retainer.balance)}
                                </p>
                            ) : (
                                <Skeleton className="h-10 w-32 mx-auto" />
                            )}
                        </CardContent>
                    </Card>

                    {canEdit && (
                        <div className="flex justify-end gap-2">
                            <Button size="sm" variant="outline" className="gap-1.5" onClick={() => setDepositDialogOpen(true)}>
                                <span>+</span> Add Deposit
                            </Button>
                            <Button size="sm" variant="outline" className="gap-1.5 text-red-600 border-red-200 hover:bg-red-50" onClick={() => setDrawDialogOpen(true)}>
                                <span>&minus;</span> Record Draw
                            </Button>
                        </div>
                    )}

                    {/* Transaction history */}
                    {!retainer ? (
                        <div className="space-y-2">
                            {[1, 2, 3].map((n) => <Skeleton key={n} className="h-14 w-full rounded-lg" />)}
                        </div>
                    ) : retainer.history.length === 0 ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No retainer transactions yet.
                            </CardContent>
                        </Card>
                    ) : (
                        retainer.history.map((tx) => (
                            <Card key={tx.id}>
                                <CardContent className="flex items-center justify-between py-3">
                                    <div>
                                        <p className="text-sm font-medium">{tx.description}</p>
                                        <p className="text-xs text-muted-foreground">{tx.date}</p>
                                    </div>
                                    <p className={`text-sm font-bold ${tx.type === "deposit" ? "text-green-600" : "text-red-600"}`}>
                                        {tx.type === "deposit" ? "+" : "-"}{fmtCurrency(tx.amount)}
                                    </p>
                                </CardContent>
                            </Card>
                        ))
                    )}
                </TabsContent>

                {/* ================================================================
                   TAB 5: AGING REPORT
                   ================================================================ */}
                <TabsContent value="aging" className="space-y-4 mt-4">
                    {!(isAdmin || isAttorney) ? (
                        <Card>
                            <CardContent className="py-12 text-center text-muted-foreground">
                                Aging reports are available to administrators and attorneys only.
                            </CardContent>
                        </Card>
                    ) : !aging ? (
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                {[1, 2, 3, 4].map((n) => <Skeleton key={n} className="h-24 w-full rounded-lg" />)}
                            </div>
                        </div>
                    ) : (
                        <>
                            {/* Total outstanding */}
                            <Card>
                                <CardContent className="pt-4 pb-3 text-center">
                                    <p className="text-xs font-medium text-muted-foreground uppercase">Total Outstanding</p>
                                    <p className="text-3xl font-bold mt-1 text-red-600">
                                        {fmtCurrency(aging.total_outstanding)}
                                    </p>
                                </CardContent>
                            </Card>

                            {/* Aging buckets */}
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                {([
                                    { key: "current", label: "Current (0-30 days)", data: aging.current },
                                    { key: "thirty", label: "30-60 days", data: aging.thirty },
                                    { key: "sixty", label: "60-90 days", data: aging.sixty },
                                    { key: "ninety_plus", label: "90+ days", data: aging.ninety_plus },
                                ] as const).map(({ key, label, data }) => (
                                    <Card key={key}>
                                        <CardContent className="pt-4 pb-3">
                                            <p className="text-xs font-medium text-muted-foreground uppercase">{label}</p>
                                            <p className={`text-xl font-bold mt-1 ${data.total > 0 ? "text-red-600" : ""}`}>
                                                {fmtCurrency(data.total)}
                                            </p>
                                            <p className="text-xs text-muted-foreground mt-0.5">
                                                {data.invoices.length} invoice{data.invoices.length !== 1 ? "s" : ""}
                                            </p>
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>

                            {/* Breakdown list */}
                            {([
                                { label: "Current (0-30 days)", data: aging.current },
                                { label: "30-60 days", data: aging.thirty },
                                { label: "60-90 days", data: aging.sixty },
                                { label: "90+ days", data: aging.ninety_plus },
                            ] as const).map(({ label, data }) =>
                                data.invoices.length > 0 && (
                                    <div key={label}>
                                        <h3 className="text-sm font-semibold mb-2">{label}</h3>
                                        {data.invoices.map((inv, idx) => (
                                            <Card key={idx} className="mb-1">
                                                <CardContent className="flex items-center justify-between py-2">
                                                    <div>
                                                        <p className="text-sm font-medium">{inv.invoice_number}</p>
                                                        <p className="text-xs text-muted-foreground">{inv.client} · {inv.days} days</p>
                                                    </div>
                                                    <p className="text-sm font-bold text-red-600">{fmtCurrency(inv.amount)}</p>
                                                </CardContent>
                                            </Card>
                                        ))}
                                    </div>
                                )
                            )}
                        </>
                    )}
                </TabsContent>

                {/* ================================================================
                   TAB 6: SETTINGS
                   ================================================================ */}
                <TabsContent value="settings" className="space-y-4 mt-4">
                    {!isAdmin ? (
                        <Card>
                            <CardContent className="py-12 text-center text-muted-foreground">
                                Billing settings are available to administrators only.
                            </CardContent>
                        </Card>
                    ) : !settings ? (
                        <div className="space-y-3">
                            {[1, 2, 3, 4, 5].map((n) => <Skeleton key={n} className="h-12 w-full rounded-lg" />)}
                        </div>
                    ) : (
                        <SettingsForm
                            settings={settings}
                            isEditing={settingsEditing}
                            setIsEditing={setSettingsEditing}
                            onSave={(data) => saveSettings.mutate(data)}
                            isLoading={saveSettings.isPending}
                        />
                    )}
                </TabsContent>
            </Tabs>

            {/* ================================================================
               DIALOGS & PANELS
               ================================================================ */}

            {/* Time Entry create dialog */}
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

            {/* Delete confirm */}
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

            {/* ---- Invoice Create Dialog ---- */}
            <Dialog open={invoiceCreateOpen} onOpenChange={setInvoiceCreateOpen}>
                <DialogContent className="sm:max-w-lg max-h-[80vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Create Invoice</DialogTitle>
                        <DialogDescription>Select unbilled time entries and expenses to include.</DialogDescription>
                    </DialogHeader>

                    {/* Unbilled time entries */}
                    <div className="space-y-2">
                        <h4 className="text-sm font-semibold">Time Entries</h4>
                        {unbilledTime.length === 0 ? (
                            <p className="text-xs text-muted-foreground">No unbilled time entries.</p>
                        ) : (
                            <>
                                <div className="flex gap-2 mb-1">
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setSelectedTimeIds(new Set(unbilledTime.map((t) => t.id)))}
                                    >
                                        Select All
                                    </Button>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setSelectedTimeIds(new Set())}
                                    >
                                        Clear
                                    </Button>
                                </div>
                                {unbilledTime.map((t) => (
                                    <label key={t.id} className="flex items-center gap-2 text-sm py-1 cursor-pointer hover:bg-accent/20 rounded px-1">
                                        <Checkbox
                                            checked={selectedTimeIds.has(t.id)}
                                            onCheckedChange={() => toggleTimeId(t.id)}
                                        />
                                        <span className="flex-1 truncate">{t.description}</span>
                                        <span className="text-muted-foreground">{t.hours}h</span>
                                        <span className="font-medium">{fmtCurrency(t.hours * t.rate)}</span>
                                    </label>
                                ))}
                            </>
                        )}
                    </div>

                    {/* Unbilled expenses */}
                    <div className="space-y-2">
                        <h4 className="text-sm font-semibold">Expenses</h4>
                        {unbilledExpenses.length === 0 ? (
                            <p className="text-xs text-muted-foreground">No unbilled expenses.</p>
                        ) : (
                            <>
                                <div className="flex gap-2 mb-1">
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setSelectedExpenseIds(new Set(unbilledExpenses.map((e) => e.id)))}
                                    >
                                        Select All
                                    </Button>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setSelectedExpenseIds(new Set())}
                                    >
                                        Clear
                                    </Button>
                                </div>
                                {unbilledExpenses.map((e) => (
                                    <label key={e.id} className="flex items-center gap-2 text-sm py-1 cursor-pointer hover:bg-accent/20 rounded px-1">
                                        <Checkbox
                                            checked={selectedExpenseIds.has(e.id)}
                                            onCheckedChange={() => toggleExpenseId(e.id)}
                                        />
                                        <span className="flex-1 truncate">{e.description}</span>
                                        <span className="font-medium">{fmtCurrency(e.amount)}</span>
                                    </label>
                                ))}
                            </>
                        )}
                    </div>

                    {/* Notes */}
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium">Notes</label>
                        <textarea
                            value={invoiceNotes}
                            onChange={(e) => setInvoiceNotes(e.target.value)}
                            rows={3}
                            placeholder="Optional invoice notes..."
                            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
                        />
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setInvoiceCreateOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            disabled={
                                (selectedTimeIds.size === 0 && selectedExpenseIds.size === 0) ||
                                createInvoice.isPending
                            }
                            onClick={() =>
                                createInvoice.mutate({
                                    time_entry_ids: Array.from(selectedTimeIds),
                                    expense_ids: Array.from(selectedExpenseIds),
                                    notes: invoiceNotes,
                                })
                            }
                        >
                            {createInvoice.isPending ? "Creating..." : "Create Invoice"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* ---- Invoice Detail Panel ---- */}
            <Dialog open={!!activeInvoice} onOpenChange={(open) => !open && setActiveInvoice(null)}>
                <DialogContent className="sm:max-w-lg max-h-[80vh] overflow-y-auto">
                    {activeInvoice && (
                        <>
                            <DialogHeader>
                                <DialogTitle className="flex items-center gap-2">
                                    {activeInvoice.invoice_number}
                                    <Badge
                                        variant={INVOICE_STATUS_STYLE[activeInvoice.status]?.variant ?? "secondary"}
                                        className={INVOICE_STATUS_STYLE[activeInvoice.status]?.className}
                                    >
                                        {activeInvoice.status}
                                    </Badge>
                                </DialogTitle>
                                <DialogDescription>
                                    Issued {activeInvoice.date} · Due {activeInvoice.due_date}
                                </DialogDescription>
                            </DialogHeader>

                            {/* Totals */}
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <p className="text-xs text-muted-foreground uppercase">Total</p>
                                    <p className="text-lg font-bold">{fmtCurrency(activeInvoice.total)}</p>
                                </div>
                                <div>
                                    <p className="text-xs text-muted-foreground uppercase">Balance Due</p>
                                    <p className={`text-lg font-bold ${activeInvoice.balance > 0 ? "text-red-600" : "text-green-600"}`}>
                                        {fmtCurrency(activeInvoice.balance)}
                                    </p>
                                </div>
                            </div>

                            {/* Status update */}
                            {canEdit && activeInvoice.status !== "void" && (
                                <div className="flex items-center gap-2">
                                    <Select
                                        value={statusUpdateId === activeInvoice.id ? newStatus : activeInvoice.status}
                                        onValueChange={(val) => {
                                            setStatusUpdateId(activeInvoice.id);
                                            setNewStatus(val);
                                        }}
                                    >
                                        <SelectTrigger className="w-40">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="draft">Draft</SelectItem>
                                            <SelectItem value="sent">Sent</SelectItem>
                                            <SelectItem value="paid">Paid</SelectItem>
                                            <SelectItem value="overdue">Overdue</SelectItem>
                                            <SelectItem value="void">Void</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    {statusUpdateId === activeInvoice.id && newStatus && newStatus !== activeInvoice.status && (
                                        <Button
                                            size="sm"
                                            disabled={updateInvoiceStatus.isPending}
                                            onClick={() =>
                                                updateInvoiceStatus.mutate({ id: activeInvoice.id, status: newStatus })
                                            }
                                        >
                                            {updateInvoiceStatus.isPending ? "Updating..." : "Update Status"}
                                        </Button>
                                    )}
                                </div>
                            )}

                            {/* Line items */}
                            <div className="space-y-1">
                                <h4 className="text-sm font-semibold">Line Items</h4>
                                {activeInvoice.line_items.length === 0 ? (
                                    <p className="text-xs text-muted-foreground">No line items.</p>
                                ) : (
                                    activeInvoice.line_items.map((li, idx) => (
                                        <div key={li.id || idx} className="flex items-center justify-between py-1.5 border-b last:border-0">
                                            <div>
                                                <p className="text-sm">{li.description}</p>
                                                <p className="text-xs text-muted-foreground">
                                                    {li.type === "time" ? `${li.quantity}h @ ${fmtCurrency(li.rate)}/hr` : li.type}
                                                </p>
                                            </div>
                                            <p className="text-sm font-medium">{fmtCurrency(li.amount)}</p>
                                        </div>
                                    ))
                                )}
                            </div>

                            {/* Payments */}
                            <div className="space-y-1">
                                <h4 className="text-sm font-semibold">Payments</h4>
                                {invoicePayments.length === 0 ? (
                                    <p className="text-xs text-muted-foreground">No payments recorded.</p>
                                ) : (
                                    invoicePayments.map((p) => (
                                        <div key={p.id} className="flex items-center justify-between py-1.5 border-b last:border-0">
                                            <div>
                                                <p className="text-sm">{p.method}</p>
                                                <p className="text-xs text-muted-foreground">
                                                    {p.date}{p.notes && ` · ${p.notes}`}
                                                </p>
                                            </div>
                                            <p className="text-sm font-bold text-green-600">+{fmtCurrency(p.amount)}</p>
                                        </div>
                                    ))
                                )}
                            </div>

                            {/* Actions */}
                            <DialogFooter className="gap-2 flex-wrap">
                                {canEdit && activeInvoice.status !== "void" && (
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => setPaymentDialogOpen(true)}
                                    >
                                        Record Payment
                                    </Button>
                                )}
                                <Button
                                    size="sm"
                                    variant="outline"
                                    disabled={downloadInvoicePdf.isPending}
                                    onClick={() => downloadInvoicePdf.mutate(activeInvoice.id)}
                                >
                                    {downloadInvoicePdf.isPending ? "Downloading..." : "Download PDF"}
                                </Button>
                            </DialogFooter>
                        </>
                    )}
                </DialogContent>
            </Dialog>

            {/* ---- Record Payment Dialog ---- */}
            {canEdit && (
                <FormDialog
                    open={paymentDialogOpen}
                    onOpenChange={setPaymentDialogOpen}
                    title="Record Payment"
                    description={activeInvoice ? `For invoice ${activeInvoice.invoice_number} — Balance: ${fmtCurrency(activeInvoice.balance)}` : undefined}
                    schema={paymentSchema}
                    defaultValues={{
                        date: new Date().toISOString().split("T")[0],
                        amount: activeInvoice?.balance ?? 0,
                        method: "check",
                        notes: "",
                    }}
                    fields={paymentFields}
                    onSubmit={(data) => recordPayment.mutate(data)}
                    submitLabel="Record Payment"
                    isLoading={recordPayment.isPending}
                />
            )}

            {/* ---- Retainer Deposit Dialog ---- */}
            {canEdit && (
                <>
                    <FormDialog
                        open={depositDialogOpen}
                        onOpenChange={setDepositDialogOpen}
                        title="Add Retainer Deposit"
                        schema={retainerSchema}
                        defaultValues={{ amount: 0, description: "" }}
                        fields={retainerFields}
                        onSubmit={(data) => addDeposit.mutate(data)}
                        submitLabel="Add Deposit"
                        isLoading={addDeposit.isPending}
                    />
                    <FormDialog
                        open={drawDialogOpen}
                        onOpenChange={setDrawDialogOpen}
                        title="Record Retainer Draw"
                        schema={retainerSchema}
                        defaultValues={{ amount: 0, description: "" }}
                        fields={retainerFields}
                        onSubmit={(data) => recordDraw.mutate(data)}
                        submitLabel="Record Draw"
                        isLoading={recordDraw.isPending}
                    />
                </>
            )}
        </div>
    );
}

// ---- Settings Form (extracted for readability) ----------------------------

function SettingsForm({
    settings,
    isEditing,
    setIsEditing,
    onSave,
    isLoading,
}: {
    settings: BillingSettings;
    isEditing: boolean;
    setIsEditing: (v: boolean) => void;
    onSave: (data: SettingsInput) => void;
    isLoading: boolean;
}) {
    const [form, setForm] = useState<SettingsInput>({ ...settings });

    function handleChange(field: keyof SettingsInput, value: string | number) {
        setForm((prev) => ({ ...prev, [field]: value }));
    }

    const fields: { key: keyof SettingsInput; label: string; type: "text" | "number" }[] = [
        { key: "default_rate", label: "Default Hourly Rate ($)", type: "number" },
        { key: "payment_terms_days", label: "Payment Terms (days)", type: "number" },
        { key: "firm_name", label: "Firm Name", type: "text" },
        { key: "address", label: "Address", type: "text" },
        { key: "phone", label: "Phone", type: "text" },
        { key: "email", label: "Email", type: "text" },
        { key: "tax_rate", label: "Tax Rate (%)", type: "number" },
    ];

    return (
        <Card>
            <CardContent className="pt-6 space-y-4">
                {fields.map(({ key, label, type }) => (
                    <div key={key} className="space-y-1.5">
                        <label className="text-sm font-medium text-muted-foreground">{label}</label>
                        {isEditing ? (
                            <Input
                                type={type}
                                step={type === "number" ? "any" : undefined}
                                value={form[key] ?? ""}
                                onChange={(e) =>
                                    handleChange(
                                        key,
                                        type === "number" ? parseFloat(e.target.value) || 0 : e.target.value,
                                    )
                                }
                            />
                        ) : (
                            <p className="text-sm py-1">
                                {type === "number" && (key === "default_rate" || key === "tax_rate")
                                    ? key === "tax_rate"
                                        ? `${settings[key]}%`
                                        : fmtCurrency(settings[key] as number)
                                    : String(settings[key] ?? "\u2014")}
                            </p>
                        )}
                    </div>
                ))}

                <div className="flex gap-2 pt-2">
                    {isEditing ? (
                        <>
                            <Button
                                variant="outline"
                                onClick={() => {
                                    setForm({ ...settings });
                                    setIsEditing(false);
                                }}
                            >
                                Cancel
                            </Button>
                            <Button disabled={isLoading} onClick={() => onSave(form)}>
                                {isLoading ? "Saving..." : "Save Settings"}
                            </Button>
                        </>
                    ) : (
                        <Button variant="outline" onClick={() => setIsEditing(true)}>
                            Edit Settings
                        </Button>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
