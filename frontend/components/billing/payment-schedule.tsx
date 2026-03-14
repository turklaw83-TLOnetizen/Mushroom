// ---- Payment Schedule Table ----------------------------------------------
// Displays the list of scheduled payments with status badges.
"use client";

import { Badge } from "@/components/ui/badge";
import type { ScheduledPayment } from "@/types/api";

const STATUS_STYLES: Record<string, { label: string; variant: "default" | "secondary" | "outline" | "destructive" }> = {
    paid: { label: "Paid", variant: "default" },
    pending: { label: "Pending", variant: "outline" },
    partial: { label: "Partial", variant: "secondary" },
    overdue: { label: "Overdue", variant: "destructive" },
    waived: { label: "Waived", variant: "outline" },
};

const TYPE_LABELS: Record<string, string> = {
    down_payment: "Down Payment",
    recurring: "Recurring",
    final: "Final",
};

function formatDate(dateStr: string): string {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

interface PaymentScheduleProps {
    schedule: ScheduledPayment[];
}

export function PaymentSchedule({ schedule }: PaymentScheduleProps) {
    if (schedule.length === 0) {
        return (
            <p className="text-sm text-muted-foreground py-4 text-center">
                No scheduled payments.
            </p>
        );
    }

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-sm">
                <thead className="sticky top-0 z-10 bg-background">
                    <tr className="border-b text-xs text-muted-foreground">
                        <th className="text-left py-2 px-2 font-medium">Due Date</th>
                        <th className="text-left py-2 px-2 font-medium">Type</th>
                        <th className="text-right py-2 px-2 font-medium">Amount</th>
                        <th className="text-right py-2 px-2 font-medium">Paid</th>
                        <th className="text-center py-2 px-2 font-medium">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {schedule.map((sp) => {
                        const style = STATUS_STYLES[sp.status] || STATUS_STYLES.pending;
                        return (
                            <tr key={sp.id} className="border-b last:border-0 hover:bg-accent/30 transition-colors">
                                <td className="py-2 px-2 font-mono text-xs">
                                    {formatDate(sp.due_date)}
                                </td>
                                <td className="py-2 px-2 text-xs text-muted-foreground">
                                    {TYPE_LABELS[sp.type] || sp.type}
                                </td>
                                <td className="py-2 px-2 text-right font-medium">
                                    ${sp.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                    {sp.late_fee_applied > 0 && (
                                        <span className="text-[10px] text-destructive ml-1">
                                            (+${sp.late_fee_applied} fee)
                                        </span>
                                    )}
                                </td>
                                <td className="py-2 px-2 text-right">
                                    {sp.paid_amount > 0 ? (
                                        <span className="text-emerald-500 font-medium">
                                            ${sp.paid_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                        </span>
                                    ) : (
                                        <span className="text-muted-foreground">-</span>
                                    )}
                                </td>
                                <td className="py-2 px-2 text-center">
                                    <Badge variant={style.variant} className="text-[10px]">
                                        {style.label}
                                    </Badge>
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}
