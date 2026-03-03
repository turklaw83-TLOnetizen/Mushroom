// ---- Version History / Snapshots Tab ------------------------------------
"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { usePrep } from "@/hooks/use-prep";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";

// ---- Types --------------------------------------------------------------

interface Snapshot {
    id: string;
    label: string;
    created_at: string;
    created_by?: string;
    size_bytes?: number;
}

// Snapshot state as returned by the API (key analysis modules)
interface SnapshotState {
    case_summary?: string;
    strategy_notes?: string;
    witnesses?: unknown[];
    cross_exam_plan?: string;
    direct_exam_plan?: string;
    timeline?: unknown[];
    evidence_foundations?: string;
    investigation_plan?: string;
    consistency_check?: string;
    devils_advocate?: string;
    legal_research?: string;
    voir_dire?: string;
    mock_jury?: string;
    [key: string]: unknown;
}

type DiffStatus = "unchanged" | "changed" | "added" | "removed";

interface ModuleDiff {
    module: string;
    label: string;
    status: DiffStatus;
    valueA?: string;
    valueB?: string;
}

// ---- Diff Modules -------------------------------------------------------

const DIFF_MODULES: { key: string; label: string; isArray?: boolean }[] = [
    { key: "case_summary", label: "Case Summary" },
    { key: "strategy_notes", label: "Strategy Notes" },
    { key: "witnesses", label: "Witnesses", isArray: true },
    { key: "cross_exam_plan", label: "Cross Exam Plan" },
    { key: "direct_exam_plan", label: "Direct Exam Plan" },
    { key: "timeline", label: "Timeline", isArray: true },
    { key: "evidence_foundations", label: "Evidence Foundations" },
    { key: "investigation_plan", label: "Investigation Plan" },
    { key: "consistency_check", label: "Consistency Check" },
    { key: "devils_advocate", label: "Devil's Advocate" },
    { key: "legal_research", label: "Legal Research" },
    { key: "voir_dire", label: "Voir Dire" },
    { key: "mock_jury", label: "Mock Jury" },
];

function getModuleContent(state: SnapshotState, key: string, isArray?: boolean): string | null {
    const val = state[key];
    if (val === undefined || val === null) return null;
    if (isArray && Array.isArray(val)) {
        return val.length > 0 ? `${val.length} item${val.length !== 1 ? "s" : ""}` : null;
    }
    if (typeof val === "string") return val.length > 0 ? val : null;
    if (typeof val === "object") {
        const str = JSON.stringify(val);
        return str.length > 2 ? str : null; // "{}" or "[]" = empty
    }
    return String(val);
}

function computeDiffs(stateA: SnapshotState, stateB: SnapshotState): ModuleDiff[] {
    return DIFF_MODULES.map(({ key, label, isArray }) => {
        const a = getModuleContent(stateA, key, isArray);
        const b = getModuleContent(stateB, key, isArray);

        let status: DiffStatus;
        if (a === b) {
            status = "unchanged";
        } else if (a && !b) {
            status = "removed";
        } else if (!a && b) {
            status = "added";
        } else {
            status = "changed";
        }

        return {
            module: key,
            label,
            status,
            valueA: a ?? undefined,
            valueB: b ?? undefined,
        };
    });
}

function truncate(text: string | undefined, maxLen: number): string {
    if (!text) return "(empty)";
    return text.length > maxLen ? text.slice(0, maxLen) + "..." : text;
}

// ---- SnapshotDiffView Component -----------------------------------------

function SnapshotDiffView({
    open,
    onOpenChange,
    diffs,
    labelA,
    labelB,
    isLoading,
    error,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    diffs: ModuleDiff[];
    labelA: string;
    labelB: string;
    isLoading: boolean;
    error?: string | null;
}) {
    const statusBadge = (status: DiffStatus) => {
        switch (status) {
            case "changed":
                return (
                    <Badge variant="outline" className="text-[10px] text-amber-400 border-amber-500/30">
                        Changed
                    </Badge>
                );
            case "added":
                return (
                    <Badge variant="outline" className="text-[10px] text-green-400 border-green-500/30">
                        Added
                    </Badge>
                );
            case "removed":
                return (
                    <Badge variant="outline" className="text-[10px] text-red-400 border-red-500/30">
                        Removed
                    </Badge>
                );
            case "unchanged":
                return (
                    <Badge variant="outline" className="text-[10px] text-muted-foreground border-border">
                        Unchanged
                    </Badge>
                );
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-5xl max-h-[85vh] flex flex-col">
                <DialogHeader>
                    <DialogTitle>Snapshot Comparison</DialogTitle>
                    <DialogDescription>
                        Comparing &ldquo;{labelA}&rdquo; vs &ldquo;{labelB}&rdquo;
                    </DialogDescription>
                </DialogHeader>

                {isLoading ? (
                    <div className="space-y-3 py-4">
                        {Array.from({ length: 6 }).map((_, i) => (
                            <Skeleton key={i} className="h-12 w-full rounded-lg" />
                        ))}
                    </div>
                ) : error ? (
                    <div className="py-8 text-center">
                        <p className="text-sm text-destructive">{error}</p>
                    </div>
                ) : (
                    <div className="overflow-y-auto flex-1 -mx-6 px-6 space-y-2">
                        {/* Column headers */}
                        <div className="grid grid-cols-[1fr_auto_1fr] gap-3 px-2 pb-1 border-b border-border sticky top-0 bg-background z-10">
                            <p className="text-xs font-medium text-muted-foreground truncate">
                                {labelA}
                            </p>
                            <div className="w-20" />
                            <p className="text-xs font-medium text-muted-foreground truncate text-right">
                                {labelB}
                            </p>
                        </div>

                        {diffs.map((diff) => (
                            <Card key={diff.module} className={
                                diff.status === "unchanged"
                                    ? "border-border/50 opacity-60"
                                    : diff.status === "changed"
                                    ? "border-amber-500/30"
                                    : diff.status === "added"
                                    ? "border-green-500/30"
                                    : "border-red-500/30"
                            }>
                                <CardContent className="py-3">
                                    <div className="flex items-center gap-2 mb-2">
                                        <p className="text-sm font-medium">{diff.label}</p>
                                        {statusBadge(diff.status)}
                                    </div>

                                    {diff.status !== "unchanged" && (
                                        <div className="grid grid-cols-2 gap-3">
                                            <div className="rounded-md bg-muted/50 p-2">
                                                <p className="text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">
                                                    {labelA}
                                                </p>
                                                <p className="text-xs whitespace-pre-wrap break-words">
                                                    {truncate(diff.valueA, 500)}
                                                </p>
                                            </div>
                                            <div className="rounded-md bg-muted/50 p-2">
                                                <p className="text-[10px] text-muted-foreground mb-1 uppercase tracking-wider">
                                                    {labelB}
                                                </p>
                                                <p className="text-xs whitespace-pre-wrap break-words">
                                                    {truncate(diff.valueB, 500)}
                                                </p>
                                            </div>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )}

                <DialogFooter showCloseButton />
            </DialogContent>
        </Dialog>
    );
}

// ---- Schema & Fields ----------------------------------------------------

const snapshotSchema = z.object({
    label: z.string().min(1, "Label is required").max(200),
});
type SnapshotInput = z.infer<typeof snapshotSchema>;

const createFields: FieldConfig<SnapshotInput>[] = [
    {
        name: "label",
        label: "Snapshot Label",
        required: true,
        placeholder: "e.g. Pre-hearing snapshot, After discovery update",
    },
];

// ---- Helpers ------------------------------------------------------------

function formatTimestamp(ts: string): string {
    try {
        const d = new Date(ts);
        if (isNaN(d.getTime())) return ts;
        return d.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "numeric",
            minute: "2-digit",
        });
    } catch {
        return ts;
    }
}

function formatSize(bytes: number | undefined): string {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ---- Component ----------------------------------------------------------

export default function HistoryPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, isLoading: prepLoading } = usePrep();
    const { canEdit } = useRole();
    const queryClient = useQueryClient();

    const [dialogOpen, setDialogOpen] = useState(false);
    const [restoreTarget, setRestoreTarget] = useState<Snapshot | null>(null);

    // ---- Compare Mode State -------------------------------------------------
    const [compareMode, setCompareMode] = useState(false);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [diffDialogOpen, setDiffDialogOpen] = useState(false);
    const [diffResult, setDiffResult] = useState<ModuleDiff[]>([]);
    const [diffLabels, setDiffLabels] = useState<{ a: string; b: string }>({ a: "", b: "" });
    const [diffLoading, setDiffLoading] = useState(false);
    const [diffError, setDiffError] = useState<string | null>(null);

    const queryKey = ["snapshots", caseId, activePrepId];

    const { data, isLoading, error } = useQuery({
        queryKey,
        queryFn: () =>
            api.get<Snapshot[]>(
                `/cases/${caseId}/preparations/${activePrepId}/snapshots`,
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    const snapshots = data ?? [];

    // ---- Compare Helpers ----------------------------------------------------

    const toggleSelection = (id: string) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else {
                // Only allow selecting 2 snapshots
                if (next.size >= 2) return prev;
                next.add(id);
            }
            return next;
        });
    };

    const exitCompareMode = () => {
        setCompareMode(false);
        setSelectedIds(new Set());
    };

    const selectedArray = useMemo(() => Array.from(selectedIds), [selectedIds]);

    const handleCompare = async () => {
        if (selectedArray.length !== 2 || !activePrepId) return;

        const [idA, idB] = selectedArray;
        const snapA = snapshots.find((s) => s.id === idA);
        const snapB = snapshots.find((s) => s.id === idB);

        setDiffLabels({
            a: snapA?.label ?? "Snapshot A",
            b: snapB?.label ?? "Snapshot B",
        });
        setDiffLoading(true);
        setDiffError(null);
        setDiffDialogOpen(true);

        try {
            const [stateA, stateB] = await Promise.all([
                api.get<SnapshotState>(
                    `/cases/${caseId}/preparations/${activePrepId}/snapshots/${idA}`,
                    { getToken },
                ),
                api.get<SnapshotState>(
                    `/cases/${caseId}/preparations/${activePrepId}/snapshots/${idB}`,
                    { getToken },
                ),
            ]);

            setDiffResult(computeDiffs(stateA, stateB));
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Failed to load snapshot data";
            setDiffError(message);
        } finally {
            setDiffLoading(false);
        }
    };

    // ---- Mutations ----------------------------------------------------------

    const createMutation = useMutationWithToast<SnapshotInput>({
        mutationFn: (input) =>
            api.post(
                `/cases/${caseId}/preparations/${activePrepId}/snapshots`,
                input,
                { getToken },
            ),
        successMessage: "Snapshot created",
        invalidateKeys: [queryKey],
        onSuccess: () => setDialogOpen(false),
    });

    const restoreMutation = useMutationWithToast<string>({
        mutationFn: (snapshotId) =>
            api.post(
                `/cases/${caseId}/preparations/${activePrepId}/snapshots/${snapshotId}/restore`,
                {},
                { getToken },
            ),
        successMessage: "Snapshot restored successfully",
        invalidateKeys: [
            queryKey,
            ["timeline", caseId, activePrepId],
            ["witnesses", caseId, activePrepId],
            ["evidence", caseId, activePrepId],
            ["research", caseId, activePrepId],
        ],
        onSuccess: () => setRestoreTarget(null),
    });

    // ---- Guard: no prep selected --------------------------------------------

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">Create a preparation first to manage snapshots.</p>
            </div>
        );
    }

    // ---- Render -------------------------------------------------------------

    return (
        <div className="space-y-5">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">Version History</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Snapshots of preparation state — save and restore checkpoints
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {/* Compare mode toggle — only show when 2+ snapshots exist */}
                    {snapshots.length >= 2 && (
                        compareMode ? (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={exitCompareMode}
                            >
                                Cancel Compare
                            </Button>
                        ) : (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setCompareMode(true)}
                            >
                                Compare
                            </Button>
                        )
                    )}
                    {canEdit && (
                        <Button onClick={() => setDialogOpen(true)} size="sm" className="gap-1.5">
                            <span>+</span> Create Snapshot
                        </Button>
                    )}
                </div>
            </div>

            {/* Compare mode instructions */}
            {compareMode && (
                <div className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-4 py-2.5">
                    <p className="text-sm text-muted-foreground">
                        Select exactly 2 snapshots to compare.
                        {selectedArray.length > 0 && (
                            <span className="ml-1 font-medium text-foreground">
                                {selectedArray.length}/2 selected
                            </span>
                        )}
                    </p>
                    <Button
                        size="sm"
                        disabled={selectedArray.length !== 2}
                        onClick={handleCompare}
                    >
                        Compare Selected
                    </Button>
                </div>
            )}

            {/* Content */}
            {isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 5 }).map((_, i) => (
                        <Skeleton key={i} className="h-16 w-full rounded-lg" />
                    ))}
                </div>
            ) : error ? (
                <Card className="border-destructive/50">
                    <CardContent className="py-8 text-center">
                        <p className="text-sm text-destructive">
                            Failed to load snapshots: {error.message}
                        </p>
                    </CardContent>
                </Card>
            ) : snapshots.length === 0 ? (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        No snapshots yet. Create one to save the current preparation state.
                    </CardContent>
                </Card>
            ) : (
                <div className="relative">
                    {/* Vertical timeline line */}
                    <div className="absolute left-[19px] top-4 bottom-4 w-px bg-border" />

                    <div className="space-y-2">
                        {snapshots.map((snapshot, i) => {
                            const isSelected = selectedIds.has(snapshot.id);
                            const selectionDisabled = !isSelected && selectedIds.size >= 2;

                            return (
                                <div key={snapshot.id || i} className="flex gap-3 items-start relative">
                                    {/* Timeline dot */}
                                    <div className="w-10 h-10 rounded-full bg-card border border-border flex items-center justify-center shrink-0 z-10">
                                        <div
                                            className={`w-2.5 h-2.5 rounded-full ${
                                                i === 0 ? "bg-green-400" : "bg-muted-foreground"
                                            }`}
                                        />
                                    </div>

                                    {/* Snapshot card */}
                                    <Card
                                        className={`flex-1 transition-colors ${
                                            compareMode && isSelected
                                                ? "ring-2 ring-primary bg-primary/5"
                                                : "hover:bg-accent/20"
                                        } ${compareMode && selectionDisabled ? "opacity-50" : ""}`}
                                    >
                                        <CardContent className="py-3 flex items-center justify-between">
                                            <div className="flex items-center gap-3 min-w-0">
                                                {/* Checkbox in compare mode */}
                                                {compareMode && (
                                                    <input
                                                        type="checkbox"
                                                        checked={isSelected}
                                                        disabled={selectionDisabled}
                                                        onChange={() => toggleSelection(snapshot.id)}
                                                        className="h-4 w-4 rounded border-border accent-primary shrink-0 cursor-pointer disabled:cursor-not-allowed"
                                                    />
                                                )}
                                                <div className="min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        <p className="text-sm font-medium">{snapshot.label}</p>
                                                        {i === 0 && (
                                                            <Badge variant="outline" className="text-[10px] text-green-400 border-green-500/30">
                                                                Latest
                                                            </Badge>
                                                        )}
                                                    </div>
                                                    <div className="flex items-center gap-2 mt-0.5">
                                                        <span className="text-xs text-muted-foreground">
                                                            {formatTimestamp(snapshot.created_at)}
                                                        </span>
                                                        {snapshot.created_by && (
                                                            <Badge variant="secondary" className="text-[10px]">
                                                                {snapshot.created_by}
                                                            </Badge>
                                                        )}
                                                        {snapshot.size_bytes != null && snapshot.size_bytes > 0 && (
                                                            <span className="text-xs text-muted-foreground">
                                                                {formatSize(snapshot.size_bytes)}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                            {!compareMode && canEdit && (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => setRestoreTarget(snapshot)}
                                                    disabled={restoreMutation.isPending}
                                                >
                                                    Restore
                                                </Button>
                                            )}
                                        </CardContent>
                                    </Card>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Summary */}
            {!isLoading && snapshots.length > 0 && (
                <div className="pt-2 border-t border-border">
                    <span className="text-xs text-muted-foreground">
                        {snapshots.length} snapshot{snapshots.length !== 1 ? "s" : ""}
                    </span>
                </div>
            )}

            {/* Create Snapshot Dialog */}
            {canEdit && (
                <FormDialog
                    open={dialogOpen}
                    onOpenChange={setDialogOpen}
                    title="Create Snapshot"
                    description="Save the current preparation state. You can restore this snapshot later."
                    schema={snapshotSchema}
                    defaultValues={{ label: "" }}
                    fields={createFields}
                    onSubmit={(data) => createMutation.mutate(data)}
                    submitLabel="Create Snapshot"
                    isLoading={createMutation.isPending}
                />
            )}

            {/* Restore Confirm Dialog */}
            <ConfirmDialog
                open={!!restoreTarget}
                onOpenChange={(open) => !open && setRestoreTarget(null)}
                title="Restore Snapshot"
                description={`Restore "${restoreTarget?.label}"? The current state will be saved as a new snapshot before restoring.`}
                confirmLabel="Restore"
                variant="default"
                onConfirm={() => {
                    if (restoreTarget) restoreMutation.mutate(restoreTarget.id);
                }}
                isLoading={restoreMutation.isPending}
            />

            {/* Snapshot Diff Dialog */}
            <SnapshotDiffView
                open={diffDialogOpen}
                onOpenChange={setDiffDialogOpen}
                diffs={diffResult}
                labelA={diffLabels.a}
                labelB={diffLabels.b}
                isLoading={diffLoading}
                error={diffError}
            />
        </div>
    );
}
