// ---- Documents Tab (with detail panel) ----------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { DataPage } from "@/components/shared/data-page";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { DetailPanel, type DetailField } from "@/components/shared/detail-panel";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Draft {
    id: string;
    title: string;
    type: string;
    content: string;
    created_at: string;
    last_updated: string;
}

const draftSchema = z.object({
    title: z.string().min(1, "Title required").max(500),
    type: z.string().min(1),
    content: z.string().optional().default(""),
});
type DraftInput = z.infer<typeof draftSchema>;

const createFields: FieldConfig<DraftInput>[] = [
    { name: "title", label: "Document Title", required: true, placeholder: "e.g. Motion to Suppress" },
    {
        name: "type", label: "Type", type: "select", required: true, options: [
            { value: "brief", label: "Brief" },
            { value: "motion", label: "Motion" },
            { value: "memo", label: "Memorandum" },
            { value: "letter", label: "Letter" },
            { value: "outline", label: "Outline" },
            { value: "other", label: "Other" },
        ],
    },
    { name: "content", label: "Initial Content", type: "textarea", placeholder: "Start writing..." },
];

const detailFields: DetailField<DraftInput>[] = [
    { name: "title", label: "Title" },
    {
        name: "type", label: "Type", type: "select", options: [
            { value: "brief", label: "Brief" },
            { value: "motion", label: "Motion" },
            { value: "memo", label: "Memorandum" },
            { value: "letter", label: "Letter" },
            { value: "outline", label: "Outline" },
            { value: "other", label: "Other" },
        ],
    },
    { name: "content", label: "Content", type: "textarea" },
];

export default function DocumentsPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { canEdit, canDelete } = useRole();
    const queryClient = useQueryClient();
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<Draft | null>(null);
    const [detailDraft, setDetailDraft] = useState<Draft | null>(null);
    const [isCreating, setIsCreating] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    const query = useQuery({
        queryKey: ["documents", caseId],
        queryFn: () => api.get<Draft[]>(`/documents/drafts/${caseId}`, { getToken }),
    });

    const invalidate = () => queryClient.invalidateQueries({ queryKey: ["documents", caseId] });

    const handleCreate = async (data: DraftInput) => {
        setIsCreating(true);
        try {
            await api.post(`/documents/drafts/${caseId}`, data, { getToken });
            toast.success("Draft created");
            setDialogOpen(false);
            invalidate();
        } catch (err) {
            toast.error("Failed", { description: err instanceof Error ? err.message : "Unknown error" });
        } finally {
            setIsCreating(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setIsDeleting(true);
        try {
            await api.delete(`/documents/drafts/${caseId}/${deleteTarget.id}`, { getToken });
            toast.success("Draft deleted");
            invalidate();
        } catch (err) {
            toast.error("Failed", { description: err instanceof Error ? err.message : "Unknown error" });
        } finally {
            setIsDeleting(false);
            setDeleteTarget(null);
        }
    };

    const handleUpdate = async (data: DraftInput) => {
        if (!detailDraft) return;
        setIsSaving(true);
        try {
            await api.put(
                `/documents/drafts/${caseId}/${detailDraft.id}`,
                data,
                { getToken },
            );
            toast.success("Draft updated");
            setDetailDraft(null);
            invalidate();
        } catch (err) {
            toast.error("Failed", { description: err instanceof Error ? err.message : "Unknown error" });
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <DataPage
            title="Documents"
            subtitle="Major document drafts — briefs, motions, and outlines"
            query={query}
            searchFilter={(d, s) => d.title.toLowerCase().includes(s)}
            searchPlaceholder="Search documents..."
            createLabel={canEdit ? "New Draft" : null}
            onCreateClick={() => setDialogOpen(true)}
            renderItem={(draft, i) => (
                <Card
                    key={draft.id || i}
                    className="hover:bg-accent/30 transition-colors cursor-pointer group"
                    onClick={() => setDetailDraft(draft)}
                >
                    <CardContent className="flex items-center justify-between py-3">
                        <div className="flex items-center gap-3">
                            <span aria-hidden="true">📝</span>
                            <div>
                                <p className="font-medium text-sm">{draft.title}</p>
                                <p className="text-xs text-muted-foreground">
                                    {draft.content ? `${draft.content.length} chars` : "Empty"}
                                    {draft.last_updated && ` · Updated ${draft.last_updated}`}
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <Badge variant="secondary" className="text-xs">{draft.type || "brief"}</Badge>
                            {canDelete && (
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive"
                                    aria-label={`Delete ${draft.title}`}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setDeleteTarget(draft);
                                    }}
                                >
                                    ✕
                                </Button>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}
        >
            {canEdit && (
                <FormDialog
                    open={dialogOpen}
                    onOpenChange={setDialogOpen}
                    title="New Draft"
                    description="Create a new document draft."
                    schema={draftSchema}
                    defaultValues={{ title: "", type: "brief", content: "" }}
                    fields={createFields}
                    onSubmit={handleCreate}
                    submitLabel="Create Draft"
                    isLoading={isCreating}
                />
            )}
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
                title="Delete Draft"
                description={`Delete "${deleteTarget?.title}"? This cannot be undone.`}
                onConfirm={handleDelete}
                isLoading={isDeleting}
            />
            {detailDraft && (
                <DetailPanel
                    open={!!detailDraft}
                    onOpenChange={(open) => !open && setDetailDraft(null)}
                    title={detailDraft.title}
                    description="View and edit document draft"
                    schema={draftSchema}
                    values={detailDraft as DraftInput}
                    fields={detailFields}
                    onSave={handleUpdate}
                    readOnly={!canEdit}
                    isLoading={isSaving}
                    onDelete={canDelete ? () => {
                        setDeleteTarget(detailDraft);
                        setDetailDraft(null);
                    } : undefined}
                />
            )}
        </DataPage>
    );
}
