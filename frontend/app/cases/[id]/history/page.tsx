// ---- Version History / Snapshots Tab ------------------------------------
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
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

// ---- Types --------------------------------------------------------------

interface Snapshot {
    id: string;
    label: string;
    created_at: string;
    created_by?: string;
    size_bytes?: number;
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
                    {canEdit && (
                        <Button onClick={() => setDialogOpen(true)} size="sm" className="gap-1.5">
                            <span>+</span> Create Snapshot
                        </Button>
                    )}
                </div>
            </div>

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
                        {snapshots.map((snapshot, i) => (
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
                                <Card className="flex-1 hover:bg-accent/20 transition-colors">
                                    <CardContent className="py-3 flex items-center justify-between">
                                        <div>
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
                                        {canEdit && (
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
                        ))}
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
        </div>
    );
}
