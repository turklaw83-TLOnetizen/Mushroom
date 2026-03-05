// ---- AI Plan Generator ---------------------------------------------------
// Natural language input that calls AI to parse payment plan parameters.
// Shows parsed result for confirmation before creating the plan.
"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface ParsedPlanParams {
    total_amount: number;
    down_payment: number;
    recurring_amount: number;
    frequency: string;
    start_date: string;
    notes?: string;
}

interface AIPlanGeneratorProps {
    clientId: string;
    clientName?: string;
    onPlanParsed: (params: ParsedPlanParams) => void;
}

export function AIPlanGenerator({ clientId, clientName, onPlanParsed }: AIPlanGeneratorProps) {
    const { getToken } = useAuth();
    const [input, setInput] = useState("");
    const [parsed, setParsed] = useState<ParsedPlanParams | null>(null);

    const parseMutation = useMutation({
        mutationFn: () =>
            api.post<{ status: string; plan_params: ParsedPlanParams }>(
                `/crm/clients/${clientId}/payment-plan/ai-generate`,
                { text: input, client_name: clientName || "" },
                { getToken },
            ),
        onSuccess: (data) => {
            setParsed(data.plan_params);
        },
    });

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || parseMutation.isPending) return;
        setParsed(null);
        parseMutation.mutate();
    };

    const handleConfirm = () => {
        if (parsed) {
            onPlanParsed(parsed);
            setParsed(null);
            setInput("");
        }
    };

    return (
        <div className="space-y-3">
            <form onSubmit={handleSubmit} className="flex gap-2">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder='e.g. "$5000, $1k down immediately, $200 every Friday"'
                    className="flex-1 rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                />
                <Button
                    type="submit"
                    size="sm"
                    disabled={!input.trim() || parseMutation.isPending}
                >
                    {parseMutation.isPending ? (
                        <span className="flex items-center gap-2">
                            <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                            Parsing...
                        </span>
                    ) : (
                        "Create with AI"
                    )}
                </Button>
            </form>

            {parseMutation.isError && (
                <p className="text-xs text-destructive">
                    Failed to parse. Try rephrasing (e.g. &quot;$3000 total, $500 down, $250 per month&quot;).
                </p>
            )}

            {parsed && (
                <Card className="border-primary/30 bg-primary/5">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium flex items-center gap-2">
                            Parsed Plan
                            <Badge variant="outline" className="text-[10px]">Review & Confirm</Badge>
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
                            <div>
                                <span className="text-muted-foreground text-xs">Total:</span>{" "}
                                <span className="font-bold">${parsed.total_amount.toLocaleString()}</span>
                            </div>
                            <div>
                                <span className="text-muted-foreground text-xs">Down Payment:</span>{" "}
                                <span className="font-bold">${parsed.down_payment.toLocaleString()}</span>
                            </div>
                            <div>
                                <span className="text-muted-foreground text-xs">Recurring:</span>{" "}
                                <span className="font-bold">${parsed.recurring_amount.toLocaleString()}</span>
                            </div>
                            <div>
                                <span className="text-muted-foreground text-xs">Frequency:</span>{" "}
                                <span className="font-bold capitalize">{parsed.frequency}</span>
                            </div>
                            <div>
                                <span className="text-muted-foreground text-xs">Start Date:</span>{" "}
                                <span className="font-bold">{parsed.start_date}</span>
                            </div>
                        </div>
                        {parsed.notes && (
                            <p className="text-xs text-muted-foreground mt-1">{parsed.notes}</p>
                        )}
                        <div className="flex gap-2 pt-2">
                            <Button size="sm" onClick={handleConfirm}>
                                Create This Plan
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setParsed(null)}>
                                Cancel
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
