// ---- Witnesses Tab (with detail panel, exam generation, optimistic deletes)
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
import { Skeleton } from "@/components/ui/skeleton";

// ---- Types --------------------------------------------------------------

interface Witness {
    name: string;
    type: string;
    role: string;
    goal: string;
}

interface ExamEntry {
    witness?: string;
    witness_name?: string;
    topic?: string;
    question?: string;
    questions?: string[];
    themes?: string[];
    strategy?: string;
    objectives?: string[];
    content?: string;
    [key: string]: unknown;
}

interface PrepState {
    cross_examination_plan?: ExamEntry[] | string;
    direct_examination_plan?: ExamEntry[] | string;
    [key: string]: unknown;
}

// ---- Schema & Fields ----------------------------------------------------

const witnessSchema = z.object({
    name: z.string().min(1, "Name is required").max(200),
    type: z.string().min(1).max(50).default("State"),
    role: z.string().max(200).optional().default(""),
    goal: z.string().max(2000).optional().default(""),
});
type WitnessInput = z.infer<typeof witnessSchema>;

const WITNESS_TYPE_OPTIONS = [
    { value: "State", label: "State" },
    { value: "Defense", label: "Defense" },
    { value: "Swing", label: "Swing" },
    { value: "Expert", label: "Expert" },
    { value: "Character", label: "Character" },
];

const createFields: FieldConfig<WitnessInput>[] = [
    { name: "name", label: "Witness Name", required: true, placeholder: "e.g. Officer Smith" },
    { name: "type", label: "Type", type: "select", options: WITNESS_TYPE_OPTIONS },
    { name: "role", label: "Role", placeholder: "e.g. Arresting officer" },
    { name: "goal", label: "Cross Goal", type: "textarea", placeholder: "What do we want from this witness?" },
];

const detailFields: DetailField<WitnessInput>[] = [
    { name: "name", label: "Name" },
    { name: "type", label: "Type", type: "select", options: WITNESS_TYPE_OPTIONS },
    { name: "role", label: "Role" },
    { name: "goal", label: "Cross Examination Goal", type: "textarea" },
];

// ---- Helpers ------------------------------------------------------------

/** Witness types eligible for cross-examination (opposing/neutral). */
const CROSS_TYPES = new Set(["State", "Swing", "Unknown"]);

/** Witness types eligible for direct examination (friendly). */
const DIRECT_TYPES = new Set(["Defense", "Swing"]);

function canCrossExam(type: string) {
    return CROSS_TYPES.has(type);
}

function canDirectExam(type: string) {
    return DIRECT_TYPES.has(type);
}

/** Get the display name for a witness in an exam entry. */
function examWitnessName(entry: ExamEntry): string {
    return entry.witness ?? entry.witness_name ?? "Unknown";
}

/** Find all exam entries matching a witness name. */
function findExamEntries(plan: ExamEntry[] | string | undefined, witnessName: string): ExamEntry[] {
    if (!plan || typeof plan === "string") return [];
    return plan.filter(
        (e) => examWitnessName(e).toLowerCase() === witnessName.toLowerCase()
    );
}

// ---- Exam Content Renderer ----------------------------------------------

function ExamContent({ entries, label }: { entries: ExamEntry[]; label: string }) {
    const [expanded, setExpanded] = useState(false);

    if (entries.length === 0) return null;

    return (
        <div className="mt-2 border-t border-border/50 pt-2">
            <button
                type="button"
                className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors w-full text-left"
                onClick={(e) => {
                    e.stopPropagation();
                    setExpanded((prev) => !prev);
                }}
            >
                <span className={`transition-transform ${expanded ? "rotate-90" : ""}`}>
                    {"\u25B6"}
                </span>
                {label} ({entries.length} {entries.length === 1 ? "section" : "sections"})
            </button>
            {expanded && (
                <div className="mt-2 space-y-2 pl-3 border-l-2 border-primary/20">
                    {entries.map((entry, idx) => (
                        <div key={idx} className="space-y-1">
                            {entry.topic && (
                                <p className="text-xs font-medium text-primary">{entry.topic}</p>
                            )}
                            {entry.strategy && (
                                <p className="text-xs text-muted-foreground">{entry.strategy}</p>
                            )}
                            {entry.objectives && entry.objectives.length > 0 && (
                                <ul className="text-xs text-muted-foreground list-disc pl-4 space-y-0.5">
                                    {entry.objectives.map((obj, oi) => (
                                        <li key={oi}>{obj}</li>
                                    ))}
                                </ul>
                            )}
                            {entry.themes && entry.themes.length > 0 && (
                                <div className="flex gap-1 flex-wrap">
                                    {entry.themes.map((theme, ti) => (
                                        <Badge key={ti} variant="secondary" className="text-[9px]">
                                            {theme}
                                        </Badge>
                                    ))}
                                </div>
                            )}
                            {entry.questions && entry.questions.length > 0 && (
                                <ul className="text-xs text-muted-foreground list-decimal pl-4 space-y-0.5">
                                    {entry.questions.map((q, qi) => (
                                        <li key={qi}>{q}</li>
                                    ))}
                                </ul>
                            )}
                            {entry.question && !entry.questions && (
                                <p className="text-xs text-muted-foreground italic">{entry.question}</p>
                            )}
                            {entry.content && typeof entry.content === "string" && (
                                <p className="text-xs text-muted-foreground whitespace-pre-wrap">
                                    {entry.content.length > 500
                                        ? entry.content.slice(0, 500) + "..."
                                        : entry.content}
                                </p>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

// ---- Page Component -----------------------------------------------------

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

    // Track which witness+exam type is currently generating
    const [generatingExam, setGeneratingExam] = useState<string | null>(null);

    const queryKey = ["witnesses", caseId, activePrepId];
    const prepStateKey = ["prep-state", caseId, activePrepId];

    const query = useQuery({
        queryKey,
        queryFn: () =>
            api.get<Witness[]>(
                `/cases/${caseId}/preparations/${activePrepId}/witnesses`,
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    // Fetch prep state to get existing exam plans
    const prepStateQuery = useQuery({
        queryKey: prepStateKey,
        queryFn: () =>
            api.get<PrepState>(
                `/cases/${caseId}/preparations/${activePrepId}`,
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

    // ---- Exam Generation ----

    const handleGenerateExam = async (witnessName: string, examType: "cross" | "direct") => {
        const genKey = `${witnessName}-${examType}`;
        setGeneratingExam(genKey);

        const moduleKey = examType === "cross" ? "cross_examiner" : "direct_examiner";

        try {
            await api.post(
                `/cases/${caseId}/analysis/start`,
                {
                    prep_id: activePrepId,
                    active_modules: [moduleKey],
                },
                { getToken },
            );

            // Poll for completion
            const maxPollAttempts = 60; // 5 minutes at 5s intervals
            for (let i = 0; i < maxPollAttempts; i++) {
                await new Promise((r) => setTimeout(r, 5000));

                const status = await api.get<{ status: string; progress?: number; current_module?: string }>(
                    `/cases/${caseId}/analysis/status`,
                    { getToken, params: { prep_id: activePrepId! } },
                );

                if (status.status === "completed" || status.status === "idle") {
                    break;
                }
                if (status.status === "error") {
                    throw new Error("Analysis failed");
                }
            }

            // Refresh prep state to get the new exam plan
            await queryClient.invalidateQueries({ queryKey: prepStateKey });

            const label = examType === "cross" ? "Cross-examination" : "Direct-examination";
            const toastFn = await import("sonner").then((m) => m.toast);
            toastFn.success(`${label} plan generated for ${witnessName}`);
        } catch (err) {
            const toastFn = await import("sonner").then((m) => m.toast);
            const label = examType === "cross" ? "cross-examination" : "direct-examination";
            toastFn.error(`Failed to generate ${label}`, {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        } finally {
            setGeneratingExam(null);
        }
    };

    // ---- Derived exam data ----

    const crossPlan = prepStateQuery.data?.cross_examination_plan;
    const directPlan = prepStateQuery.data?.direct_examination_plan;

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
            renderItem={(witness, i) => {
                const crossEntries = findExamEntries(crossPlan, witness.name);
                const directEntries = findExamEntries(directPlan, witness.name);
                const crossGenKey = `${witness.name}-cross`;
                const directGenKey = `${witness.name}-direct`;
                const isGeneratingCross = generatingExam === crossGenKey;
                const isGeneratingDirect = generatingExam === directGenKey;
                const isGeneratingAny = generatingExam !== null;

                return (
                    <Card
                        key={i}
                        className="hover:bg-accent/30 transition-colors group cursor-pointer"
                        onClick={() => setDetailWitness({ witness, index: i })}
                    >
                        <CardContent className="py-3">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3 min-w-0">
                                    <span className="text-2xl flex-shrink-0" aria-hidden="true">{"\uD83D\uDC64"}</span>
                                    <div className="min-w-0">
                                        <p className="font-medium text-sm">{witness.name}</p>
                                        <p className="text-xs text-muted-foreground truncate">
                                            {witness.goal || "No goal set"}
                                        </p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2 flex-shrink-0">
                                    <Badge
                                        variant="outline"
                                        className={
                                            witness.type === "Defense"
                                                ? "text-blue-400 border-blue-500/30"
                                                : witness.type === "Expert"
                                                    ? "text-violet-400 border-violet-500/30"
                                                    : witness.type === "Swing"
                                                        ? "text-cyan-400 border-cyan-500/30"
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
                                            {"\u2715"}
                                        </Button>
                                    )}
                                </div>
                            </div>

                            {/* Exam action buttons */}
                            {canEdit && (canCrossExam(witness.type) || canDirectExam(witness.type)) && (
                                <div className="flex gap-2 mt-2 ml-10" onClick={(e) => e.stopPropagation()}>
                                    {canCrossExam(witness.type) && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="text-xs h-7 gap-1.5"
                                            disabled={isGeneratingAny}
                                            onClick={() => handleGenerateExam(witness.name, "cross")}
                                        >
                                            {isGeneratingCross ? (
                                                <>
                                                    <LoadingSpinner />
                                                    Generating...
                                                </>
                                            ) : (
                                                <>
                                                    {crossEntries.length > 0 ? "Regenerate" : "Generate"} Cross-Exam
                                                </>
                                            )}
                                        </Button>
                                    )}
                                    {canDirectExam(witness.type) && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="text-xs h-7 gap-1.5"
                                            disabled={isGeneratingAny}
                                            onClick={() => handleGenerateExam(witness.name, "direct")}
                                        >
                                            {isGeneratingDirect ? (
                                                <>
                                                    <LoadingSpinner />
                                                    Generating...
                                                </>
                                            ) : (
                                                <>
                                                    {directEntries.length > 0 ? "Regenerate" : "Generate"} Direct-Exam
                                                </>
                                            )}
                                        </Button>
                                    )}
                                </div>
                            )}

                            {/* Existing exam plans */}
                            {crossEntries.length > 0 && (
                                <div className="ml-10" onClick={(e) => e.stopPropagation()}>
                                    <ExamContent entries={crossEntries} label="Cross-Examination Plan" />
                                </div>
                            )}
                            {directEntries.length > 0 && (
                                <div className="ml-10" onClick={(e) => e.stopPropagation()}>
                                    <ExamContent entries={directEntries} label="Direct-Examination Plan" />
                                </div>
                            )}

                            {/* Show string-type plans (e.g. "No defense witnesses identified.") */}
                            {typeof directPlan === "string" && canDirectExam(witness.type) && (
                                <div className="ml-10 mt-1" onClick={(e) => e.stopPropagation()}>
                                    <p className="text-xs text-muted-foreground italic">{directPlan}</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                );
            }}
        >
            {/* Loading state for prep state query */}
            {prepStateQuery.isLoading && activePrepId && (
                <div className="space-y-2">
                    <Skeleton className="h-4 w-48" />
                    <Skeleton className="h-4 w-32" />
                </div>
            )}

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

// ---- Loading Spinner Component ------------------------------------------

function LoadingSpinner() {
    return (
        <svg
            className="animate-spin h-3 w-3"
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
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
        </svg>
    );
}
