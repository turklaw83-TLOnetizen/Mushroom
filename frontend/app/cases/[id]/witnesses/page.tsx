// ---- Witnesses Tab (with detail panel + optimistic deletes) -------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
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

interface Witness {
    name: string;
    type: string;
    role: string;
    goal: string;
}

const witnessSchema = z.object({
    name: z.string().min(1, "Name is required").max(200),
    type: z.string().min(1).max(50).default("State"),
    role: z.string().max(200).optional().default(""),
    goal: z.string().max(2000).optional().default(""),
});
type WitnessInput = z.infer<typeof witnessSchema>;

const createFields: FieldConfig<WitnessInput>[] = [
    { name: "name", label: "Witness Name", required: true, placeholder: "e.g. Officer Smith" },
    {
        name: "type", label: "Type", type: "select", options: [
            { value: "State", label: "State" },
            { value: "Defense", label: "Defense" },
            { value: "Expert", label: "Expert" },
            { value: "Character", label: "Character" },
        ],
    },
    { name: "role", label: "Role", placeholder: "e.g. Arresting officer" },
    { name: "goal", label: "Cross Goal", type: "textarea", placeholder: "What do we want from this witness?" },
];

const detailFields: DetailField<WitnessInput>[] = [
    { name: "name", label: "Name" },
    {
        name: "type", label: "Type", type: "select", options: [
            { value: "State", label: "State" },
            { value: "Defense", label: "Defense" },
            { value: "Expert", label: "Expert" },
            { value: "Character", label: "Character" },
        ],
    },
    { name: "role", label: "Role" },
    { name: "goal", label: "Cross Examination Goal", type: "textarea" },
];

export default function WitnessesPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, isLoading: prepLoading } = usePrep();
    const { canEdit, canDelete } = useRole();
    const queryClient = useQueryClient();
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteIndex, setDeleteIndex] = useState<number | null>(null);
    const [deleteWitness, setDeleteWitness] = useState<Witness | null>(null);
    const [detailWitness, setDetailWitness] = useState<{ witness: Witness; index: number } | null>(null);

    const queryKey = ["witnesses", caseId, activePrepId];

    const query = useQuery({
        queryKey,
        queryFn: () =>
            api.get<Witness[]>(
                `/cases/${caseId}/preparations/${activePrepId}/witnesses`,
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">Create a preparation first to manage witnesses.</p>
            </div>
        );
    }

    // ---- Mutations with centralized toast + optimistic delete ----

    const createMutation = useMutationWithToast<WitnessInput>({
        mutationFn: (data) =>
            api.post(`/cases/${caseId}/preparations/${activePrepId}/witnesses`, data, { getToken }),
        successMessage: "Witness added",
        invalidateKeys: [queryKey],
        onSuccess: () => setDialogOpen(false),
    });

    const updateMutation = useMutationWithToast<WitnessInput>({
        mutationFn: (data) => {
            if (!detailWitness) throw new Error("No witness selected");
            return api.put(
                `/cases/${caseId}/preparations/${activePrepId}/witnesses/${detailWitness.index}`,
                data,
                { getToken },
            );
        },
        successMessage: "Witness updated",
        invalidateKeys: [queryKey],
        onSuccess: () => setDetailWitness(null),
    });

    // Optimistic delete: immediately removes the witness from the list
    const deleteMutation = useMutationWithToast<number>({
        mutationFn: (index) =>
            api.delete(`/cases/${caseId}/preparations/${activePrepId}/witnesses/${index}`, { getToken }),
        successMessage: "Witness removed",
        invalidateKeys: [queryKey],
        onSuccess: () => { setDeleteIndex(null); setDeleteWitness(null); },
    });

    // Wrap delete to add optimistic update
    const handleDelete = () => {
        if (deleteIndex === null) return;
        const previousData = queryClient.getQueryData<Witness[]>(queryKey);

        // Optimistic: remove from cache immediately
        queryClient.setQueryData<Witness[]>(queryKey, (old) =>
            old ? old.filter((_, i) => i !== deleteIndex) : [],
        );

        deleteMutation.mutate(deleteIndex, {
            onError: () => {
                // Rollback on error
                if (previousData) queryClient.setQueryData(queryKey, previousData);
            },
        });
    };

    return (
        <DataPage
            title="Witnesses"
            subtitle="Witness list, goals, and examination plans"
            query={query}
            searchFilter={(w, s) =>
                w.name.toLowerCase().includes(s) || w.type.toLowerCase().includes(s)
            }
            searchPlaceholder="Search witnesses..."
            createLabel={canEdit ? "Add Witness" : null}
            onCreateClick={() => setDialogOpen(true)}
            renderItem={(witness, i) => (
                <Card
                    key={i}
                    className="hover:bg-accent/30 transition-colors group cursor-pointer"
                    onClick={() => setDetailWitness({ witness, index: i })}
                >
                    <CardContent className="flex items-center justify-between py-3">
                        <div className="flex items-center gap-3">
                            <span className="text-2xl" aria-hidden="true">👤</span>
                            <div>
                                <p className="font-medium text-sm">{witness.name}</p>
                                <p className="text-xs text-muted-foreground">{witness.goal || "No goal set"}</p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <Badge
                                variant="outline"
                                className={
                                    witness.type === "Defense"
                                        ? "text-blue-400 border-blue-500/30"
                                        : witness.type === "Expert"
                                            ? "text-violet-400 border-violet-500/30"
                                            : "text-amber-400 border-amber-500/30"
                                }
                            >
                                {witness.type}
                            </Badge>
                            {witness.role && (
                                <Badge variant="secondary" className="text-xs">{witness.role}</Badge>
                            )}
                            {canDelete && (
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive"
                                    aria-label={`Delete ${witness.name}`}
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setDeleteIndex(i);
                                        setDeleteWitness(witness);
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
                    title="Add Witness"
                    description="Add a new witness to this preparation."
                    schema={witnessSchema}
                    defaultValues={{ name: "", type: "State", role: "", goal: "" }}
                    fields={createFields}
                    onSubmit={(data) => createMutation.mutate(data)}
                    submitLabel="Add Witness"
                    isLoading={createMutation.isPending}
                />
            )}
            <ConfirmDialog
                open={deleteIndex !== null}
                onOpenChange={(open) => {
                    if (!open) { setDeleteIndex(null); setDeleteWitness(null); }
                }}
                title="Remove Witness"
                description={`Remove "${deleteWitness?.name}" from this preparation?`}
                confirmLabel="Remove"
                onConfirm={handleDelete}
                isLoading={deleteMutation.isPending}
            />
            {detailWitness && (
                <DetailPanel
                    open={!!detailWitness}
                    onOpenChange={(open) => !open && setDetailWitness(null)}
                    title={detailWitness.witness.name}
                    description="View and edit witness details"
                    schema={witnessSchema}
                    values={detailWitness.witness as WitnessInput}
                    fields={detailFields}
                    onSave={(data) => updateMutation.mutate(data)}
                    readOnly={!canEdit}
                    isLoading={updateMutation.isPending}
                    onDelete={canDelete ? () => {
                        setDeleteIndex(detailWitness.index);
                        setDeleteWitness(detailWitness.witness);
                        setDetailWitness(null);
                    } : undefined}
                />
            )}
        </DataPage>
    );
}
