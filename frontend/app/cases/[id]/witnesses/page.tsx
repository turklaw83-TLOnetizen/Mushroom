// ---- Witnesses Tab (with detail panel, exam generation, on-demand AI, optimistic deletes)
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import type { Witness } from "@/types/api";
import { usePrep } from "@/hooks/use-prep";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { DataPage } from "@/components/shared/data-page";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { DetailPanel, type DetailField } from "@/components/shared/detail-panel";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
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

/** Shape of the on-demand result returned by witness-prep / interview-plan endpoints. */
interface OnDemandResult {
    result?: string;
    content?: string;
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

/** Extract readable text from an on-demand result object. */
function extractResultText(data: OnDemandResult): string {
    return data.result ?? data.content ?? JSON.stringify(data, null, 2);
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

// ---- Markdown Result Renderer -------------------------------------------

function MarkdownResult({ content }: { content: string }) {
    return (
        <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
    );
}

// ---- On-Demand Result Modal ---------------------------------------------

function OnDemandResultDialog({
    open,
    onOpenChange,
    title,
    witnessName,
    content,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title: string;
    witnessName: string;
    content: string;
}) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>{title}</DialogTitle>
                    <DialogDescription>Generated for {witnessName}</DialogDescription>
                </DialogHeader>
                <div className="mt-2">
                    <MarkdownResult content={content} />
                </div>
                <DialogFooter showCloseButton />
            </DialogContent>
        </Dialog>
    );
}

// ---- Deposition Analysis Section ----------------------------------------

function DepositionAnalysisSection({
    caseId,
    prepId,
    getToken,
}: {
    caseId: string;
    prepId: string;
    getToken: () => Promise<string | null>;
}) {
    const [expanded, setExpanded] = useState(false);
    const [transcript, setTranscript] = useState("");
    const [analysisResult, setAnalysisResult] = useState<string | null>(null);

    const depositionMutation = useMutation({
        mutationFn: (body: { prep_id: string; transcript: string }) =>
            api.post<OnDemandResult>(
                `/cases/${caseId}/ondemand/deposition-analysis`,
                body,
                { getToken },
            ),
        onSuccess: (data) => {
            const text = extractResultText(data);
            setAnalysisResult(text);
            toast.success("Deposition analysis complete");
        },
        onError: (err: Error) => {
            toast.error("Deposition analysis failed", { description: err.message });
        },
    });

    const handleAnalyze = () => {
        if (!transcript.trim()) {
            toast.error("Please paste a transcript before analyzing");
            return;
        }
        depositionMutation.mutate({ prep_id: prepId, transcript: transcript.trim() });
    };

    return (
        <Card className="mt-6">
            <CardHeader className="pb-3">
                <button
                    type="button"
                    className="flex items-center gap-2 text-left w-full"
                    onClick={() => setExpanded((prev) => !prev)}
                >
                    <span className={`transition-transform text-xs ${expanded ? "rotate-90" : ""}`}>
                        {"\u25B6"}
                    </span>
                    <CardTitle className="text-base">Deposition Analysis</CardTitle>
                </button>
                {!expanded && (
                    <CardDescription className="ml-5">
                        Paste a deposition transcript to get AI-powered analysis
                    </CardDescription>
                )}
            </CardHeader>
            {expanded && (
                <CardContent className="space-y-4">
                    <CardDescription>
                        Paste a deposition transcript below, then click Analyze to generate an AI-powered analysis.
                    </CardDescription>
                    <textarea
                        className="w-full min-h-[200px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-y"
                        placeholder="Paste deposition transcript here..."
                        value={transcript}
                        onChange={(e) => setTranscript(e.target.value)}
                        disabled={depositionMutation.isPending}
                    />
                    <div className="flex items-center gap-3">
                        <Button
                            onClick={handleAnalyze}
                            disabled={depositionMutation.isPending || !transcript.trim()}
                            size="sm"
                            className="gap-1.5"
                        >
                            {depositionMutation.isPending ? (
                                <>
                                    <LoadingSpinner />
                                    Analyzing...
                                </>
                            ) : (
                                "Analyze"
                            )}
                        </Button>
                        {transcript.trim() && (
                            <span className="text-xs text-muted-foreground">
                                {transcript.trim().split(/\s+/).length} words
                            </span>
                        )}
                    </div>
                    {analysisResult && (
                        <div className="mt-4 rounded-lg border bg-muted/30 p-4">
                            <div className="flex items-center justify-between mb-3">
                                <h4 className="text-sm font-semibold">Analysis Result</h4>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="text-xs h-7"
                                    onClick={() => setAnalysisResult(null)}
                                >
                                    Clear
                                </Button>
                            </div>
                            <MarkdownResult content={analysisResult} />
                        </div>
                    )}
                </CardContent>
            )}
        </Card>
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

    // On-demand result dialog state
    const [onDemandDialog, setOnDemandDialog] = useState<{
        open: boolean;
        title: string;
        witnessName: string;
        content: string;
    }>({ open: false, title: "", witnessName: "", content: "" });

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
            toast.success(`${label} plan generated for ${witnessName}`);
        } catch (err) {
            const label = examType === "cross" ? "cross-examination" : "direct-examination";
            toast.error(`Failed to generate ${label}`, {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        } finally {
            setGeneratingExam(null);
        }
    };

    // ---- On-Demand: Witness Prep ----

    const witnessPrepMutation = useMutation({
        mutationFn: (vars: { witnessIndex: number; witnessName: string }) =>
            api.post<OnDemandResult>(
                `/cases/${caseId}/ondemand/witness-prep`,
                { prep_id: activePrepId, witness_index: vars.witnessIndex },
                { getToken },
            ),
        onSuccess: (data, vars) => {
            const text = extractResultText(data);
            setOnDemandDialog({
                open: true,
                title: "Witness Prep",
                witnessName: vars.witnessName,
                content: text,
            });
            toast.success(`Witness prep generated for ${vars.witnessName}`);
        },
        onError: (err: Error) => {
            toast.error("Failed to generate witness prep", { description: err.message });
        },
    });

    // ---- On-Demand: Interview Plan ----

    const interviewPlanMutation = useMutation({
        mutationFn: (vars: { witnessIndex: number; witnessName: string }) =>
            api.post<OnDemandResult>(
                `/cases/${caseId}/ondemand/interview-plan`,
                { prep_id: activePrepId, witness_index: vars.witnessIndex },
                { getToken },
            ),
        onSuccess: (data, vars) => {
            const text = extractResultText(data);
            setOnDemandDialog({
                open: true,
                title: "Interview Plan",
                witnessName: vars.witnessName,
                content: text,
            });
            toast.success(`Interview plan generated for ${vars.witnessName}`);
        },
        onError: (err: Error) => {
            toast.error("Failed to generate interview plan", { description: err.message });
        },
    });

    // ---- Derived exam data ----

    const crossPlan = prepStateQuery.data?.cross_examination_plan;
    const directPlan = prepStateQuery.data?.direct_examination_plan;

    // Check if any on-demand mutation is currently running for a given witness
    const isOnDemandPending = (witnessIndex: number) => {
        return (
            (witnessPrepMutation.isPending && witnessPrepMutation.variables?.witnessIndex === witnessIndex) ||
            (interviewPlanMutation.isPending && interviewPlanMutation.variables?.witnessIndex === witnessIndex)
        );
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
            renderItem={(witness, i) => {
                const crossEntries = findExamEntries(crossPlan, witness.name);
                const directEntries = findExamEntries(directPlan, witness.name);
                const crossGenKey = `${witness.name}-cross`;
                const directGenKey = `${witness.name}-direct`;
                const isGeneratingCross = generatingExam === crossGenKey;
                const isGeneratingDirect = generatingExam === directGenKey;
                const isGeneratingAny = generatingExam !== null;
                const isPrepPending = witnessPrepMutation.isPending && witnessPrepMutation.variables?.witnessIndex === i;
                const isInterviewPending = interviewPlanMutation.isPending && interviewPlanMutation.variables?.witnessIndex === i;

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
                                    {/* On-Demand AI buttons */}
                                    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="text-xs h-7 gap-1"
                                            disabled={isOnDemandPending(i)}
                                            onClick={() =>
                                                witnessPrepMutation.mutate({ witnessIndex: i, witnessName: witness.name })
                                            }
                                        >
                                            {isPrepPending ? (
                                                <>
                                                    <LoadingSpinner />
                                                    Prep...
                                                </>
                                            ) : (
                                                "Prep"
                                            )}
                                        </Button>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="text-xs h-7 gap-1"
                                            disabled={isOnDemandPending(i)}
                                            onClick={() =>
                                                interviewPlanMutation.mutate({ witnessIndex: i, witnessName: witness.name })
                                            }
                                        >
                                            {isInterviewPending ? (
                                                <>
                                                    <LoadingSpinner />
                                                    Interview...
                                                </>
                                            ) : (
                                                "Interview"
                                            )}
                                        </Button>
                                    </div>
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

            {/* Deposition Analysis Section */}
            {activePrepId && (
                <DepositionAnalysisSection
                    caseId={caseId}
                    prepId={activePrepId}
                    getToken={getToken}
                />
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

            {/* On-Demand Result Dialog */}
            <OnDemandResultDialog
                open={onDemandDialog.open}
                onOpenChange={(open) => setOnDemandDialog((prev) => ({ ...prev, open }))}
                title={onDemandDialog.title}
                witnessName={onDemandDialog.witnessName}
                content={onDemandDialog.content}
            />
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
