// ---- E-Signature Tab ----------------------------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

interface FileItem {
    filename: string;
    size: number;
    tags: string[];
}

interface SignatureRequest {
    id: string;
    title: string;
    filename: string;
    signer_name: string;
    signer_email: string;
    status: string;
    created_at: string;
    signed_at?: string;
}

interface SendSignatureInput {
    filename: string;
    signer_name: string;
    signer_email: string;
    title: string;
    subject: string;
    message: string;
}

const statusColors: Record<string, string> = {
    pending: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    signed: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    declined: "bg-red-500/15 text-red-400 border-red-500/30",
};

function formatDate(ts: string): string {
    try {
        const d = new Date(ts);
        return d.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    } catch {
        return ts;
    }
}

const emptyForm: SendSignatureInput = {
    filename: "",
    signer_name: "",
    signer_email: "",
    title: "",
    subject: "",
    message: "",
};

export default function ESignPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { canEdit } = useRole();
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState<SendSignatureInput>({ ...emptyForm });

    // Load case files for the file selector
    const filesQuery = useQuery({
        queryKey: ["cases", caseId, "files"],
        queryFn: () => api.get<FileItem[]>(`/cases/${caseId}/files`, { getToken }),
    });

    // Load signature requests
    const requestsQuery = useQuery({
        queryKey: ["esign", "requests", caseId],
        queryFn: () =>
            api.get<SignatureRequest[]>(`/cases/${caseId}/esign/requests`, { getToken }),
    });

    const files = filesQuery.data ?? [];
    const requests = requestsQuery.data ?? [];

    // Send for signature
    const sendMutation = useMutationWithToast<SendSignatureInput>({
        mutationFn: (data) =>
            api.post(`/cases/${caseId}/esign/send`, data, { getToken }),
        successMessage: "Document sent for signature",
        invalidateKeys: [["esign", "requests", caseId]],
        onSuccess: () => {
            setShowForm(false);
            setForm({ ...emptyForm });
        },
    });

    // Check status of a request
    const checkStatus = useMutationWithToast<string>({
        mutationFn: (requestId) =>
            api.get(`/cases/${caseId}/esign/requests/${requestId}`, { getToken }),
        successMessage: "Status refreshed",
        invalidateKeys: [["esign", "requests", caseId]],
    });

    const handleSubmit = () => {
        if (!form.filename || !form.signer_name || !form.signer_email || !form.title) return;
        sendMutation.mutate(form);
    };

    return (
        <div className="space-y-5">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">E-Signature</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Send documents for electronic signature and track requests
                    </p>
                </div>
                {canEdit && !showForm && (
                    <Button size="sm" className="gap-1.5" onClick={() => setShowForm(true)}>
                        <span>+</span> Send for Signature
                    </Button>
                )}
            </div>

            {/* Send Document Form */}
            {showForm && canEdit && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Send Document for Signature</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div>
                            <label className="text-xs font-medium text-muted-foreground mb-1 block">
                                Document
                            </label>
                            {filesQuery.isLoading ? (
                                <Skeleton className="h-9 w-full" />
                            ) : (
                                <select
                                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={form.filename}
                                    onChange={(e) => setForm({ ...form, filename: e.target.value })}
                                >
                                    <option value="">Select a file...</option>
                                    {files.map((f) => (
                                        <option key={f.filename} value={f.filename}>
                                            {f.filename}
                                        </option>
                                    ))}
                                </select>
                            )}
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label className="text-xs font-medium text-muted-foreground mb-1 block">
                                    Signer Name
                                </label>
                                <Input
                                    placeholder="John Doe"
                                    value={form.signer_name}
                                    onChange={(e) => setForm({ ...form, signer_name: e.target.value })}
                                />
                            </div>
                            <div>
                                <label className="text-xs font-medium text-muted-foreground mb-1 block">
                                    Signer Email
                                </label>
                                <Input
                                    type="email"
                                    placeholder="john@example.com"
                                    value={form.signer_email}
                                    onChange={(e) => setForm({ ...form, signer_email: e.target.value })}
                                />
                            </div>
                        </div>
                        <div>
                            <label className="text-xs font-medium text-muted-foreground mb-1 block">
                                Title
                            </label>
                            <Input
                                placeholder="Document title for the signature request"
                                value={form.title}
                                onChange={(e) => setForm({ ...form, title: e.target.value })}
                            />
                        </div>
                        <div>
                            <label className="text-xs font-medium text-muted-foreground mb-1 block">
                                Subject (optional)
                            </label>
                            <Input
                                placeholder="Email subject line"
                                value={form.subject}
                                onChange={(e) => setForm({ ...form, subject: e.target.value })}
                            />
                        </div>
                        <div>
                            <label className="text-xs font-medium text-muted-foreground mb-1 block">
                                Message (optional)
                            </label>
                            <textarea
                                className="flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                placeholder="Message to include with the signature request..."
                                value={form.message}
                                onChange={(e) => setForm({ ...form, message: e.target.value })}
                            />
                        </div>
                        <div className="flex gap-2 justify-end">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                    setShowForm(false);
                                    setForm({ ...emptyForm });
                                }}
                            >
                                Cancel
                            </Button>
                            <Button
                                size="sm"
                                onClick={handleSubmit}
                                disabled={
                                    !form.filename ||
                                    !form.signer_name ||
                                    !form.signer_email ||
                                    !form.title ||
                                    sendMutation.isPending
                                }
                            >
                                {sendMutation.isPending ? "Sending..." : "Send for Signature"}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Signature Requests List */}
            {requestsQuery.isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 3 }).map((_, i) => (
                        <Skeleton key={i} className="h-20 w-full rounded-lg" />
                    ))}
                </div>
            ) : requests.length === 0 ? (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        No signature requests yet. Send a document for signature to get started.
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-3">
                    {requests.map((req, i) => (
                        <Card key={req.id || i} className="hover:bg-accent/20 transition-colors">
                            <CardContent className="py-4">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="flex-1 space-y-1">
                                        <div className="flex items-center gap-2">
                                            <p className="text-sm font-medium">{req.title}</p>
                                            <Badge
                                                variant="outline"
                                                className={statusColors[req.status] || ""}
                                            >
                                                {req.status}
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-muted-foreground">
                                            {req.signer_name} ({req.signer_email})
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                            {req.filename} &middot; Sent {formatDate(req.created_at)}
                                            {req.signed_at && ` &middot; Signed ${formatDate(req.signed_at)}`}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => checkStatus.mutate(req.id)}
                                            disabled={checkStatus.isPending}
                                        >
                                            Check Status
                                        </Button>
                                        {req.status === "signed" && (
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() =>
                                                    window.open(
                                                        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/cases/${caseId}/esign/download/${req.id}`,
                                                        "_blank",
                                                    )
                                                }
                                            >
                                                Download
                                            </Button>
                                        )}
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
