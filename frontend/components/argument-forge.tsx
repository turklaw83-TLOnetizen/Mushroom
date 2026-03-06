"use client";

import { useState, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { toast } from "sonner";
import {
    Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import type {
    LegalIssue, ForgeArgument, OppositionArgument, CounterMatrixEntry,
    OralSegment, ScoredArgument, ArgumentSession,
} from "@/types/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ArgumentForgeProps {
    caseId: string;
    prepId: string | null;
}

type ForgeStep = "issues" | "arguments" | "steelman" | "matrix" | "oral" | "scoring" | "export";

interface OralPrepResult {
    segments: OralSegment[];
    total_minutes: number;
    opening_hook: string;
    closing_punch: string;
}

interface ScoreResult {
    scored_arguments: ScoredArgument[];
    overall_confidence: number;
    strongest_argument: string;
    weakest_argument: string;
}

interface ExportResult {
    doc_type: string;
    doc_subtype: string;
    document_title: string;
    outline: Array<{ section_num: string; title: string; description: string }>;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STEPS: { key: ForgeStep; label: string }[] = [
    { key: "issues", label: "Issues" },
    { key: "arguments", label: "Arguments" },
    { key: "steelman", label: "Opposition" },
    { key: "matrix", label: "Counter-Matrix" },
    { key: "oral", label: "Oral Prep" },
    { key: "scoring", label: "Scoring" },
    { key: "export", label: "Export" },
];

const FW_COLORS: Record<string, string> = {
    constitutional: "bg-blue-500/20 text-blue-300 border-blue-500/30",
    statutory: "bg-indigo-500/20 text-indigo-300 border-indigo-500/30",
    common_law: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    policy: "bg-green-500/20 text-green-300 border-green-500/30",
    equity: "bg-purple-500/20 text-purple-300 border-purple-500/30",
};

const PRIORITY_COLORS: Record<string, string> = {
    high: "bg-red-500/20 text-red-300 border-red-500/30",
    medium: "bg-amber-500/20 text-amber-300 border-amber-500/30",
    low: "bg-blue-500/20 text-blue-300 border-blue-500/30",
};

const ADV_COLORS: Record<string, string> = {
    ours: "bg-green-500/20 text-green-300 border-green-500/30",
    theirs: "bg-red-500/20 text-red-300 border-red-500/30",
    neutral: "bg-amber-500/20 text-amber-300 border-amber-500/30",
};

const TIMELINE_HUES = [
    "bg-indigo-500/60", "bg-blue-500/60", "bg-purple-500/60",
    "bg-violet-500/60", "bg-cyan-500/60", "bg-teal-500/60",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function barColor(v: number) {
    if (v >= 80) return "bg-green-500";
    if (v >= 60) return "bg-yellow-500";
    return "bg-red-500";
}

function txtColor(v: number) {
    if (v >= 80) return "text-green-400";
    if (v >= 60) return "text-yellow-400";
    return "text-red-400";
}

function StrengthBar({ value, label }: { value: number; label: string }) {
    return (
        <div className="flex items-center gap-2" aria-label={label}>
            <div className="flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
                <div className={`h-full rounded-full transition-all ${barColor(value)}`} style={{ width: `${value}%` }} />
            </div>
            <span className={`text-[10px] font-medium w-7 text-right ${txtColor(value)}`}>{value}%</span>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ArgumentForge({ caseId, prepId }: ArgumentForgeProps) {
    const { getToken } = useAuth();

    const [step, setStep] = useState<ForgeStep>("issues");
    const [issues, setIssues] = useState<LegalIssue[]>([]);
    const [selectedIssue, setSelectedIssue] = useState<LegalIssue | null>(null);
    const [arguments_, setArguments] = useState<ForgeArgument[]>([]);
    const [opposition, setOpposition] = useState<OppositionArgument[]>([]);
    const [matrix, setMatrix] = useState<CounterMatrixEntry[]>([]);
    const [oralPrep, setOralPrep] = useState<OralPrepResult | null>(null);
    const [scores, setScores] = useState<ScoreResult | null>(null);
    const [exportResult, setExportResult] = useState<ExportResult | null>(null);
    const [customFocus, setCustomFocus] = useState("");
    const [timeLimit, setTimeLimit] = useState(15);
    const [expandedArgs, setExpandedArgs] = useState<Set<number>>(new Set());
    const [sessionName, setSessionName] = useState("");
    const [showSessionInput, setShowSessionInput] = useState(false);

    if (!prepId) {
        return (
            <Card className="glass-card" role="alert">
                <CardContent className="py-12 text-center">
                    <p className="text-muted-foreground text-sm">Create a preparation first to use the Argument Forge.</p>
                </CardContent>
            </Card>
        );
    }

    const stepIndex = STEPS.findIndex((s) => s.key === step);
    const goBack = useCallback(() => {
        const idx = STEPS.findIndex((s) => s.key === step);
        if (idx > 0) setStep(STEPS[idx - 1].key);
    }, [step]);

    const post = <T,>(path: string, body: unknown) =>
        api.post<T>(`/cases/${caseId}/argument-forge${path}`, { prep_id: prepId, ...(body as Record<string, unknown>) }, { getToken });

    // -- Mutations --

    const identifyMut = useMutationWithToast<{ custom_focus: string }, { issues: LegalIssue[] }>({
        mutationFn: (input) => post("/identify-issues", input),
        successMessage: "Issues identified",
        onSuccess: (r) => setIssues(r.issues || []),
    });

    const generateMut = useMutationWithToast<{ issue: LegalIssue; frameworks: string[] }, { arguments: ForgeArgument[] }>({
        mutationFn: (input) => post("/generate-arguments", input),
        successMessage: "Arguments generated",
        onSuccess: (r) => setArguments(r.arguments || []),
    });

    const steelmanMut = useMutationWithToast<{ our_arguments: ForgeArgument[] }, { opposition_arguments: OppositionArgument[] }>({
        mutationFn: (input) => post("/steelman", input),
        successMessage: "Opposition arguments generated",
        onSuccess: (r) => setOpposition(r.opposition_arguments || []),
    });

    const matrixMut = useMutationWithToast<
        { our_arguments: ForgeArgument[]; opponent_arguments: OppositionArgument[] },
        { matrix: CounterMatrixEntry[] }
    >({
        mutationFn: (input) => post("/counter-matrix", input),
        successMessage: "Counter-matrix built",
        onSuccess: (r) => setMatrix(r.matrix || []),
    });

    const oralMut = useMutationWithToast<{ arguments: ForgeArgument[]; time_limit: number }, OralPrepResult>({
        mutationFn: (input) => post("/oral-prep", input),
        successMessage: "Oral arguments prepared",
        onSuccess: (r) => setOralPrep(r),
    });

    const scoreMut = useMutationWithToast<{ arguments: ForgeArgument[] }, ScoreResult>({
        mutationFn: (input) => post("/score", input),
        successMessage: "Arguments scored",
        onSuccess: (r) => setScores(r),
    });

    const exportMut = useMutationWithToast<
        { arguments: ForgeArgument[]; counter_matrix: CounterMatrixEntry[] },
        ExportResult
    >({
        mutationFn: (input) => api.post(`/cases/${caseId}/argument-forge/export-skeleton`, input, { getToken }),
        successMessage: "Export skeleton generated",
        onSuccess: (r) => setExportResult(r),
    });

    const saveSessionMut = useMutationWithToast<{ name: string; data: Record<string, unknown> }, { status: string; id: string }>({
        mutationFn: (input) => api.post(`/cases/${caseId}/argument-forge/sessions`, input, { getToken }),
        successMessage: "Session saved",
        invalidateKeys: [["forge-sessions", caseId]],
        onSuccess: () => { setShowSessionInput(false); setSessionName(""); },
    });

    const deleteSessionMut = useMutationWithToast<{ sessionId: string }, { status: string; id: string }>({
        mutationFn: (input) => api.delete(`/cases/${caseId}/argument-forge/sessions/${input.sessionId}`, { getToken }),
        successMessage: "Session deleted",
        invalidateKeys: [["forge-sessions", caseId]],
    });

    const saveDraftMut = useMutationWithToast<{ outline: ExportResult }, { status: string }>({
        mutationFn: (input) => api.post(`/documents/drafts/${caseId}/full`, input.outline, { getToken }),
        successMessage: "Draft saved to Document Drafter",
    });

    // -- Queries --

    const sessionsQuery = useQuery({
        queryKey: ["forge-sessions", caseId],
        queryFn: () => api.get<{ sessions: ArgumentSession[] }>(`/cases/${caseId}/argument-forge/sessions`, { getToken }),
        enabled: !!prepId,
    });

    // -- Handlers --

    function handleSelectIssue(issue: LegalIssue) {
        setSelectedIssue(issue);
        generateMut.mutate({ issue, frameworks: issue.frameworks });
        setStep("arguments");
    }

    function handleLoadSession(s: ArgumentSession) {
        if (s.issues) setIssues(s.issues);
        if (s.arguments) setArguments(s.arguments);
        if (s.opposition) setOpposition(s.opposition);
        if (s.counter_matrix) setMatrix(s.counter_matrix);
        if (s.oral_prep) {
            setOralPrep({
                segments: s.oral_prep,
                total_minutes: s.oral_prep.reduce((a, x) => a + x.duration_minutes, 0),
                opening_hook: "", closing_punch: "",
            });
        }
        if (s.scores) {
            setScores({
                scored_arguments: s.scores,
                overall_confidence: s.overall_confidence ?? 0,
                strongest_argument: "", weakest_argument: "",
            });
        }
        toast.success(`Loaded session: ${s.name}`);
    }

    function toggleExpand(i: number) {
        setExpandedArgs((prev) => {
            const next = new Set(prev);
            if (next.has(i)) next.delete(i); else next.add(i);
            return next;
        });
    }

    function saveCurrentSession() {
        if (!sessionName.trim()) { toast.error("Enter a session name"); return; }
        saveSessionMut.mutate({
            name: sessionName.trim(),
            data: { issues, selectedIssue, arguments: arguments_, opposition, matrix, oralPrep, scores, step },
        });
    }

    function BackBtn({ label }: { label: string }) {
        return <Button variant="outline" size="sm" onClick={goBack} aria-label={label}>&larr; Back</Button>;
    }

    // -- Step Indicator --

    function StepNav() {
        return (
            <nav aria-label="Argument Forge progress" className="mb-6">
                <ol className="flex items-center gap-1 overflow-x-auto pb-2">
                    {STEPS.map((s, i) => {
                        const cur = s.key === step, past = i < stepIndex;
                        return (
                            <li key={s.key} className="flex items-center gap-1">
                                {i > 0 && <div className={`h-px w-4 sm:w-8 ${past ? "bg-indigo-500" : "bg-white/10"}`} aria-hidden="true" />}
                                <button
                                    type="button" onClick={() => past && setStep(s.key)} disabled={!past && !cur}
                                    aria-current={cur ? "step" : undefined}
                                    aria-label={`Step ${i + 1}: ${s.label}${cur ? " (current)" : ""}${past ? " (completed)" : ""}`}
                                    className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors whitespace-nowrap ${
                                        cur ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/40"
                                        : past ? "bg-white/5 text-white/60 hover:bg-white/10 cursor-pointer"
                                        : "bg-white/5 text-white/30 cursor-default"}`}
                                >
                                    <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] ${
                                        cur ? "bg-indigo-500 text-white" : past ? "bg-white/20 text-white/70" : "bg-white/10 text-white/30"}`}
                                        aria-hidden="true">
                                        {past ? "\u2713" : i + 1}
                                    </span>
                                    {s.label}
                                </button>
                            </li>
                        );
                    })}
                </ol>
            </nav>
        );
    }

    // -- Step 1: Issue Identification --

    function IssuesStep() {
        return (
            <div className="space-y-4" role="region" aria-label="Issue identification">
                <Card className="glass-card">
                    <CardHeader className="pb-3"><CardTitle className="text-base">Identify Legal Issues</CardTitle></CardHeader>
                    <CardContent className="space-y-3">
                        <div>
                            <label htmlFor="custom-focus" className="text-xs text-muted-foreground mb-1 block">
                                Custom focus area (optional)
                            </label>
                            <Input id="custom-focus" placeholder="e.g., Fourth Amendment search and seizure issues"
                                value={customFocus} onChange={(e) => setCustomFocus(e.target.value)} aria-describedby="focus-hint" />
                            <p id="focus-hint" className="text-[11px] text-muted-foreground mt-1">
                                Leave blank to automatically identify all relevant issues from case documents.
                            </p>
                        </div>
                        <Button onClick={() => identifyMut.mutate({ custom_focus: customFocus })}
                            disabled={identifyMut.isPending} aria-busy={identifyMut.isPending}>
                            {identifyMut.isPending ? "Identifying..." : "Identify Issues"}
                        </Button>
                    </CardContent>
                </Card>
                {identifyMut.isPending && (
                    <div className="space-y-3">{[1, 2, 3].map((n) => <Skeleton key={n} className="h-28 rounded-lg" />)}</div>
                )}
                {issues.length > 0 && (
                    <div className="space-y-3" role="list" aria-label="Identified legal issues">
                        {issues.map((issue) => (
                            <Card key={issue.id} className="glass-card" role="listitem">
                                <CardContent className="pt-4 pb-4 space-y-2">
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="flex-1 min-w-0">
                                            <h4 className="text-sm font-semibold text-white">{issue.title}</h4>
                                            <p className="text-xs text-muted-foreground mt-1">{issue.description}</p>
                                        </div>
                                        <Badge variant="outline" className={`shrink-0 text-[10px] ${PRIORITY_COLORS[issue.priority] ?? ""}`}>
                                            {issue.priority}
                                        </Badge>
                                    </div>
                                    <div className="flex flex-wrap gap-1.5">
                                        {issue.frameworks.map((fw) => (
                                            <Badge key={fw} variant="outline" className={`text-[10px] ${FW_COLORS[fw] ?? "bg-white/10 text-white/60"}`}>
                                                {fw.replace(/_/g, " ")}
                                            </Badge>
                                        ))}
                                    </div>
                                    <Button size="sm" onClick={() => handleSelectIssue(issue)} disabled={generateMut.isPending}
                                        aria-label={`Select issue: ${issue.title} and generate arguments`}>
                                        Select &amp; Generate Arguments
                                    </Button>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )}
            </div>
        );
    }

    // -- Step 2: Framework Generation --

    function ArgumentsStep() {
        return (
            <div className="space-y-4" role="region" aria-label="Argument generation">
                {selectedIssue && (
                    <Card className="glass-card border-indigo-500/20">
                        <CardContent className="pt-4 pb-3">
                            <p className="text-xs text-muted-foreground">Selected Issue</p>
                            <h4 className="text-sm font-semibold text-white mt-0.5">{selectedIssue.title}</h4>
                            <p className="text-xs text-muted-foreground mt-1">{selectedIssue.description}</p>
                        </CardContent>
                    </Card>
                )}
                <div className="flex items-center gap-2">
                    <BackBtn label="Go back to issue identification" />
                    <Button size="sm"
                        onClick={() => selectedIssue && generateMut.mutate({ issue: selectedIssue, frameworks: selectedIssue.frameworks })}
                        disabled={generateMut.isPending || !selectedIssue} aria-busy={generateMut.isPending}>
                        {generateMut.isPending ? "Generating..." : "Regenerate Arguments"}
                    </Button>
                </div>
                {generateMut.isPending && (
                    <div className="space-y-3">{[1, 2, 3].map((n) => <Skeleton key={n} className="h-40 rounded-lg" />)}</div>
                )}
                {arguments_.length > 0 && (
                    <>
                        <div className="space-y-3" role="list" aria-label="Generated arguments by framework">
                            {arguments_.map((arg, idx) => (
                                <Card key={idx} className="glass-card" role="listitem">
                                    <CardContent className="pt-4 pb-4 space-y-3">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="outline" className={`text-[10px] ${FW_COLORS[arg.framework] ?? "bg-white/10 text-white/60"}`}>
                                                {arg.framework.replace(/_/g, " ")}
                                            </Badge>
                                            <span className={`text-xs font-medium ${txtColor(arg.strength)}`}>{arg.strength}%</span>
                                        </div>
                                        <p className="text-sm text-white font-medium">{arg.thesis}</p>
                                        <StrengthBar value={arg.strength} label={`Strength: ${arg.strength}%`} />
                                        <button type="button" onClick={() => toggleExpand(idx)}
                                            className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                                            aria-expanded={expandedArgs.has(idx)} aria-controls={`arg-details-${idx}`}>
                                            {expandedArgs.has(idx) ? "Hide Details" : "Show Details"}
                                        </button>
                                        {expandedArgs.has(idx) && (
                                            <div id={`arg-details-${idx}`} className="space-y-2 border-t border-white/5 pt-3">
                                                <div>
                                                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Reasoning</p>
                                                    <p className="text-xs text-white/80 mt-0.5">{arg.reasoning}</p>
                                                </div>
                                                <div>
                                                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Supporting Law</p>
                                                    <p className="text-xs text-white/80 mt-0.5">{arg.supporting_law}</p>
                                                </div>
                                                <div>
                                                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Supporting Facts</p>
                                                    <p className="text-xs text-white/80 mt-0.5">{arg.supporting_facts}</p>
                                                </div>
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                        <div className="flex justify-end">
                            <Button onClick={() => { steelmanMut.mutate({ our_arguments: arguments_ }); setStep("steelman"); }}
                                disabled={steelmanMut.isPending} aria-label="Proceed to steelman opposition arguments">
                                Steelman Opposition &rarr;
                            </Button>
                        </div>
                    </>
                )}
            </div>
        );
    }

    // -- Step 3: Opposition Steelman --

    function SteelmanStep() {
        return (
            <div className="space-y-4" role="region" aria-label="Opposition steelman">
                <div className="flex items-center gap-2">
                    <BackBtn label="Go back to arguments" />
                    <Button size="sm" onClick={() => steelmanMut.mutate({ our_arguments: arguments_ })}
                        disabled={steelmanMut.isPending} aria-busy={steelmanMut.isPending}>
                        {steelmanMut.isPending ? "Generating..." : "Regenerate Opposition"}
                    </Button>
                </div>
                {steelmanMut.isPending && (
                    <div className="space-y-3">{[1, 2, 3].map((n) => <Skeleton key={n} className="h-32 rounded-lg" />)}</div>
                )}
                {opposition.length > 0 && (
                    <>
                        <div className="space-y-3" role="list" aria-label="Opposition arguments">
                            {opposition.map((opp, idx) => (
                                <Card key={idx} className="glass-card border-red-500/10" role="listitem">
                                    <CardContent className="pt-4 pb-4 space-y-2">
                                        <p className="text-[10px] text-muted-foreground uppercase tracking-wide">
                                            Responding to Argument #{opp.responding_to}
                                        </p>
                                        <p className="text-sm text-white font-semibold">{opp.position}</p>
                                        <p className="text-xs text-white/70">{opp.reasoning}</p>
                                        <div>
                                            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Legal Basis</p>
                                            <p className="text-xs text-white/70 mt-0.5">{opp.legal_basis}</p>
                                        </div>
                                        <StrengthBar value={opp.strength} label={`Opposition strength: ${opp.strength}%`} />
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                        <div className="flex justify-end">
                            <Button onClick={() => { matrixMut.mutate({ our_arguments: arguments_, opponent_arguments: opposition }); setStep("matrix"); }}
                                disabled={matrixMut.isPending} aria-label="Proceed to build counter-matrix">
                                Build Counter-Matrix &rarr;
                            </Button>
                        </div>
                    </>
                )}
            </div>
        );
    }

    // -- Step 4: Counter-Matrix --

    function MatrixStep() {
        return (
            <div className="space-y-4" role="region" aria-label="Counter-matrix">
                <div className="flex items-center gap-2">
                    <BackBtn label="Go back to opposition steelman" />
                    <Button size="sm"
                        onClick={() => matrixMut.mutate({ our_arguments: arguments_, opponent_arguments: opposition })}
                        disabled={matrixMut.isPending} aria-busy={matrixMut.isPending}>
                        {matrixMut.isPending ? "Building..." : "Rebuild Matrix"}
                    </Button>
                </div>
                {matrixMut.isPending && <Skeleton className="h-64 rounded-lg" />}
                {matrix.length > 0 && (
                    <>
                        <Card className="glass-card overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full text-xs" role="table" aria-label="Counter-matrix comparison">
                                    <thead>
                                        <tr className="border-b border-white/10">
                                            <th scope="col" className="text-left px-3 py-2 text-muted-foreground font-medium">Our Argument</th>
                                            <th scope="col" className="text-left px-3 py-2 text-muted-foreground font-medium">Their Counter</th>
                                            <th scope="col" className="text-left px-3 py-2 text-muted-foreground font-medium">Our Rebuttal</th>
                                            <th scope="col" className="text-center px-3 py-2 text-muted-foreground font-medium">Advantage</th>
                                            <th scope="col" className="text-center px-3 py-2 text-muted-foreground font-medium w-28">Confidence</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {matrix.map((entry, idx) => (
                                            <tr key={idx} className="border-b border-white/5 hover:bg-white/[0.02]">
                                                <td className="px-3 py-3 text-white/80 max-w-[200px]">{entry.our_argument}</td>
                                                <td className="px-3 py-3 text-white/70 max-w-[200px]">{entry.their_counter}</td>
                                                <td className="px-3 py-3 text-white/80 max-w-[200px]">{entry.our_rebuttal}</td>
                                                <td className="px-3 py-3 text-center">
                                                    <Badge variant="outline" className={`text-[10px] ${ADV_COLORS[entry.net_advantage] ?? ""}`}>
                                                        {entry.net_advantage}
                                                    </Badge>
                                                </td>
                                                <td className="px-3 py-3">
                                                    <StrengthBar value={entry.confidence} label={`Confidence: ${entry.confidence}%`} />
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </Card>
                        <div className="flex justify-end">
                            <Button onClick={() => { oralMut.mutate({ arguments: arguments_, time_limit: timeLimit }); setStep("oral"); }}
                                disabled={oralMut.isPending} aria-label="Proceed to oral argument preparation">
                                Prepare Oral Arguments &rarr;
                            </Button>
                        </div>
                    </>
                )}
            </div>
        );
    }

    // -- Step 5: Oral Prep --

    function OralStep() {
        return (
            <div className="space-y-4" role="region" aria-label="Oral argument preparation">
                <BackBtn label="Go back to counter-matrix" />
                <Card className="glass-card">
                    <CardContent className="pt-4 pb-4 space-y-3">
                        <div className="flex items-end gap-3">
                            <div className="flex-1 max-w-[200px]">
                                <label htmlFor="time-limit" className="text-xs text-muted-foreground mb-1 block">
                                    Time limit (minutes)
                                </label>
                                <Input id="time-limit" type="number" min={1} max={60} value={timeLimit}
                                    onChange={(e) => setTimeLimit(Math.max(1, Math.min(60, parseInt(e.target.value) || 15)))}
                                    aria-describedby="time-limit-hint" />
                                <p id="time-limit-hint" className="text-[10px] text-muted-foreground mt-1">
                                    Allocate between 1 and 60 minutes.
                                </p>
                            </div>
                            <Button onClick={() => oralMut.mutate({ arguments: arguments_, time_limit: timeLimit })}
                                disabled={oralMut.isPending} aria-busy={oralMut.isPending}>
                                {oralMut.isPending ? "Preparing..." : "Prepare Oral Arguments"}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
                {oralMut.isPending && (
                    <div className="space-y-3">
                        <Skeleton className="h-20 rounded-lg" />
                        <Skeleton className="h-40 rounded-lg" />
                        <Skeleton className="h-20 rounded-lg" />
                    </div>
                )}
                {oralPrep && (
                    <>
                        <Card className="glass-card border-blue-500/20">
                            <CardContent className="pt-4 pb-4">
                                <p className="text-[10px] text-blue-400 uppercase tracking-wide font-medium">Opening Hook</p>
                                <p className="text-sm text-white mt-1">{oralPrep.opening_hook}</p>
                            </CardContent>
                        </Card>
                        <div className="flex gap-1 h-6 rounded overflow-hidden" role="img"
                            aria-label={`Oral argument timeline: ${oralPrep.total_minutes} minutes across ${oralPrep.segments.length} segments`}>
                            {oralPrep.segments.map((seg, idx) => {
                                const widthPct = oralPrep.total_minutes > 0 ? (seg.duration_minutes / oralPrep.total_minutes) * 100 : 0;
                                return (
                                    <div key={idx}
                                        className={`${TIMELINE_HUES[idx % TIMELINE_HUES.length]} flex items-center justify-center text-[9px] text-white/80 font-medium truncate px-1`}
                                        style={{ width: `${widthPct}%` }}
                                        title={`${seg.topic}: ${seg.duration_minutes}min`}>
                                        {seg.duration_minutes}m
                                    </div>
                                );
                            })}
                        </div>
                        <div className="space-y-3" role="list" aria-label="Oral argument segments">
                            {oralPrep.segments.map((seg, idx) => (
                                <Card key={idx} className="glass-card" role="listitem">
                                    <CardContent className="pt-4 pb-4 space-y-2">
                                        <div className="flex items-center justify-between">
                                            <h4 className="text-sm font-semibold text-white">{seg.topic}</h4>
                                            <Badge variant="outline" className="text-[10px] bg-indigo-500/20 text-indigo-300 border-indigo-500/30">
                                                {seg.duration_minutes} min
                                            </Badge>
                                        </div>
                                        <ul className="space-y-1 pl-3" aria-label={`Key points for ${seg.topic}`}>
                                            {seg.key_points.map((pt, pi) => (
                                                <li key={pi} className="text-xs text-white/70 list-disc">{pt}</li>
                                            ))}
                                        </ul>
                                        {seg.transitions && (
                                            <div className="border-t border-white/5 pt-2 mt-2">
                                                <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Transition</p>
                                                <p className="text-xs text-white/60 italic mt-0.5">{seg.transitions}</p>
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                        <Card className="glass-card border-indigo-500/20">
                            <CardContent className="pt-4 pb-4">
                                <p className="text-[10px] text-indigo-400 uppercase tracking-wide font-medium">Closing Punch</p>
                                <p className="text-sm text-white mt-1">{oralPrep.closing_punch}</p>
                            </CardContent>
                        </Card>
                        <div className="flex items-center justify-between">
                            <p className="text-xs text-muted-foreground">
                                Total time: <span className="text-white font-medium">{oralPrep.total_minutes} minutes</span>
                            </p>
                            <Button onClick={() => { scoreMut.mutate({ arguments: arguments_ }); setStep("scoring"); }}
                                disabled={scoreMut.isPending} aria-label="Proceed to score arguments">
                                Score Arguments &rarr;
                            </Button>
                        </div>
                    </>
                )}
            </div>
        );
    }

    // -- Step 6: Scoring --

    function ScoringStep() {
        return (
            <div className="space-y-4" role="region" aria-label="Argument scoring">
                <div className="flex items-center gap-2">
                    <BackBtn label="Go back to oral prep" />
                    <Button size="sm" onClick={() => scoreMut.mutate({ arguments: arguments_ })}
                        disabled={scoreMut.isPending} aria-busy={scoreMut.isPending}>
                        {scoreMut.isPending ? "Scoring..." : "Rescore Arguments"}
                    </Button>
                </div>
                {scoreMut.isPending && (
                    <div className="space-y-3">
                        <Skeleton className="h-24 rounded-lg" />
                        <Skeleton className="h-48 rounded-lg" />
                    </div>
                )}
                {scores && (
                    <>
                        <Card className="glass-card">
                            <CardContent className="pt-5 pb-5">
                                <div className="flex flex-col items-center gap-3">
                                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Overall Confidence</p>
                                    <p className={`text-5xl font-bold ${txtColor(scores.overall_confidence)}`}
                                        aria-label={`Overall confidence: ${scores.overall_confidence}%`}>
                                        {scores.overall_confidence}%
                                    </p>
                                    <Progress value={scores.overall_confidence} className="w-48 h-2" aria-hidden="true" />
                                </div>
                            </CardContent>
                        </Card>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <Card className="glass-card border-green-500/20">
                                <CardContent className="pt-4 pb-4">
                                    <p className="text-[10px] text-green-400 uppercase tracking-wide font-medium">Strongest Argument</p>
                                    <p className="text-sm text-white mt-1">{scores.strongest_argument}</p>
                                </CardContent>
                            </Card>
                            <Card className="glass-card border-red-500/20">
                                <CardContent className="pt-4 pb-4">
                                    <p className="text-[10px] text-red-400 uppercase tracking-wide font-medium">Weakest Argument</p>
                                    <p className="text-sm text-white mt-1">{scores.weakest_argument}</p>
                                </CardContent>
                            </Card>
                        </div>
                        <div className="space-y-3" role="list" aria-label="Ranked scored arguments">
                            {scores.scored_arguments.slice().sort((a, b) => b.win_probability - a.win_probability).map((sa, idx) => (
                                <Card key={idx} className="glass-card" role="listitem">
                                    <CardContent className="pt-4 pb-4 space-y-2">
                                        <p className="text-sm text-white">{sa.argument}</p>
                                        <div className="flex items-center gap-2" aria-label={`Win probability: ${sa.win_probability}%`}>
                                            <span className="text-[10px] text-muted-foreground w-20 shrink-0">Win Prob.</span>
                                            <div className="flex-1 h-2 rounded-full bg-white/10 overflow-hidden">
                                                <div className={`h-full rounded-full ${barColor(sa.win_probability)}`}
                                                    style={{ width: `${sa.win_probability}%` }} />
                                            </div>
                                            <span className={`text-xs font-medium w-9 text-right ${txtColor(sa.win_probability)}`}>
                                                {sa.win_probability}%
                                            </span>
                                        </div>
                                        {sa.risk_factors.length > 0 && (
                                            <div className="flex flex-wrap gap-1" aria-label="Risk factors">
                                                {sa.risk_factors.map((rf, ri) => (
                                                    <Badge key={ri} variant="outline"
                                                        className="text-[10px] bg-red-500/10 text-red-300 border-red-500/20">
                                                        {rf}
                                                    </Badge>
                                                ))}
                                            </div>
                                        )}
                                        <p className="text-xs text-white/80">
                                            <span className="font-semibold">Recommendation:</span> {sa.recommendation}
                                        </p>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                        <div className="flex justify-end">
                            <Button onClick={() => { exportMut.mutate({ arguments: arguments_, counter_matrix: matrix }); setStep("export"); }}
                                disabled={exportMut.isPending} aria-label="Proceed to export">
                                Export to Document Drafter &rarr;
                            </Button>
                        </div>
                    </>
                )}
            </div>
        );
    }

    // -- Step 7: Export Bridge --

    function ExportStep() {
        return (
            <div className="space-y-4" role="region" aria-label="Export to document drafter">
                <div className="flex items-center gap-2">
                    <BackBtn label="Go back to scoring" />
                    <Button size="sm" onClick={() => exportMut.mutate({ arguments: arguments_, counter_matrix: matrix })}
                        disabled={exportMut.isPending} aria-busy={exportMut.isPending}>
                        {exportMut.isPending ? "Generating..." : "Regenerate Skeleton"}
                    </Button>
                </div>
                {exportMut.isPending && <Skeleton className="h-64 rounded-lg" />}
                {exportResult && (
                    <>
                        <Card className="glass-card border-indigo-500/20">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-base">{exportResult.document_title}</CardTitle>
                                <div className="flex gap-2 mt-1">
                                    <Badge variant="outline" className="text-[10px] bg-indigo-500/20 text-indigo-300 border-indigo-500/30">
                                        {exportResult.doc_type}
                                    </Badge>
                                    {exportResult.doc_subtype && (
                                        <Badge variant="outline" className="text-[10px]">{exportResult.doc_subtype}</Badge>
                                    )}
                                </div>
                            </CardHeader>
                            <CardContent className="space-y-2">
                                <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Outline Preview</p>
                                <ol className="space-y-1.5" aria-label="Document outline">
                                    {exportResult.outline.map((sec, idx) => (
                                        <li key={idx} className="text-xs text-white/80 flex gap-2">
                                            <span className="text-muted-foreground shrink-0 w-6 text-right">{sec.section_num}</span>
                                            <div>
                                                <span className="font-medium text-white">{sec.title}</span>
                                                {sec.description && <span className="text-white/50 ml-1">&mdash; {sec.description}</span>}
                                            </div>
                                        </li>
                                    ))}
                                </ol>
                            </CardContent>
                        </Card>
                        <div className="flex justify-end">
                            <Button onClick={() => saveDraftMut.mutate({ outline: exportResult })}
                                disabled={saveDraftMut.isPending} aria-busy={saveDraftMut.isPending}>
                                {saveDraftMut.isPending ? "Saving..." : "Save as Draft"}
                            </Button>
                        </div>
                    </>
                )}
            </div>
        );
    }

    // -- Session Management --

    function SessionManager() {
        const sessions = sessionsQuery.data?.sessions ?? [];
        return (
            <Card className="glass-card mt-8" role="region" aria-label="Session management">
                <CardHeader className="pb-3"><CardTitle className="text-sm">Sessions</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                    <div className="flex flex-wrap gap-2">
                        {showSessionInput ? (
                            <div className="flex items-center gap-2 w-full">
                                <Input placeholder="Session name" value={sessionName}
                                    onChange={(e) => setSessionName(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter") saveCurrentSession();
                                        if (e.key === "Escape") setShowSessionInput(false);
                                    }}
                                    className="flex-1 max-w-xs h-8 text-xs" aria-label="Session name" autoFocus />
                                <Button size="sm" onClick={saveCurrentSession}
                                    disabled={saveSessionMut.isPending} aria-busy={saveSessionMut.isPending}>
                                    {saveSessionMut.isPending ? "Saving..." : "Save"}
                                </Button>
                                <Button size="sm" variant="outline" onClick={() => setShowSessionInput(false)}>Cancel</Button>
                            </div>
                        ) : (
                            <Button size="sm" variant="outline" onClick={() => setShowSessionInput(true)}
                                aria-label="Save current session">
                                Save Session
                            </Button>
                        )}
                    </div>
                    {sessionsQuery.isLoading && (
                        <div className="space-y-2">
                            <Skeleton className="h-8 rounded" />
                            <Skeleton className="h-8 rounded" />
                        </div>
                    )}
                    {sessions.length > 0 && (
                        <div className="space-y-1.5" role="list" aria-label="Saved sessions">
                            {sessions.map((session) => (
                                <div key={session.id} role="listitem"
                                    className="flex items-center justify-between gap-2 rounded-lg bg-white/[0.03] px-3 py-2">
                                    <div className="flex-1 min-w-0">
                                        <p className="text-xs text-white font-medium truncate">{session.name}</p>
                                        <p className="text-[10px] text-muted-foreground">
                                            {new Date(session.created_at).toLocaleDateString()}
                                        </p>
                                    </div>
                                    <div className="flex gap-1.5 shrink-0">
                                        <Button size="sm" variant="outline" className="h-7 text-[10px] px-2"
                                            onClick={() => handleLoadSession(session)}
                                            aria-label={`Load session: ${session.name}`}>
                                            Load
                                        </Button>
                                        <Button size="sm" variant="outline"
                                            className="h-7 text-[10px] px-2 text-red-400 hover:text-red-300 border-red-500/20 hover:border-red-500/40"
                                            onClick={() => deleteSessionMut.mutate({ sessionId: session.id })}
                                            disabled={deleteSessionMut.isPending}
                                            aria-label={`Delete session: ${session.name}`}>
                                            Delete
                                        </Button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                    {!sessionsQuery.isLoading && sessions.length === 0 && (
                        <p className="text-xs text-muted-foreground">No saved sessions yet.</p>
                    )}
                </CardContent>
            </Card>
        );
    }

    // -- Main Render --

    const renderStep: Record<ForgeStep, () => React.JSX.Element> = {
        issues: IssuesStep,
        arguments: ArgumentsStep,
        steelman: SteelmanStep,
        matrix: MatrixStep,
        oral: OralStep,
        scoring: ScoringStep,
        export: ExportStep,
    };

    return (
        <div className="space-y-4" role="region" aria-label="Argument Forge wizard">
            <StepNav />
            {renderStep[step]()}
            <SessionManager />
        </div>
    );
}
