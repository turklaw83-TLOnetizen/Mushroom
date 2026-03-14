// ---- Witnesses Tab (CRUD + Exam Results) ---------------------------------
// Detail panel now includes Cross-Exam and Direct-Exam plans from analysis.
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import { api } from "@/lib/api-client";
import { usePrep } from "@/hooks/use-prep";
import { useRole } from "@/hooks/use-role";
import { usePrepState } from "@/hooks/use-prep-state";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { MarkdownContent } from "@/components/analysis/markdown-content";
import { GenerateButton } from "@/components/analysis/generate-button";
import { DataPage } from "@/components/shared/data-page";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";

// ---- Witness Type Colors ------------------------------------------------

const WITNESS_TYPE_COLORS: Record<string, { bg: string; border: string; text: string; dot: string; borderTop: string }> = {
    State: { bg: "bg-amber-500/20", border: "border-amber-500", text: "text-amber-300", dot: "bg-amber-500", borderTop: "border-t-amber-500" },
    Defense: { bg: "bg-blue-500/20", border: "border-blue-500", text: "text-blue-300", dot: "bg-blue-500", borderTop: "border-t-blue-500" },
    Expert: { bg: "bg-violet-500/20", border: "border-violet-500", text: "text-violet-300", dot: "bg-violet-500", borderTop: "border-t-violet-500" },
    Character: { bg: "bg-emerald-500/20", border: "border-emerald-500", text: "text-emerald-300", dot: "bg-emerald-500", borderTop: "border-t-emerald-500" },
    Swing: { bg: "bg-orange-500/20", border: "border-orange-500", text: "text-orange-300", dot: "bg-orange-500", borderTop: "border-t-orange-500" },
};

const DEFAULT_TYPE_COLORS = { bg: "bg-muted/40", border: "border-muted-foreground", text: "text-muted-foreground", dot: "bg-muted-foreground", borderTop: "border-t-muted-foreground" };

const WITNESS_TYPE_ORDER = ["State", "Expert", "Defense", "Character", "Swing"];

// ---- Witness Timeline Overlay -------------------------------------------

function WitnessTimeline({ witnesses }: { witnesses: Witness[] }) {
    // Sort witnesses by type order, then alphabetically within each type
    const sorted = [...witnesses].sort((a, b) => {
        const aOrder = WITNESS_TYPE_ORDER.indexOf(a.type);
        const bOrder = WITNESS_TYPE_ORDER.indexOf(b.type);
        const aIdx = aOrder === -1 ? WITNESS_TYPE_ORDER.length : aOrder;
        const bIdx = bOrder === -1 ? WITNESS_TYPE_ORDER.length : bOrder;
        if (aIdx !== bIdx) return aIdx - bIdx;
        return a.name.localeCompare(b.name);
    });

    if (sorted.length === 0) {
        return (
            <div className="mb-4">
                <EmptyState
                    icon="👥"
                    title="No witnesses recorded"
                    description="Add witnesses to build your witness list for examination preparation."
                />
            </div>
        );
    }

    return (
        <Card className="mb-4">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                    Witness Timeline
                    <Badge variant="secondary" className="text-xs">{sorted.length} witnesses</Badge>
                </CardTitle>
                <div className="flex gap-2 mt-1">
                    {WITNESS_TYPE_ORDER.map((type) => {
                        const colors = WITNESS_TYPE_COLORS[type] ?? DEFAULT_TYPE_COLORS;
                        return (
                            <Badge key={type} variant="outline" className={`text-[10px] ${colors.text} ${colors.border}`}>
                                <span className={`inline-block w-1.5 h-1.5 rounded-full ${colors.dot} mr-1`} />
                                {type}
                            </Badge>
                        );
                    })}
                </div>
            </CardHeader>
            <CardContent>
                <div className="overflow-x-auto">
                    <div className="flex gap-2 min-w-max pb-1">
                        {sorted.map((w, i) => {
                            const colors = WITNESS_TYPE_COLORS[w.type] ?? DEFAULT_TYPE_COLORS;
                            return (
                                <div
                                    key={`${w.name}-${i}`}
                                    className={`flex-shrink-0 rounded-md border-t-2 ${colors.borderTop} border-l-4 ${colors.border} ${colors.bg} px-3 py-2 min-w-[220px] max-w-[260px]`}
                                >
                                    <p className="text-sm font-medium truncate">{w.name}</p>
                                    <p className="text-xs text-muted-foreground truncate">{w.role || w.type}</p>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

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

// ---- Witness Detail Panel with Exam Results ------------------------------

function WitnessDetailPanel({
    witness,
    crossExamContent,
    directExamContent,
    caseId,
    prepId,
    canEdit,
    canDelete,
    onClose,
    onUpdate,
    onDelete,
    isUpdating,
}: {
    witness: Witness;
    crossExamContent: string | Record<string, unknown> | null;
    directExamContent: string | Record<string, unknown> | null;
    caseId: string;
    prepId: string | null;
    canEdit: boolean;
    canDelete: boolean;
    onClose: () => void;
    onUpdate: (data: WitnessInput) => void;
    onDelete: () => void;
    isUpdating: boolean;
}) {
    const [isEditing, setIsEditing] = useState(false);
    const [editData, setEditData] = useState<WitnessInput>({
        name: witness.name,
        type: witness.type,
        role: witness.role,
        goal: witness.goal,
    });

    const handleSave = () => {
        onUpdate(editData);
        setIsEditing(false);
    };

    const renderExamContent = (content: string | Record<string, unknown>) => {
        if (typeof content === "string") {
            return <MarkdownContent content={content} />;
        }
        return (
            <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-96 whitespace-pre-wrap">
                {JSON.stringify(content, null, 2)}
            </pre>
        );
    };

    return (
        <Sheet open onOpenChange={(open) => !open && onClose()}>
            <SheetContent className="sm:max-w-xl overflow-y-auto">
                <SheetHeader>
                    <SheetTitle className="flex items-center gap-2">
                        <span aria-hidden="true">👤</span> {witness.name}
                    </SheetTitle>
                    <SheetDescription>
                        {(() => {
                            const tc = WITNESS_TYPE_COLORS[witness.type] ?? DEFAULT_TYPE_COLORS;
                            return (
                                <Badge variant="outline" className={`${tc.text} ${tc.border}`}>
                                    <span className={`inline-block w-1.5 h-1.5 rounded-full ${tc.dot} mr-1`} />
                                    {witness.type}
                                </Badge>
                            );
                        })()}
                        {witness.role && (
                            <Badge variant="secondary" className="ml-2 text-xs">{witness.role}</Badge>
                        )}
                    </SheetDescription>
                </SheetHeader>

                <Tabs defaultValue="info" className="mt-4">
                    <TabsList variant="line" className="w-full">
                        <TabsTrigger value="info">Info</TabsTrigger>
                        <TabsTrigger value="cross-exam">
                            Cross {crossExamContent && <span className="ml-1 text-emerald-400" aria-hidden="true">●</span>}
                        </TabsTrigger>
                        <TabsTrigger value="direct-exam">
                            Direct {directExamContent && <span className="ml-1 text-emerald-400" aria-hidden="true">●</span>}
                        </TabsTrigger>
                        <TabsTrigger value="witness-prep">Prep</TabsTrigger>
                    </TabsList>

                    {/* ---- Info Tab ---- */}
                    <TabsContent value="info" className="space-y-4 mt-4">
                        {isEditing ? (
                            <div className="space-y-3">
                                <div>
                                    <label className="text-sm font-medium">Name</label>
                                    <input
                                        className="w-full mt-1 px-3 py-2 rounded-md border bg-background text-sm"
                                        value={editData.name}
                                        onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="text-sm font-medium">Type</label>
                                    <select
                                        className="w-full mt-1 px-3 py-2 rounded-md border bg-background text-sm"
                                        value={editData.type}
                                        onChange={(e) => setEditData({ ...editData, type: e.target.value })}
                                    >
                                        <option value="State">State</option>
                                        <option value="Defense">Defense</option>
                                        <option value="Expert">Expert</option>
                                        <option value="Character">Character</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="text-sm font-medium">Role</label>
                                    <input
                                        className="w-full mt-1 px-3 py-2 rounded-md border bg-background text-sm"
                                        value={editData.role}
                                        onChange={(e) => setEditData({ ...editData, role: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="text-sm font-medium">Cross Goal</label>
                                    <textarea
                                        className="w-full mt-1 px-3 py-2 rounded-md border bg-background text-sm min-h-[80px]"
                                        value={editData.goal}
                                        onChange={(e) => setEditData({ ...editData, goal: e.target.value })}
                                    />
                                </div>
                                <div className="flex gap-2">
                                    <Button size="sm" onClick={handleSave} disabled={isUpdating}>
                                        {isUpdating ? "Saving..." : "Save"}
                                    </Button>
                                    <Button size="sm" variant="outline" onClick={() => setIsEditing(false)}>Cancel</Button>
                                </div>
                            </div>
                        ) : (
                            <>
                                <dl className="space-y-3">
                                    <div>
                                        <dt className="text-xs font-medium text-muted-foreground">Type</dt>
                                        <dd className="text-sm mt-0.5">{witness.type}</dd>
                                    </div>
                                    {witness.role && (
                                        <div>
                                            <dt className="text-xs font-medium text-muted-foreground">Role</dt>
                                            <dd className="text-sm mt-0.5">{witness.role}</dd>
                                        </div>
                                    )}
                                    {witness.goal && (
                                        <div>
                                            <dt className="text-xs font-medium text-muted-foreground">Cross-Examination Goal</dt>
                                            <dd className="text-sm mt-0.5 whitespace-pre-wrap">{witness.goal}</dd>
                                        </div>
                                    )}
                                </dl>
                                <Separator />
                                <div className="flex gap-2">
                                    {canEdit && (
                                        <Button size="sm" variant="outline" onClick={() => setIsEditing(true)}>
                                            Edit
                                        </Button>
                                    )}
                                    {canDelete && (
                                        <Button size="sm" variant="destructive" onClick={onDelete}>
                                            Delete
                                        </Button>
                                    )}
                                </div>
                            </>
                        )}
                    </TabsContent>

                    {/* ---- Cross-Exam Tab ---- */}
                    <TabsContent value="cross-exam" className="mt-4">
                        {crossExamContent ? (
                            <Card>
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm flex items-center gap-2">
                                        <span aria-hidden="true">❓</span> Cross-Examination Plan
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    {renderExamContent(crossExamContent)}
                                </CardContent>
                            </Card>
                        ) : (
                            <EmptyState
                                icon="🗡️"
                                title="No cross-examination plan yet"
                                description="Run analysis with the cross-examiner module to generate cross-examination strategies for this witness."
                            />
                        )}
                    </TabsContent>

                    {/* ---- Direct-Exam Tab ---- */}
                    <TabsContent value="direct-exam" className="mt-4">
                        {directExamContent ? (
                            <Card>
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm flex items-center gap-2">
                                        <span aria-hidden="true">💬</span> Direct-Examination Plan
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    {renderExamContent(directExamContent)}
                                </CardContent>
                            </Card>
                        ) : (
                            <EmptyState
                                icon="🛡️"
                                title="No direct examination plan yet"
                                description="Run analysis with the direct-examiner module to generate direct examination questions for this witness."
                            />
                        )}
                    </TabsContent>

                    {/* ---- Witness Prep Tab (On-Demand Generation) ---- */}
                    <TabsContent value="witness-prep" className="mt-4 space-y-6">
                        <GenerateButton
                            caseId={caseId}
                            prepId={prepId}
                            endpoint="witness-prep"
                            label="Witness Prep"
                            icon="🎯"
                            body={{
                                witness_name: witness.name,
                                witness_role: witness.role || "",
                                witness_goal: witness.goal || "",
                            }}
                            resultKey="witness_prep"
                            emptyMessage="Generate mock cross-examination scenarios and preparation notes for this witness."
                        />
                        <GenerateButton
                            caseId={caseId}
                            prepId={prepId}
                            endpoint="interview-plan"
                            label="Interview Plan"
                            icon="📋"
                            body={{
                                witness_name: witness.name,
                                witness_role: witness.role || "",
                                interview_type: "initial",
                            }}
                            resultKey="interview_plan"
                            emptyMessage="Generate a structured interview preparation plan for this witness."
                        />
                        <GenerateButton
                            caseId={caseId}
                            prepId={prepId}
                            endpoint="deposition-outline"
                            label="Deposition Outline"
                            icon="📑"
                            body={{
                                witness_name: witness.name,
                                witness_role: witness.role || "",
                                topics: "",
                            }}
                            resultKey="deposition_outline"
                            emptyMessage="Generate a structured deposition outline for this witness."
                        />
                    </TabsContent>
                </Tabs>
            </SheetContent>
        </Sheet>
    );
}

// ---- Main Page ----------------------------------------------------------

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
    const [showTimeline, setShowTimeline] = useState(false);

    // Analysis results for exam plans
    const { sections } = usePrepState(caseId, activePrepId);

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

    // ---- Loading skeleton ----
    if (prepLoading || query.isLoading) {
        return (
            <div className="space-y-4 p-6">
                <div className="flex items-center justify-between">
                    <div>
                        <Skeleton className="h-7 w-36" />
                        <Skeleton className="h-4 w-64 mt-1" />
                    </div>
                    <Skeleton className="h-9 w-28" />
                </div>
                <Skeleton className="h-9 w-full max-w-sm" />
                <div className="space-y-2">
                    {Array.from({ length: 5 }).map((_, i) => (
                        <Card key={i}>
                            <CardContent className="flex items-center justify-between py-3">
                                <div className="flex items-center gap-3">
                                    <Skeleton className="h-8 w-8 rounded-full" />
                                    <div>
                                        <Skeleton className="h-4 w-32 mb-1" />
                                        <Skeleton className="h-3 w-48" />
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Skeleton className="h-5 w-14 rounded-full" />
                                    <Skeleton className="h-5 w-16 rounded-full" />
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
                <p className="text-muted-foreground">Create a preparation first to manage witnesses.</p>
            </div>
        );
    }

    // ---- Mutations ----

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

    const deleteMutation = useMutationWithToast<number>({
        mutationFn: (index) =>
            api.delete(`/cases/${caseId}/preparations/${activePrepId}/witnesses/${index}`, { getToken }),
        successMessage: "Witness removed",
        invalidateKeys: [queryKey],
        onSuccess: () => { setDeleteIndex(null); setDeleteWitness(null); },
    });

    const handleDelete = () => {
        if (deleteIndex === null) return;
        const previousData = queryClient.getQueryData<Witness[]>(queryKey);

        queryClient.setQueryData<Witness[]>(queryKey, (old) =>
            old ? old.filter((_, i) => i !== deleteIndex) : [],
        );

        deleteMutation.mutate(deleteIndex, {
            onError: () => {
                if (previousData) queryClient.setQueryData(queryKey, previousData);
            },
        });
    };

    // Get exam content for a witness by name
    const getExamContent = (witnessName: string, plan: Record<string, unknown>) => {
        if (plan[witnessName]) return plan[witnessName] as string | Record<string, unknown>;
        const key = Object.keys(plan).find(k => k.toLowerCase() === witnessName.toLowerCase());
        if (key) return plan[key] as string | Record<string, unknown>;
        return null;
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
            headerActions={
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowTimeline((v) => !v)}
                >
                    {showTimeline ? "List View" : "Timeline View"}
                </Button>
            }
            beforeList={
                showTimeline && query.data ? (
                    <WitnessTimeline witnesses={query.data} />
                ) : null
            }
            renderItem={(witness, i) => {
                const hasCross = !!getExamContent(witness.name, sections.crossExamPlan);
                const hasDirect = !!getExamContent(witness.name, sections.directExamPlan);

                return (
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
                                {hasCross && (
                                    <Badge variant="outline" className="text-xs bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30">
                                        <span className="mr-0.5" aria-hidden="true">&#10003;</span> Cross
                                    </Badge>
                                )}
                                {hasDirect && (
                                    <Badge variant="outline" className="text-xs bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/30">
                                        <span className="mr-0.5" aria-hidden="true">&#10003;</span> Direct
                                    </Badge>
                                )}
                                {(() => {
                                    const tc = WITNESS_TYPE_COLORS[witness.type] ?? DEFAULT_TYPE_COLORS;
                                    return (
                                        <Badge variant="outline" className={`${tc.text} ${tc.border}`}>
                                            <span className={`inline-block w-1.5 h-1.5 rounded-full ${tc.dot} mr-1`} />
                                            {witness.type}
                                        </Badge>
                                    );
                                })()}
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
                                        <span aria-hidden="true">✕</span>
                                    </Button>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                );
            }}
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
                <WitnessDetailPanel
                    witness={detailWitness.witness}
                    crossExamContent={getExamContent(detailWitness.witness.name, sections.crossExamPlan)}
                    directExamContent={getExamContent(detailWitness.witness.name, sections.directExamPlan)}
                    caseId={caseId}
                    prepId={activePrepId}
                    canEdit={canEdit}
                    canDelete={canDelete}
                    onClose={() => setDetailWitness(null)}
                    onUpdate={(data) => updateMutation.mutate(data)}
                    onDelete={() => {
                        setDeleteIndex(detailWitness.index);
                        setDeleteWitness(detailWitness.witness);
                        setDetailWitness(null);
                    }}
                    isUpdating={updateMutation.isPending}
                />
            )}
        </DataPage>
    );
}
