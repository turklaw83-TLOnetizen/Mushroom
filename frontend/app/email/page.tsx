// ---- Email Queue Page ----------------------------------------------------
// Review incoming emails, classify to cases or dismiss.
"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface EmailItem {
    id: string;
    subject: string;
    sender: string;
    date: string;
    snippet: string;
    status: string;
    suggested_case?: string;
}

export default function EmailQueuePage() {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    const { data, isLoading } = useQuery({
        queryKey: ["email-queue"],
        queryFn: () => api.get<{ items: EmailItem[]; total: number }>("/email/queue", { getToken }),
    });

    const { data: stats } = useQuery({
        queryKey: ["email-stats"],
        queryFn: () => api.get<{ pending: number; approved: number; dismissed: number }>("/email/queue/stats", { getToken }),
    });

    const classify = useMutation({
        mutationFn: (vars: { email_id: string; case_id: string }) =>
            api.post("/email/classify", vars, { getToken }),
        onSuccess: () => {
            toast.success("Email classified");
            queryClient.invalidateQueries({ queryKey: ["email-queue"] });
            queryClient.invalidateQueries({ queryKey: ["email-stats"] });
        },
    });

    const dismiss = useMutation({
        mutationFn: (email_id: string) =>
            api.post("/email/dismiss", { email_id }, { getToken }),
        onSuccess: () => {
            toast.success("Email dismissed");
            queryClient.invalidateQueries({ queryKey: ["email-queue"] });
            queryClient.invalidateQueries({ queryKey: ["email-stats"] });
        },
    });

    const emails = data?.items ?? [];

    return (
        <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Email Queue</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Review and classify incoming emails
                </p>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-4">
                <Card>
                    <CardContent className="pt-4 pb-3 text-center">
                        <p className="text-xs text-muted-foreground uppercase">Pending</p>
                        <p className="text-2xl font-bold text-amber-400">{stats?.pending ?? 0}</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3 text-center">
                        <p className="text-xs text-muted-foreground uppercase">Approved</p>
                        <p className="text-2xl font-bold text-green-400">{stats?.approved ?? 0}</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3 text-center">
                        <p className="text-xs text-muted-foreground uppercase">Dismissed</p>
                        <p className="text-2xl font-bold text-muted-foreground">{stats?.dismissed ?? 0}</p>
                    </CardContent>
                </Card>
            </div>

            {/* Email List */}
            {isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-24 w-full rounded-lg" />
                    ))}
                </div>
            ) : emails.length === 0 ? (
                <Card>
                    <CardContent className="py-12 text-center text-muted-foreground">
                        📭 No emails in the queue
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-3">
                    {emails.map((email) => (
                        <Card key={email.id} className="hover:border-primary/30 transition-colors">
                            <CardContent className="pt-4 pb-3">
                                <div className="flex items-start justify-between gap-4">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <p className="text-sm font-medium truncate">{email.subject}</p>
                                            <Badge variant={email.status === "pending" ? "secondary" : "outline"} className="text-[10px]">
                                                {email.status}
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-muted-foreground mt-0.5">
                                            From: {email.sender} · {email.date}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                            {email.snippet}
                                        </p>
                                    </div>
                                    {email.status === "pending" && (
                                        <div className="flex gap-2 shrink-0">
                                            {email.suggested_case && (
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() => classify.mutate({ email_id: email.id, case_id: email.suggested_case! })}
                                                    disabled={classify.isPending}
                                                >
                                                    ✅ Classify
                                                </Button>
                                            )}
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                onClick={() => dismiss.mutate(email.id)}
                                                disabled={dismiss.isPending}
                                            >
                                                🚫
                                            </Button>
                                        </div>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
