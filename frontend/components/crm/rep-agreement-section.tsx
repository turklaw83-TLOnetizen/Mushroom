// ---- Rep Agreement Section -----------------------------------------------
// Upload, download, replace, delete a client's representation agreement.
"use client";

import { useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { RepAgreement } from "@/types/api";

interface RepAgreementSectionProps {
    clientId: string;
    agreement: RepAgreement | null | undefined;
}

function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function RepAgreementSection({ clientId, agreement }: RepAgreementSectionProps) {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const fileRef = useRef<HTMLInputElement>(null);
    const [uploading, setUploading] = useState(false);
    const [deleteOpen, setDeleteOpen] = useState(false);
    const [deleting, setDeleting] = useState(false);

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setUploading(true);
        try {
            const token = await getToken();
            const formData = new FormData();
            formData.append("file", file);

            const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const csrfMatch = document.cookie.match(/(?:^|;\s*)mc-csrf=([^;]*)/);
            const csrfToken = csrfMatch ? decodeURIComponent(csrfMatch[1]) : "";
            const headers: Record<string, string> = {};
            if (token) headers["Authorization"] = `Bearer ${token}`;
            if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
            const res = await fetch(`${apiUrl}/api/v1/crm/clients/${clientId}/rep-agreement`, {
                method: "POST",
                headers,
                credentials: "include",
                body: formData,
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => null);
                throw new Error(errData?.detail || `Upload failed (${res.status})`);
            }

            toast.success("Rep agreement uploaded");
            queryClient.invalidateQueries({ queryKey: ["crm-clients"] });
        } catch (err) {
            toast.error("Upload failed", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        } finally {
            setUploading(false);
            // Reset file input so same file can be re-selected
            if (fileRef.current) fileRef.current.value = "";
        }
    };

    const handleDownload = async () => {
        try {
            const token = await getToken();
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const res = await fetch(`${apiUrl}/api/v1/crm/clients/${clientId}/rep-agreement`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
            if (!res.ok) throw new Error("Download failed");

            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = agreement?.filename || "rep_agreement";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (err) {
            toast.error("Download failed");
        }
    };

    const handleDelete = async () => {
        setDeleting(true);
        try {
            await api.delete(`/crm/clients/${clientId}/rep-agreement`, { getToken });
            toast.success("Rep agreement deleted");
            queryClient.invalidateQueries({ queryKey: ["crm-clients"] });
            setDeleteOpen(false);
        } catch {
            toast.error("Delete failed");
        } finally {
            setDeleting(false);
        }
    };

    return (
        <div className="border-t pt-3 mt-3">
            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-2">
                Rep Agreement
            </p>

            {agreement ? (
                <div className="space-y-2">
                    <div className="flex items-center gap-2 flex-wrap">
                        <Badge variant="outline" className="text-[10px] font-mono">
                            {agreement.filename}
                        </Badge>
                        <span className="text-[10px] text-muted-foreground">
                            {formatBytes(agreement.size_bytes)}
                        </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-6 text-[10px] px-2"
                            onClick={handleDownload}
                        >
                            Download
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-6 text-[10px] px-2"
                            onClick={() => fileRef.current?.click()}
                            disabled={uploading}
                        >
                            {uploading ? "Uploading..." : "Replace"}
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 text-[10px] px-2 text-destructive hover:text-destructive"
                            onClick={() => setDeleteOpen(true)}
                        >
                            Delete
                        </Button>
                    </div>
                </div>
            ) : (
                <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs gap-1.5"
                    onClick={() => fileRef.current?.click()}
                    disabled={uploading}
                >
                    {uploading ? "Uploading..." : "Upload Agreement"}
                </Button>
            )}

            {/* Hidden file input */}
            <input
                type="file"
                ref={fileRef}
                onChange={handleUpload}
                accept=".pdf,.docx,.doc,.txt,.rtf"
                className="hidden"
            />

            <ConfirmDialog
                open={deleteOpen}
                onOpenChange={setDeleteOpen}
                title="Delete Rep Agreement"
                description="This will permanently delete the uploaded representation agreement."
                onConfirm={handleDelete}
                isLoading={deleting}
            />
        </div>
    );
}
