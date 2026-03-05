// ---- Evidence Tab (CRUD + Analysis Results) ------------------------------
// Sub-tabs: Items | Consistency Check | Legal Elements | Entities
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import { api } from "@/lib/api-client";
import { usePrep } from "@/hooks/use-prep";
import { useRole } from "@/hooks/use-role";
import { usePrepState, type ConsistencyItem, type ElementItem, type EntityItem } from "@/hooks/use-prep-state";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { ResultSection } from "@/components/analysis/result-section";
import { DataPage } from "@/components/shared/data-page";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { DetailPanel, type DetailField } from "@/components/shared/detail-panel";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ModuleNotes } from "@/components/shared/module-notes";
import type { EvidenceItem } from "@/types/api";

// ---- Evidence CRUD schema -----------------------------------------------

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

// ---- Severity color helper -----------------------------------------------

function severityColor(severity?: string): string {
    switch (severity?.toLowerCase()) {
        case "high":
        case "critical":
        case "major":
            return "bg-red-500/15 text-red-400 border-red-500/30";
        case "medium":
        case "moderate":
            return "bg-amber-500/15 text-amber-400 border-amber-500/30";
        default:
            return "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";
    }
}

function entityTypeColor(type: string): string {
    switch (type?.toLowerCase()) {
        case "person": return "bg-blue-500/15 text-blue-400 border-blue-500/30";
        case "organization": return "bg-violet-500/15 text-violet-400 border-violet-500/30";
        case "location": return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
        case "date": return "bg-amber-500/15 text-amber-400 border-amber-500/30";
        default: return "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";
    }
}

function strengthColor(strength?: string): string {
    switch (strength?.toLowerCase()) {
        case "strong": return "text-emerald-400";
        case "moderate": return "text-yellow-400";
        case "weak": return "text-red-400";
        default: return "text-muted-foreground";
    }
}

// ---- Main Page ----------------------------------------------------------

export default function EvidencePage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, isLoading: prepLoading } = usePrep();
    const { canEdit, canDelete } = useRole();
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<EvidenceItem | null>(null);
    const [detailItem, setDetailItem] = useState<EvidenceItem | null>(null);

    // Analysis results
    const { sections, isLoading: stateLoading } = usePrepState(caseId, activePrepId);

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
        <Tabs defaultValue="items" className="space-y-4">
            <TabsList variant="line">
                <TabsTrigger value="items">
                    Items {query.data?.length ? <Badge variant="secondary" className="ml-1 text-[10px] py-0 px-1">{query.data.length}</Badge> : null}
                </TabsTrigger>
                <TabsTrigger value="consistency">
                    Consistency {sections.consistencyCheck.length > 0 && <Badge variant="secondary" className="ml-1 text-[10px] py-0 px-1">{sections.consistencyCheck.length}</Badge>}
                </TabsTrigger>
                <TabsTrigger value="elements">
                    Elements {sections.elementsMap.length > 0 && <Badge variant="secondary" className="ml-1 text-[10px] py-0 px-1">{sections.elementsMap.length}</Badge>}
                </TabsTrigger>
                <TabsTrigger value="entities">
                    Entities {sections.entities.length > 0 && <Badge variant="secondary" className="ml-1 text-[10px] py-0 px-1">{sections.entities.length}</Badge>}
                </TabsTrigger>
            </TabsList>

            {/* ---- Items Tab (existing CRUD) ---- */}
            <TabsContent value="items">
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
                                                <span aria-hidden="true">✕</span>
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
            </TabsContent>

            {/* ---- Consistency Check Tab ---- */}
            <TabsContent value="consistency" className="space-y-4">
                <ResultSection
                    title="Consistency Check"
                    icon="🔄"
                    isEmpty={sections.consistencyCheck.length === 0}
                    isLoading={stateLoading}
                    emptyMessage="Run analysis to cross-reference witness statements and evidence for contradictions."
                >
                    <div className="space-y-3">
                        {sections.consistencyCheck
                            .filter((item: ConsistencyItem) => !item._ai_suggests_remove)
                            .map((item: ConsistencyItem, i: number) => (
                            <Card key={i} className="bg-accent/20">
                                <CardContent className="py-3 space-y-2">
                                    <div className="flex items-start justify-between gap-2">
                                        <p className="text-sm font-medium">{item.fact}</p>
                                        {item.severity && (
                                            <Badge variant="outline" className={`text-xs shrink-0 ${severityColor(item.severity)}`}>
                                                {item.severity}
                                            </Badge>
                                        )}
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
                                        <div className="rounded-lg bg-muted/50 p-2.5">
                                            <p className="text-xs font-medium text-muted-foreground mb-1">{item.source_a}</p>
                                            <p className="text-sm">{item.statement_a}</p>
                                        </div>
                                        <div className="rounded-lg bg-muted/50 p-2.5">
                                            <p className="text-xs font-medium text-muted-foreground mb-1">{item.source_b}</p>
                                            <p className="text-sm">{item.statement_b}</p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </ResultSection>
                <ModuleNotes caseId={caseId} prepId={activePrepId} moduleKey="consistency_check" />
            </TabsContent>

            {/* ---- Legal Elements Tab ---- */}
            <TabsContent value="elements" className="space-y-4">
                <ResultSection
                    title="Legal Elements"
                    icon="📜"
                    isEmpty={sections.elementsMap.length === 0}
                    isLoading={stateLoading}
                    emptyMessage="Run analysis to map legal elements to supporting evidence."
                >
                    <div className="space-y-3">
                        {sections.elementsMap.map((el: ElementItem, i: number) => (
                            <Card key={i} className="bg-accent/20">
                                <CardContent className="py-3 space-y-2">
                                    <div className="flex items-start justify-between gap-2">
                                        <div>
                                            <p className="text-sm font-medium">{el.element}</p>
                                            {el.charge && (
                                                <p className="text-xs text-muted-foreground">{el.charge}</p>
                                            )}
                                        </div>
                                        {el.strength && (
                                            <span className={`text-xs font-semibold ${strengthColor(el.strength)}`}>
                                                {el.strength}
                                            </span>
                                        )}
                                    </div>
                                    {el.statute && (
                                        <p className="text-xs text-muted-foreground">Statute: {el.statute}</p>
                                    )}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-1">
                                        {el.evidence_for && el.evidence_for.length > 0 && (
                                            <div>
                                                <p className="text-xs font-medium text-emerald-400 mb-1">Evidence For</p>
                                                <ul className="space-y-1">
                                                    {el.evidence_for.map((ev, j) => (
                                                        <li key={j} className="text-xs text-muted-foreground">• {ev}</li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}
                                        {el.evidence_against && el.evidence_against.length > 0 && (
                                            <div>
                                                <p className="text-xs font-medium text-red-400 mb-1">Evidence Against</p>
                                                <ul className="space-y-1">
                                                    {el.evidence_against.map((ev, j) => (
                                                        <li key={j} className="text-xs text-muted-foreground">• {ev}</li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}
                                    </div>
                                    {el.notes && (
                                        <p className="text-xs text-muted-foreground mt-1">{el.notes}</p>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </ResultSection>
                <ModuleNotes caseId={caseId} prepId={activePrepId} moduleKey="elements_map" />
            </TabsContent>

            {/* ---- Entities Tab ---- */}
            <TabsContent value="entities" className="space-y-4">
                <ResultSection
                    title="Extracted Entities"
                    icon="🏷️"
                    isEmpty={sections.entities.length === 0}
                    isLoading={stateLoading}
                    emptyMessage="Run analysis to extract people, organizations, and locations from case documents."
                >
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {sections.entities.map((entity: EntityItem, i: number) => (
                            <Card key={i} className="bg-accent/20">
                                <CardContent className="py-3">
                                    <div className="flex items-center justify-between mb-1">
                                        <p className="text-sm font-medium">{entity.name}</p>
                                        <Badge variant="outline" className={`text-xs ${entityTypeColor(entity.type)}`}>
                                            {entity.type}
                                        </Badge>
                                    </div>
                                    {entity.role && (
                                        <p className="text-xs text-muted-foreground">{entity.role}</p>
                                    )}
                                    {entity.context && (
                                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{entity.context}</p>
                                    )}
                                    {entity.mentions !== undefined && (
                                        <p className="text-xs text-muted-foreground mt-1">
                                            {entity.mentions} mention{entity.mentions !== 1 ? "s" : ""}
                                        </p>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </ResultSection>
                <ModuleNotes caseId={caseId} prepId={activePrepId} moduleKey="entities" />
            </TabsContent>
        </Tabs>
    );
}
