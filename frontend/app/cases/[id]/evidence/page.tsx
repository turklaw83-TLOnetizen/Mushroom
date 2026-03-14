// ---- Evidence Tab (CRUD + Analysis Results) ------------------------------
// Sub-tabs: Items | Consistency Check | Legal Elements | Entities | Custody
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import { toast } from "sonner";
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
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
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
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { ModuleNotes } from "@/components/shared/module-notes";
import type { EvidenceItem } from "@/types/api";

// ---- Chain of Custody types & helpers ------------------------------------

interface CustodyEntry {
    id: string;
    evidence_id: string;
    action: string;
    from_party: string;
    to_party: string;
    date: string;
    location: string;
    notes: string;
    recorded_by: string;
    recorded_at: string;
}

const CUSTODY_ACTIONS = [
    "received",
    "transferred",
    "stored",
    "presented",
    "returned",
    "photographed",
    "analyzed",
];

function custodyActionIcon(action: string): string {
    switch (action) {
        case "received": return "IN";
        case "transferred": return "TX";
        case "stored": return "ST";
        case "presented": return "PR";
        case "returned": return "RT";
        case "photographed": return "PH";
        case "analyzed": return "AN";
        default: return "??";
    }
}

function custodyActionColor(action: string): string {
    switch (action) {
        case "received": return "bg-green-500/15 text-green-400 border-green-500/30";
        case "transferred": return "bg-blue-500/15 text-blue-400 border-blue-500/30";
        case "stored": return "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";
        case "presented": return "bg-violet-500/15 text-violet-400 border-violet-500/30";
        case "returned": return "bg-amber-500/15 text-amber-400 border-amber-500/30";
        case "photographed": return "bg-cyan-500/15 text-cyan-400 border-cyan-500/30";
        case "analyzed": return "bg-indigo-500/15 text-indigo-400 border-indigo-500/30";
        default: return "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";
    }
}

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
    const queryClient = useQueryClient();
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<EvidenceItem | null>(null);
    const [detailItem, setDetailItem] = useState<EvidenceItem | null>(null);

    // Chain of Custody state
    const [custodyDialogOpen, setCustodyDialogOpen] = useState(false);
    const [custodyEvidenceId, setCustodyEvidenceId] = useState("");
    const [custodyAction, setCustodyAction] = useState("received");
    const [custodyFromParty, setCustodyFromParty] = useState("");
    const [custodyToParty, setCustodyToParty] = useState("");
    const [custodyDate, setCustodyDate] = useState("");
    const [custodyLocation, setCustodyLocation] = useState("");
    const [custodyNotes, setCustodyNotes] = useState("");
    const [custodySubmitting, setCustodySubmitting] = useState(false);

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

    // ---- Chain of Custody queries ----------------------------------------

    const custodyQueryKey = ["evidence-custody", caseId];
    const custodyQuery = useQuery({
        queryKey: custodyQueryKey,
        queryFn: () =>
            api.get<{ items: CustodyEntry[] }>(
                `/cases/${caseId}/evidence/custody`,
                { getToken },
            ),
    });

    const custodyEntries = custodyQuery.data?.items ?? [];

    function resetCustodyForm() {
        setCustodyEvidenceId("");
        setCustodyAction("received");
        setCustodyFromParty("");
        setCustodyToParty("");
        setCustodyDate("");
        setCustodyLocation("");
        setCustodyNotes("");
    }

    async function handleAddCustody() {
        if (!custodyEvidenceId.trim() || !custodyAction) {
            toast.error("Evidence ID and action are required");
            return;
        }
        setCustodySubmitting(true);
        try {
            await api.post(
                `/cases/${caseId}/evidence/custody`,
                {
                    evidence_id: custodyEvidenceId.trim(),
                    action: custodyAction,
                    from_party: custodyFromParty.trim(),
                    to_party: custodyToParty.trim(),
                    date: custodyDate,
                    location: custodyLocation.trim(),
                    notes: custodyNotes.trim(),
                },
                { getToken },
            );
            toast.success("Custody entry added");
            queryClient.invalidateQueries({ queryKey: custodyQueryKey });
            setCustodyDialogOpen(false);
            resetCustodyForm();
        } catch {
            toast.error("Failed to add custody entry");
        } finally {
            setCustodySubmitting(false);
        }
    }

    async function handleDeleteCustody(entryId: string) {
        if (!window.confirm("Delete this custody entry? This action cannot be undone.")) return;
        try {
            await api.delete(`/cases/${caseId}/evidence/custody/${entryId}`, { getToken });
            toast.success("Custody entry deleted");
            queryClient.invalidateQueries({ queryKey: custodyQueryKey });
        } catch {
            toast.error("Failed to delete custody entry");
        }
    }

    // ---- Loading skeleton ----
    if (prepLoading || query.isLoading) {
        return (
            <div className="space-y-4 p-6">
                <div className="flex items-center justify-between">
                    <div>
                        <Skeleton className="h-7 w-36" />
                        <Skeleton className="h-4 w-56 mt-1" />
                    </div>
                    <Skeleton className="h-9 w-28" />
                </div>
                <div className="flex gap-2 mb-4">
                    {Array.from({ length: 5 }).map((_, i) => (
                        <Skeleton key={i} className="h-8 w-24" />
                    ))}
                </div>
                <Skeleton className="h-9 w-full max-w-sm" />
                <div className="grid grid-cols-1 gap-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Card key={i}>
                            <CardContent className="py-3">
                                <div className="flex items-center justify-between mb-1">
                                    <div className="flex items-center gap-2">
                                        <Skeleton className="h-5 w-5 rounded" />
                                        <Skeleton className="h-4 w-48" />
                                    </div>
                                    <Skeleton className="h-5 w-20 rounded-full" />
                                </div>
                                <Skeleton className="h-3 w-36 ml-7 mt-1" />
                                <div className="flex gap-1 ml-7 mt-2">
                                    <Skeleton className="h-4 w-12 rounded-full" />
                                    <Skeleton className="h-4 w-16 rounded-full" />
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        );
    }

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
                <TabsTrigger value="custody">
                    Custody {custodyEntries.length > 0 && <Badge variant="secondary" className="ml-1 text-[10px] py-0 px-1">{custodyEntries.length}</Badge>}
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

            {/* ---- Chain of Custody Tab ---- */}
            <TabsContent value="custody" className="space-y-4">
                <div className="flex items-center justify-between">
                    <div>
                        <h3 className="text-lg font-semibold">Chain of Custody</h3>
                        <p className="text-sm text-muted-foreground">
                            Track who handled evidence, when, and how.
                        </p>
                    </div>
                    {canEdit && (
                        <Button size="sm" onClick={() => setCustodyDialogOpen(true)}>
                            + Add Entry
                        </Button>
                    )}
                </div>

                {custodyQuery.isLoading ? (
                    <div className="space-y-3">
                        {Array.from({ length: 3 }).map((_, i) => (
                            <Skeleton key={i} className="h-20 w-full rounded-lg" />
                        ))}
                    </div>
                ) : custodyEntries.length === 0 ? (
                    <EmptyState
                        icon="&#x1F517;"
                        title="No custody entries recorded yet"
                        description="Track chain of custody by logging when evidence changes hands."
                    />
                ) : (
                    <div className="relative">
                        {/* Timeline line */}
                        <div className="absolute left-4 top-0 bottom-0 w-px bg-border" />

                        <div className="space-y-3">
                            {custodyEntries.map((entry) => (
                                <div key={entry.id} className="relative pl-10 group">
                                    {/* Timeline dot */}
                                    <div className="absolute left-2.5 top-3 w-3 h-3 rounded-full bg-muted-foreground/40 border-2 border-background" />

                                    <Card className="bg-accent/20 hover:bg-accent/30 transition-colors">
                                        <CardContent className="py-3">
                                            <div className="flex items-start justify-between gap-2">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <Badge
                                                        variant="outline"
                                                        className={`text-[10px] font-mono ${custodyActionColor(entry.action)}`}
                                                    >
                                                        {custodyActionIcon(entry.action)} {entry.action}
                                                    </Badge>
                                                    <span className="text-xs text-muted-foreground">
                                                        {entry.date}
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-2 shrink-0">
                                                    {entry.recorded_by && (
                                                        <span className="text-[10px] text-muted-foreground">
                                                            by {entry.recorded_by}
                                                        </span>
                                                    )}
                                                    {canDelete && (
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity text-destructive"
                                                            aria-label="Delete custody entry"
                                                            onClick={() => handleDeleteCustody(entry.id)}
                                                        >
                                                            <span aria-hidden="true">x</span>
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>

                                            {(entry.from_party || entry.to_party) && (
                                                <p className="text-sm mt-1">
                                                    {entry.from_party && (
                                                        <span className="text-muted-foreground">{entry.from_party}</span>
                                                    )}
                                                    {entry.from_party && entry.to_party && (
                                                        <span className="mx-1.5 text-muted-foreground/50">{"->"}</span>
                                                    )}
                                                    {entry.to_party && (
                                                        <span className="text-muted-foreground">{entry.to_party}</span>
                                                    )}
                                                </p>
                                            )}

                                            {entry.location && (
                                                <p className="text-xs text-muted-foreground mt-1">
                                                    Location: {entry.location}
                                                </p>
                                            )}
                                            {entry.notes && (
                                                <p className="text-xs text-muted-foreground mt-1">
                                                    {entry.notes}
                                                </p>
                                            )}
                                        </CardContent>
                                    </Card>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Add Custody Entry Dialog */}
                <Dialog
                    open={custodyDialogOpen}
                    onOpenChange={(open) => {
                        setCustodyDialogOpen(open);
                        if (!open) resetCustodyForm();
                    }}
                >
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Add Custody Entry</DialogTitle>
                            <DialogDescription>
                                Record a chain-of-custody event for an evidence item.
                            </DialogDescription>
                        </DialogHeader>

                        <div className="space-y-3 py-2">
                            <div className="space-y-1.5">
                                <label className="text-sm font-medium">
                                    Evidence ID <span className="text-destructive">*</span>
                                </label>
                                <Input
                                    placeholder="e.g. knife-001, photo-set-A"
                                    value={custodyEvidenceId}
                                    onChange={(e) => setCustodyEvidenceId(e.target.value)}
                                />
                            </div>
                            <div className="space-y-1.5">
                                <label className="text-sm font-medium">
                                    Action <span className="text-destructive">*</span>
                                </label>
                                <Select value={custodyAction} onValueChange={setCustodyAction}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {CUSTODY_ACTIONS.map((a) => (
                                            <SelectItem key={a} value={a}>
                                                {a.charAt(0).toUpperCase() + a.slice(1)}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div className="space-y-1.5">
                                    <label className="text-sm font-medium">From</label>
                                    <Input
                                        placeholder="Person or entity"
                                        value={custodyFromParty}
                                        onChange={(e) => setCustodyFromParty(e.target.value)}
                                    />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-sm font-medium">To</label>
                                    <Input
                                        placeholder="Person or entity"
                                        value={custodyToParty}
                                        onChange={(e) => setCustodyToParty(e.target.value)}
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div className="space-y-1.5">
                                    <label className="text-sm font-medium">Date</label>
                                    <Input
                                        type="date"
                                        value={custodyDate}
                                        onChange={(e) => setCustodyDate(e.target.value)}
                                    />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="text-sm font-medium">Location</label>
                                    <Input
                                        placeholder="e.g. Evidence room"
                                        value={custodyLocation}
                                        onChange={(e) => setCustodyLocation(e.target.value)}
                                    />
                                </div>
                            </div>
                            <div className="space-y-1.5">
                                <label className="text-sm font-medium">Notes</label>
                                <textarea
                                    className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:border-ring min-h-[60px] resize-y dark:bg-input/30"
                                    placeholder="Additional notes..."
                                    value={custodyNotes}
                                    onChange={(e) => setCustodyNotes(e.target.value)}
                                />
                            </div>
                        </div>

                        <DialogFooter>
                            <Button
                                variant="outline"
                                onClick={() => {
                                    setCustodyDialogOpen(false);
                                    resetCustodyForm();
                                }}
                            >
                                Cancel
                            </Button>
                            <Button
                                onClick={handleAddCustody}
                                disabled={custodySubmitting}
                            >
                                {custodySubmitting ? "Adding..." : "Add Entry"}
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </TabsContent>
        </Tabs>
    );
}
