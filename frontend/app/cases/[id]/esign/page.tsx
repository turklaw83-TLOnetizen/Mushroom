// ---- E-Signature Tab ----------------------------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SignatureRequest {
    signature_request_id: string;
    local_id: string;
    title: string;
    signer_name: string;
    signer_email: string;
    status: "pending" | "sent" | "viewed" | "signed" | "declined" | "expired" | "cancelled" | "not_configured" | "error";
    created_at: string;
    file_key: string;
    message?: string;
    reminder_count?: number;
    last_reminder_at?: string;
}

interface SendPayload {
    file_key: string;
    signer_name: string;
    signer_email: string;
    title: string;
    subject: string;
    message: string;
}

// ---------------------------------------------------------------------------
// Status colors
// ---------------------------------------------------------------------------

const statusColors: Record<string, string> = {
    pending: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    sent: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    viewed: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30",
    signed: "bg-green-500/15 text-green-400 border-green-500/30",
    declined: "bg-red-500/15 text-red-400 border-red-500/30",
    cancelled: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    expired: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    not_configured: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    error: "bg-red-500/15 text-red-400 border-red-500/30",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
    try {
        return new Date(iso).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    } catch {
        return iso;
    }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ESignPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { canEdit } = useRole();

    const queryClient = useQueryClient();
    const [dialogOpen, setDialogOpen] = useState(false);
    const [remindingId, setRemindingId] = useState<string | null>(null);

    // Form fields
    const [fileKey, setFileKey] = useState("");
    const [signerName, setSignerName] = useState("");
    const [signerEmail, setSignerEmail] = useState("");
    const [title, setTitle] = useState("");
    const [message, setMessage] = useState("");

    // ---- Queries -----------------------------------------------------------

    const requestsQuery = useQuery({
        queryKey: ["esign", "requests", caseId],
        queryFn: () =>
            api.get<{ items: SignatureRequest[] }>(
                `/cases/${caseId}/esign/requests`,
                { getToken },
            ),
    });

    const requests = requestsQuery.data?.items ?? [];

    // ---- Mutations ---------------------------------------------------------

    const sendMutation = useMutationWithToast<SendPayload>({
        mutationFn: (data) =>
            api.post(`/cases/${caseId}/esign/send`, data, { getToken }),
        successMessage: "Signature request sent",
        errorMessage: "Failed to send signature request",
        invalidateKeys: [["esign", "requests", caseId]],
        onSuccess: () => {
            setDialogOpen(false);
            resetForm();
        },
    });

    const reminderMutation = useMutation({
        mutationFn: (requestId: string) =>
            api.post(`/cases/${caseId}/esign/requests/${requestId}/remind`, {}, { getToken }),
        onSuccess: (_result, requestId) => {
            toast.success("Reminder sent");
            queryClient.invalidateQueries({ queryKey: ["esign", "requests", caseId] });
            setRemindingId(null);
        },
        onError: (err) => {
            toast.error("Failed to send reminder", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
            setRemindingId(null);
        },
    });

    function handleSendReminder(requestId: string) {
        setRemindingId(requestId);
        reminderMutation.mutate(requestId);
    }

    function resetForm() {
        setFileKey("");
        setSignerName("");
        setSignerEmail("");
        setTitle("");
        setMessage("");
    }

    function handleSend() {
        if (!fileKey.trim() || !signerName.trim() || !signerEmail.trim() || !title.trim()) {
            toast.error("Please fill in all required fields");
            return;
        }
        sendMutation.mutate({
            file_key: fileKey.trim(),
            signer_name: signerName.trim(),
            signer_email: signerEmail.trim(),
            title: title.trim(),
            subject: title.trim(),
            message: message.trim(),
        });
    }

    // ---- Render ------------------------------------------------------------

    return (
        <div className="space-y-5">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">
                        E-Signatures
                    </h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Send documents for signature and track request status
                    </p>
                </div>
                {canEdit && (
                    <Button size="sm" onClick={() => setDialogOpen(true)}>
                        + Send for Signature
                    </Button>
                )}
            </div>

            {/* Request list */}
            {requestsQuery.isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-16 w-full rounded-lg" />
                    ))}
                </div>
            ) : requests.length === 0 ? (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        No signature requests yet.
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-2">
                    {requests.map((req) => (
                        <Card
                            key={req.signature_request_id}
                            className="hover:bg-accent/20 transition-colors"
                        >
                            <CardContent className="flex items-center justify-between py-3">
                                <div className="min-w-0">
                                    <p className="text-sm font-medium truncate">
                                        {req.title}
                                    </p>
                                    <p className="text-xs text-muted-foreground mt-0.5">
                                        {req.signer_name} &middot;{" "}
                                        {req.signer_email}
                                    </p>
                                </div>
                                <div className="flex items-center gap-3 shrink-0">
                                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                                        {formatDate(req.created_at)}
                                    </span>
                                    {["pending", "sent", "viewed"].includes(req.status) && canEdit && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="text-xs h-7"
                                            disabled={remindingId === (req.local_id || req.signature_request_id)}
                                            onClick={() => handleSendReminder(req.local_id || req.signature_request_id)}
                                        >
                                            {remindingId === (req.local_id || req.signature_request_id)
                                                ? "Sending..."
                                                : "Send Reminder"}
                                        </Button>
                                    )}
                                    <Badge
                                        variant="outline"
                                        className={
                                            statusColors[req.status] ||
                                            statusColors.pending
                                        }
                                    >
                                        {req.status}
                                    </Badge>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Send for Signature Dialog */}
            <Dialog
                open={dialogOpen}
                onOpenChange={(open) => {
                    setDialogOpen(open);
                    if (!open) resetForm();
                }}
            >
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Send for Signature</DialogTitle>
                        <DialogDescription>
                            Send a document for e-signature. The signer will
                            receive an email with a link to sign.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-2">
                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">
                                File Key <span className="text-destructive">*</span>
                            </label>
                            <Input
                                placeholder="e.g. contracts/agreement.pdf"
                                value={fileKey}
                                onChange={(e) => setFileKey(e.target.value)}
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">
                                Signer Name <span className="text-destructive">*</span>
                            </label>
                            <Input
                                placeholder="John Doe"
                                value={signerName}
                                onChange={(e) => setSignerName(e.target.value)}
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">
                                Signer Email <span className="text-destructive">*</span>
                            </label>
                            <Input
                                type="email"
                                placeholder="john@example.com"
                                value={signerEmail}
                                onChange={(e) =>
                                    setSignerEmail(e.target.value)
                                }
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">
                                Title <span className="text-destructive">*</span>
                            </label>
                            <Input
                                placeholder="Retainer Agreement"
                                value={title}
                                onChange={(e) => setTitle(e.target.value)}
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">
                                Message
                            </label>
                            <textarea
                                className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:border-ring min-h-[80px] resize-y dark:bg-input/30"
                                placeholder="Optional message to include in the signing email..."
                                value={message}
                                onChange={(e) => setMessage(e.target.value)}
                            />
                        </div>
                    </div>

                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => {
                                setDialogOpen(false);
                                resetForm();
                            }}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={handleSend}
                            disabled={sendMutation.isPending}
                        >
                            {sendMutation.isPending
                                ? "Sending..."
                                : "Send Request"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
