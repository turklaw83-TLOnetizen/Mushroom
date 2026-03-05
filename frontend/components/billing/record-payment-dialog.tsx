// ---- Record Payment Dialog -----------------------------------------------
// Form dialog for recording a payment against a payment plan.
"use client";

import { z } from "zod";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";

const paymentSchema = z.object({
    amount: z.number().min(0.01, "Amount required"),
    date: z.string().min(1, "Date required"),
    method: z.string().optional().default(""),
    payer_name: z.string().max(200).optional().default(""),
    note: z.string().max(2000).optional().default(""),
});

export type PaymentInput = z.infer<typeof paymentSchema>;

const paymentFields: FieldConfig<PaymentInput>[] = [
    { name: "amount", label: "Amount ($)", type: "number", required: true, placeholder: "200.00" },
    { name: "date", label: "Date Received", required: true, placeholder: "2026-03-10" },
    {
        name: "method",
        label: "Payment Method",
        type: "select",
        options: [
            { value: "", label: "Select..." },
            { value: "cash", label: "Cash" },
            { value: "check", label: "Check" },
            { value: "card", label: "Card" },
            { value: "wire", label: "Wire Transfer" },
            { value: "zelle", label: "Zelle" },
            { value: "venmo", label: "Venmo" },
        ],
    },
    { name: "payer_name", label: "Paid By", placeholder: "Name of person/entity who sent payment" },
    { name: "note", label: "Notes", type: "textarea", placeholder: "e.g. Check #1234, money order from client's mother" },
];

interface RecordPaymentDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSubmit: (data: PaymentInput) => void;
    isLoading?: boolean;
}

export function RecordPaymentDialog({ open, onOpenChange, onSubmit, isLoading }: RecordPaymentDialogProps) {
    return (
        <FormDialog
            open={open}
            onOpenChange={onOpenChange}
            title="Record Payment"
            description="Record a payment received against this plan."
            schema={paymentSchema}
            defaultValues={{
                amount: 0,
                date: new Date().toISOString().split("T")[0],
                method: "",
                payer_name: "",
                note: "",
            }}
            fields={paymentFields}
            onSubmit={onSubmit}
            submitLabel="Record Payment"
            isLoading={isLoading}
        />
    );
}
