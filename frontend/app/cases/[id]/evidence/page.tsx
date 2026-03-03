// ---- Evidence Tab (with detail panel + Evidence Intelligence) ---------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api-client";
import type { EvidenceItem } from "@/types/api";
import { usePrep } from "@/hooks/use-prep";
import { useRole } from "@/hooks/use-role";
import { DataPage } from "@/components/shared/data-page";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { DetailPanel, type DetailField } from "@/components/shared/detail-panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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

/** Shape returned by on-demand generation endpoints. */
interface OnDemandResult {
    result?: string;
    content?: string;
    [key: string]: unknown;
}

/** Extract readable text from an on-demand result object. */
function extractResultText(data: OnDemandResult): string {
    return data.result ?? data.content ?? JSON.stringify(data, null, 2);
}

/** Spinner SVG used in generate buttons. */
function Spinner() {
    return (
        <svg
            className="animate-spin h-3 w-3 mr-1.5"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
        >
            <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
            />
            <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
        </svg>
    );
}

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
    const [isCreating, setIsCreating] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    // ---- Evidence Intelligence state ----------------------------------------
    const [intelResults, setIntelResults] = useState<Record<string, string>>({});
    const [expandedIntel, setExpandedIntel] = useState<Record<string, boolean>>({});
    const [conflictPartyName, setConflictPartyName] = useState("");

    const query = useQuery({
        queryKey: ["evidence", caseId, activePrepId],
        queryFn: () =>
            api.get<EvidenceItem[]>(
                `/cases/${caseId}/preparations/${activePrepId}/evidence`,
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    // ---- Cross-Reference mutation -------------------------------------------
    const crossRefMutation = useMutation({
        mutationFn: () =>
            api.post<OnDemandResult>(
                `/cases/${caseId}/ondemand/cross-references`,
                { prep_id: activePrepId },
                { getToken, noRetry: true },
            ),
        onSuccess: (data) => {
            const text = extractResultText(data);
            setIntelResults((prev) => ({ ...prev, "cross-references": text }));
            setExpandedIntel((prev) => ({ ...prev, "cross-references": true }));
            toast.success("Cross-reference matrix generated");
        },
        onError: (err: Error) => {
            toast.error("Failed to generate cross-references", { description: err.message });
        },
    });

    // ---- Missing Discovery mutation -----------------------------------------
    const missingDiscoveryMutation = useMutation({
        mutationFn: () =>
            api.post<OnDemandResult>(
                `/cases/${caseId}/ondemand/missing-discovery`,
                { prep_id: activePrepId },
                { getToken, noRetry: true },
            ),
        onSuccess: (data) => {
            const text = extractResultText(data);
            setIntelResults((prev) => ({ ...prev, "missing-discovery": text }));
            setExpandedIntel((prev) => ({ ...prev, "missing-discovery": true }));
            toast.success("Missing discovery analysis generated");
        },
        onError: (err: Error) => {
            toast.error("Failed to analyze missing discovery", { description: err.message });
        },
    });

    // ---- Conflict Scan mutation ---------------------------------------------
    const conflictScanMutation = useMutation({
        mutationFn: (partyName: string) =>
            api.post<OnDemandResult>(
                `/cases/${caseId}/ondemand/conflict-scan`,
                { prep_id: activePrepId, party_name: partyName },
                { getToken, noRetry: true },
            ),
        onSuccess: (data) => {
            const text = extractResultText(data);
            setIntelResults((prev) => ({ ...prev, "conflict-scan": text }));
            setExpandedIntel((prev) => ({ ...prev, "conflict-scan": true }));
            toast.success("Conflict scan complete");
        },
        onError: (err: Error) => {
            toast.error("Failed to scan for conflicts", { description: err.message });
        },
    });

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">Create a preparation first to manage evidence.</p>
            </div>
        );
    }

    const invalidate = () => queryClient.invalidateQueries({ queryKey: ["evidence", caseId, activePrepId] });

    const handleCreate = async (data: EvidenceInput) => {
        setIsCreating(true);
        try {
            await api.post(`/cases/${caseId}/preparations/${activePrepId}/evidence`, data, { getToken });
            toast.success("Evidence added");
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
            await api.delete(`/cases/${caseId}/preparations/${activePrepId}/evidence/${deleteTarget.id}`, { getToken });
            toast.success("Evidence removed");
            invalidate();
        } catch (err) {
            toast.error("Failed", { description: err instanceof Error ? err.message : "Unknown error" });
        } finally {
            setIsDeleting(false);
            setDeleteTarget(null);
        }
    };

    const handleUpdate = async (data: EvidenceInput) => {
        if (!detailItem) return;
        setIsSaving(true);
        try {
            await api.put(
                `/cases/${caseId}/preparations/${activePrepId}/evidence/${detailItem.id}`,
                data,
                { getToken },
            );
            toast.success("Evidence updated");
            setDetailItem(null);
            invalidate();
        } catch (err) {
            toast.error("Failed", { description: err instanceof Error ? err.message : "Unknown error" });
        } finally {
            setIsSaving(false);
        }
    };

    const handleConflictScan = () => {
        const name = conflictPartyName.trim();
        if (!name) {
            toast.error("Please enter a party name");
            return;
        }
        conflictScanMutation.mutate(name);
    };

    /** Render an expandable result card for an intelligence tool. */
    const renderIntelResult = (key: string) => {
        const result = intelResults[key];
        if (!result) return null;
        const isExpanded = expandedIntel[key] ?? false;

        return (
            <Card className="border-primary/20">
                <CardHeader className="pb-0 pt-3 px-4">
                    <button
                        type="button"
                        className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors w-full text-left"
                        onClick={() =>
                            setExpandedIntel((prev) => ({
                                ...prev,
                                [key]: !prev[key],
                            }))
                        }
                    >
                        <span
                            className={`transition-transform ${
                                isExpanded ? "rotate-90" : ""
                            }`}
                        >
                            {"\u25B6"}
                        </span>
                        {isExpanded ? "Collapse" : "Expand"} result
                        <Badge variant="outline" className="ml-auto text-[10px]">
                            AI Generated
                        </Badge>
                    </button>
                </CardHeader>
                {isExpanded && (
                    <CardContent className="pt-3 px-4 pb-4">
                        <div className="prose prose-sm dark:prose-invert max-w-none">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {result}
                            </ReactMarkdown>
                        </div>
                    </CardContent>
                )}
            </Card>
        );
    };

    return (
        <div className="space-y-8">
            {/* ---- Evidence List ------------------------------------------------- */}
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
                        onSubmit={handleCreate}
                        submitLabel="Add Evidence"
                        isLoading={isCreating}
                    />
                )}
                <ConfirmDialog
                    open={!!deleteTarget}
                    onOpenChange={(open) => !open && setDeleteTarget(null)}
                    title="Remove Evidence"
                    description={`Remove "${deleteTarget?.description?.slice(0, 60)}"?`}
                    confirmLabel="Remove"
                    onConfirm={handleDelete}
                    isLoading={isDeleting}
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
                        onSave={handleUpdate}
                        readOnly={!canEdit}
                        isLoading={isSaving}
                        onDelete={canDelete ? () => {
                            setDeleteTarget(detailItem);
                            setDetailItem(null);
                        } : undefined}
                    />
                )}
            </DataPage>

            {/* ---- Evidence Intelligence ----------------------------------------- */}
            {activePrepId && (
                <div className="border-t border-border pt-6 space-y-4">
                    <div>
                        <h3 className="text-lg font-semibold tracking-tight">Evidence Intelligence</h3>
                        <p className="text-sm text-muted-foreground mt-0.5">
                            AI-powered evidence analysis, cross-referencing, and conflict detection.
                        </p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* -- Cross-Reference Matrix -- */}
                        <div className="space-y-2">
                            <Card>
                                <CardHeader className="pb-3">
                                    <div className="flex items-center justify-between gap-2">
                                        <div className="min-w-0">
                                            <CardTitle className="text-sm font-medium">
                                                Cross-Reference Matrix
                                            </CardTitle>
                                            <p className="text-xs text-muted-foreground mt-0.5">
                                                Map how each piece of evidence relates to witnesses, other evidence, and legal elements.
                                            </p>
                                        </div>
                                        <Button
                                            size="sm"
                                            variant={intelResults["cross-references"] ? "outline" : "default"}
                                            disabled={crossRefMutation.isPending}
                                            onClick={() => crossRefMutation.mutate()}
                                            className="shrink-0"
                                        >
                                            {crossRefMutation.isPending ? (
                                                <>
                                                    <Spinner />
                                                    Generating...
                                                </>
                                            ) : intelResults["cross-references"] ? (
                                                "Regenerate"
                                            ) : (
                                                "Generate"
                                            )}
                                        </Button>
                                    </div>
                                </CardHeader>
                            </Card>
                            {renderIntelResult("cross-references")}
                        </div>

                        {/* -- Missing Discovery Analysis -- */}
                        <div className="space-y-2">
                            <Card>
                                <CardHeader className="pb-3">
                                    <div className="flex items-center justify-between gap-2">
                                        <div className="min-w-0">
                                            <CardTitle className="text-sm font-medium">
                                                Missing Discovery Analysis
                                            </CardTitle>
                                            <p className="text-xs text-muted-foreground mt-0.5">
                                                Identify gaps in evidence, missing statements, and discovery violations.
                                            </p>
                                        </div>
                                        <Button
                                            size="sm"
                                            variant={intelResults["missing-discovery"] ? "outline" : "default"}
                                            disabled={missingDiscoveryMutation.isPending}
                                            onClick={() => missingDiscoveryMutation.mutate()}
                                            className="shrink-0"
                                        >
                                            {missingDiscoveryMutation.isPending ? (
                                                <>
                                                    <Spinner />
                                                    Generating...
                                                </>
                                            ) : intelResults["missing-discovery"] ? (
                                                "Regenerate"
                                            ) : (
                                                "Generate"
                                            )}
                                        </Button>
                                    </div>
                                </CardHeader>
                            </Card>
                            {renderIntelResult("missing-discovery")}
                        </div>
                    </div>

                    {/* -- Conflict Scanner (full width) -- */}
                    <div className="space-y-2">
                        <Card>
                            <CardHeader className="pb-3">
                                <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                                    <div className="min-w-0">
                                        <CardTitle className="text-sm font-medium">
                                            Conflict Scanner
                                        </CardTitle>
                                        <p className="text-xs text-muted-foreground mt-0.5">
                                            Check a party name for potential conflicts of interest, ethical issues, and disqualification risks.
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        <Input
                                            placeholder="Party name..."
                                            value={conflictPartyName}
                                            onChange={(e) => setConflictPartyName(e.target.value)}
                                            onKeyDown={(e) => {
                                                if (e.key === "Enter") handleConflictScan();
                                            }}
                                            className="w-56"
                                        />
                                        <Button
                                            size="sm"
                                            variant={intelResults["conflict-scan"] ? "outline" : "default"}
                                            disabled={conflictScanMutation.isPending}
                                            onClick={handleConflictScan}
                                        >
                                            {conflictScanMutation.isPending ? (
                                                <>
                                                    <Spinner />
                                                    Scanning...
                                                </>
                                            ) : intelResults["conflict-scan"] ? (
                                                "Re-scan"
                                            ) : (
                                                "Scan"
                                            )}
                                        </Button>
                                    </div>
                                </div>
                            </CardHeader>
                        </Card>
                        {renderIntelResult("conflict-scan")}
                    </div>
                </div>
            )}
        </div>
    );
}
