// ---- Evidence Tab (with detail panel) -----------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import { api } from "@/lib/api-client";
import { usePrep } from "@/hooks/use-prep";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { DataPage } from "@/components/shared/data-page";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { DetailPanel, type DetailField } from "@/components/shared/detail-panel";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { EvidenceItem } from "@/types/api";

const evidenceSchema = z.object({
    description: z.string().min(1, "Description is required").max(2000),
    type: z.string().max(100).optional().default(""),
    source: z.string().max(500).optional().default(""),
    foundation: z.string().max(2000).optional().default(""),
});
type EvidenceInput = z.infer<typeof evidenceSchema>;

const createFields: FieldConfig<EvidenceInput>[] = [
    { name: "description", label: "Description", required: true, type: "textarea", placeholder: "Describe the evidence item" },
    { name: "type", label: "Type", placeholder: "e.g. Physical, Documentary, Testimonial" },
    { name: "source", label: "Source", placeholder: "e.g. Discovery packet" },
    { name: "foundation", label: "Foundation", type: "textarea", placeholder: "Foundation for admissibility" },
];

const detailFields: DetailField<EvidenceInput>[] = [
    { name: "description", label: "Description", type: "textarea" },
    { name: "type", label: "Type" },
    { name: "source", label: "Source" },
    { name: "foundation", label: "Foundation", type: "textarea" },
];

export default function EvidencePage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, isLoading: prepLoading } = usePrep();
    const { canEdit, canDelete } = useRole();
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<EvidenceItem | null>(null);
    const [detailItem, setDetailItem] = useState<EvidenceItem | null>(null);

    const queryKey = ["evidence", caseId, activePrepId];
    const basePath = `/cases/${caseId}/preparations/${activePrepId}/evidence`;

    const query = useQuery({
        queryKey,
        queryFn: () => api.get<EvidenceItem[]>(basePath, { getToken }),
        enabled: !!activePrepId,
    });

    const createMutation = useMutationWithToast<EvidenceInput>({
        mutationFn: (data) => api.post(basePath, data, { getToken }),
        successMessage: "Evidence added",
        invalidateKeys: [queryKey],
        onSuccess: () => setDialogOpen(false),
    });

    const deleteMutation = useMutationWithToast<string>({
        mutationFn: (id) => api.delete(`${basePath}/${id}`, { getToken }),
        successMessage: "Evidence removed",
        invalidateKeys: [queryKey],
        onSuccess: () => setDeleteTarget(null),
    });

    const updateMutation = useMutationWithToast<EvidenceInput>({
        mutationFn: (data) => api.put(`${basePath}/${detailItem?.id}`, data, { getToken }),
        successMessage: "Evidence updated",
        invalidateKeys: [queryKey],
        onSuccess: () => setDetailItem(null),
    });

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">Create a preparation first to manage evidence.</p>
            </div>
        );
    }

    return (
        <DataPage
            title="Evidence"
            subtitle="Evidence items, foundations, and admissibility"
            query={query}
            searchFilter={(e, s) =>
                e.description.toLowerCase().includes(s) || e.source.toLowerCase().includes(s)
            }
            searchPlaceholder="Search evidence..."
            createLabel={canEdit ? "Add Evidence" : null}
            onCreateClick={() => setDialogOpen(true)}
            renderItem={(item, i) => (
                <Card
                    key={item.id || i}
                    className="hover:bg-accent/30 transition-colors group cursor-pointer"
                    onClick={() => setDetailItem(item)}
                >
                    <CardContent className="py-3">
                        <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-2">
                                <span aria-hidden="true">🔍</span>
                                <p className="font-medium text-sm">{item.description}</p>
                            </div>
                            <div className="flex items-center gap-2">
                                {item.type && (
                                    <Badge variant="outline" className="text-xs">{item.type}</Badge>
                                )}
                                {canDelete && (
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive"
                                        aria-label={`Delete ${item.description}`}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setDeleteTarget(item);
                                        }}
                                    >
                                        ✕
                                    </Button>
                                )}
                            </div>
                        </div>
                        {item.source && (
                            <p className="text-xs text-muted-foreground ml-7">Source: {item.source}</p>
                        )}
                        {item.tags?.length > 0 && (
                            <div className="flex gap-1 ml-7 mt-1">
                                {item.tags.map((tag) => (
                                    <Badge key={tag} variant="secondary" className="text-[10px]">{tag}</Badge>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}
        >
            {canEdit && (
                <FormDialog
                    open={dialogOpen}
                    onOpenChange={setDialogOpen}
                    title="Add Evidence"
                    description="Add an evidence item to this preparation."
                    schema={evidenceSchema}
                    defaultValues={{ description: "", type: "", source: "", foundation: "" }}
                    fields={createFields}
                    onSubmit={async (data) => { await createMutation.mutateAsync(data); }}
                    submitLabel="Add Evidence"
                    isLoading={createMutation.isPending}
                />
            )}
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
                title="Remove Evidence"
                description={`Remove "${deleteTarget?.description?.slice(0, 60)}"?`}
                confirmLabel="Remove"
                onConfirm={() => { if (deleteTarget) deleteMutation.mutate(deleteTarget.id); }}
                isLoading={deleteMutation.isPending}
            />
            {detailItem && (
                <DetailPanel
                    open={!!detailItem}
                    onOpenChange={(open) => !open && setDetailItem(null)}
                    title="Evidence Details"
                    description={detailItem.description.slice(0, 100)}
                    schema={evidenceSchema}
                    values={detailItem as EvidenceInput}
                    fields={detailFields}
                    onSave={async (data) => { await updateMutation.mutateAsync(data); }}
                    readOnly={!canEdit}
                    isLoading={updateMutation.isPending}
                    onDelete={canDelete ? () => {
                        setDeleteTarget(detailItem);
                        setDetailItem(null);
                    } : undefined}
                />
            )}
        </DataPage>
    );
}
