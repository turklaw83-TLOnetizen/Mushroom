// ---- E-Signature Tab ----------------------------------------------------
// Refactored to use shared infra: routes, queryKeys, StatusBadge, formatDate.
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { routes } from "@/lib/api-routes";
import { queryKeys } from "@/lib/query-keys";
import { formatDate } from "@/lib/constants";
import { useRole } from "@/hooks/use-role";
import { useCrud } from "@/hooks/use-crud";
import { StatusBadge } from "@/components/shared/status-badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
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
    const [checkingStatusId, setCheckingStatusId] = useState<string | null>(null);

    // Form fields
    const [fileKey, setFileKey] = useState("");
    const [signerName, setSignerName] = useState("");
    const [signerEmail, setSignerEmail] = useState("");
    const [title, setTitle] = useState("");
    const [message, setMessage] = useState("");

    // ---- useCrud for list query ---------------------------------------------

    const { items: requests, isLoading: requestsLoading, create: sendMutation } = useCrud<SignatureRequest, SendPayload>({
        queryKey: queryKeys.esign.requests(caseId),
        listPath: routes.esign.requests(caseId),
        createPath: routes.esign.send(caseId),
        entityName: "Signature request",
        onCreateSuccess: () => {
            setDialogOpen(false);
            resetForm();
        },
    });

    // ---- Additional Mutations (remind + status check) -----------------------

    const reminderMutation = useMutation({
        mutationFn: (requestId: string) =>
            api.post(routes.esign.remind(caseId, requestId), {}, { getToken }),
        onSuccess: () => {
            toast.success("Reminder sent");
            queryClient.invalidateQueries({ queryKey: [...queryKeys.esign.requests(caseId)] });
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

    const statusCheckMutation = useMutation({
        mutationFn: (requestId: string) =>
            api.get<{ status: string }>(
                routes.esign.status(caseId, requestId),
                { getToken },
            ),
        onSuccess: () => {
            toast.success("Status updated");
            queryClient.invalidateQueries({ queryKey: [...queryKeys.esign.requests(caseId)] });
            setCheckingStatusId(null);
        },
        onError: (err) => {
            toast.error("Failed to check status", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
            setCheckingStatusId(null);
        },
    });

    function handleCheckStatus(requestId: string) {
        setCheckingStatusId(requestId);
        statusCheckMutation.mutate(requestId);
    }

    async function handleDownload(requestId: string, docTitle: string) {
        try {
            const token = await getToken();
            const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const res = await fetch(
                `${baseUrl}/api/v1${routes.esign.download(caseId, requestId)}`,
                {
                    headers: { Authorization: `Bearer ${token}` },
                },
            );
            if (!res.ok) throw new Error("Download failed");
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${docTitle}-signed.pdf`;
            a.click();
            URL.revokeObjectURL(url);
            toast.success("Downloaded signed document");
        } catch {
            toast.error("Failed to download document");
        }
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
            {requestsLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-16 w-full rounded-lg" />
                    ))}
                </div>
            ) : requests.length === 0 ? (
                <EmptyState
                    icon="&#x270D;&#xFE0F;"
                    title="No signature requests yet"
                    description="Upload a document in Files first, then send it here for e-signature."
                />
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
                                    {req.status === "signed" && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="text-xs h-7"
                                            onClick={() =>
                                                handleDownload(
                                                    req.local_id || req.signature_request_id,
                                                    req.title,
                                                )
                                            }
                                        >
                                            Download
                                        </Button>
                                    )}
                                    {["pending", "sent", "viewed"].includes(req.status) && canEdit && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="text-xs h-7"
                                            disabled={checkingStatusId === (req.local_id || req.signature_request_id)}
                                            onClick={() =>
                                                handleCheckStatus(req.local_id || req.signature_request_id)
                                            }
                                        >
                                            {checkingStatusId === (req.local_id || req.signature_request_id)
                                                ? "Checking..."
                                                : "Check Status"}
                                        </Button>
                                    )}
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
                                    <StatusBadge status={req.status} domain="esign" />
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
