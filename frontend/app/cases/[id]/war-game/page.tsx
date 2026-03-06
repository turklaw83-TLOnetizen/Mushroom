// ---- AI War Game --------------------------------------------------------
// 5-round adversarial case simulation. Three views:
//   1. Dashboard  — past sessions list + new session creation
//   2. Active     — round-by-round attack/response/evaluation cycle
//   3. Report     — battle report with verdict, vulnerabilities, playbook
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { routes } from "@/lib/api-routes";
import { queryKeys } from "@/lib/query-keys";
import {
    formatDate,
    WAR_GAME_DIFFICULTY_COLORS,
    VERDICT_COLORS,
    SEVERITY_BADGE_COLORS,
} from "@/lib/constants";
import { usePrep } from "@/hooks/use-prep";
import { useRole } from "@/hooks/use-role";
import { StatusBadge } from "@/components/shared/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import type {
    WarGameSession,
    WarGameRound,
    WarGameReport,
} from "@/types/api";

// ---- Constants ----------------------------------------------------------

const ROUND_LABELS: Record<string, string> = {
    theory: "Theory Attack",
    evidence: "Evidence Challenge",
    witnesses: "Witness Assault",
    elements: "Element Gaps",
    jury: "Jury Verdict",
};

const ROUND_ORDER = ["theory", "evidence", "witnesses", "elements", "jury"];

const DIFFICULTY_DESCRIPTIONS: Record<string, { label: string; description: string }> = {
    standard: {
        label: "Standard",
        description: "Balanced opposing counsel. Tests core case viability with fair but probing attacks.",
    },
    aggressive: {
        label: "Aggressive",
        description: "Skilled adversary. Exploits every weakness, challenges marginal evidence, attacks witness credibility hard.",
    },
    ruthless: {
        label: "Ruthless",
        description: "Elite opposition. No-holds-barred assault on theory, evidence, and witnesses. Jury instructions skew hostile.",
    },
};

type ViewMode = "dashboard" | "active" | "report";

// ---- Score color helper -------------------------------------------------

function scoreColor(score: number): string {
    if (score >= 70) return "bg-green-500/15 text-green-400 border-green-500/30";
    if (score >= 40) return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    return "bg-red-500/15 text-red-400 border-red-500/30";
}

function scoreTextColor(score: number): string {
    if (score >= 70) return "text-green-400";
    if (score >= 40) return "text-amber-400";
    return "text-red-400";
}

// ---- Main Page ----------------------------------------------------------

export default function WarGamePage() {
    const params = useParams();
    const caseId = params.id as string;
    const { activePrepId, isLoading: prepLoading } = usePrep();
    const { getToken } = useAuth();
    const { canEdit } = useRole();
    const queryClient = useQueryClient();

    const [view, setView] = useState<ViewMode>("dashboard");
    const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [selectedDifficulty, setSelectedDifficulty] = useState<string>("standard");

    // ---- Data Fetching --------------------------------------------------

    const sessionsQuery = useQuery({
        queryKey: [...queryKeys.warGame.sessions(caseId, activePrepId ?? "")],
        queryFn: () =>
            api.get<WarGameSession[]>(
                routes.warGame.sessions(caseId, activePrepId!),
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    const sessionQuery = useQuery({
        queryKey: [...queryKeys.warGame.session(caseId, activePrepId ?? "", selectedSessionId ?? "")],
        queryFn: () =>
            api.get<WarGameSession>(
                routes.warGame.session(caseId, activePrepId!, selectedSessionId!),
                { getToken },
            ),
        enabled: !!activePrepId && !!selectedSessionId,
        refetchInterval: view === "active" ? 3000 : false,
    });

    // ---- Mutations ------------------------------------------------------

    const createSession = useMutation<WarGameSession, Error, string>({
        mutationFn: (difficulty) =>
            api.post<WarGameSession>(
                routes.warGame.sessions(caseId, activePrepId!),
                { difficulty },
                { getToken },
            ),
        onSuccess: (session) => {
            toast.success("War game created");
            queryClient.invalidateQueries({
                queryKey: [...queryKeys.warGame.sessions(caseId, activePrepId!)],
            });
            setSelectedSessionId(session.id);
            setView("active");
            setDialogOpen(false);
        },
        onError: (err) => {
            toast.error("Failed to create war game", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        },
    });

    const generateAttack = useMutation({
        mutationFn: (roundType: string) =>
            api.post<WarGameRound>(
                routes.warGame.attack(caseId, activePrepId!, selectedSessionId!, roundType),
                {},
                { getToken },
            ),
        onSuccess: () => {
            queryClient.invalidateQueries({
                queryKey: [...queryKeys.warGame.session(caseId, activePrepId!, selectedSessionId!)],
            });
        },
        onError: (err) => {
            toast.error("Failed to generate attack", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        },
    });

    const submitResponse = useMutation({
        mutationFn: ({ roundType, response }: { roundType: string; response: string }) =>
            api.post<WarGameRound>(
                routes.warGame.respond(caseId, activePrepId!, selectedSessionId!, roundType),
                { response },
                { getToken },
            ),
        onSuccess: () => {
            toast.success("Response submitted");
            queryClient.invalidateQueries({
                queryKey: [...queryKeys.warGame.session(caseId, activePrepId!, selectedSessionId!)],
            });
        },
        onError: (err) => {
            toast.error("Failed to submit response", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        },
    });

    const finalizeSession = useMutation({
        mutationFn: () =>
            api.post<WarGameSession>(
                routes.warGame.finalize(caseId, activePrepId!, selectedSessionId!),
                {},
                { getToken },
            ),
        onSuccess: () => {
            toast.success("Battle report generated");
            queryClient.invalidateQueries({
                queryKey: [...queryKeys.warGame.session(caseId, activePrepId!, selectedSessionId!)],
            });
            queryClient.invalidateQueries({
                queryKey: [...queryKeys.warGame.sessions(caseId, activePrepId!)],
            });
            setView("report");
        },
        onError: (err) => {
            toast.error("Failed to finalize", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        },
    });

    // ---- Navigation Helpers ---------------------------------------------

    function goToDashboard() {
        setView("dashboard");
        setSelectedSessionId(null);
    }

    function openSession(session: WarGameSession) {
        setSelectedSessionId(session.id);
        if (session.status === "completed" && session.report) {
            setView("report");
        } else {
            setView("active");
        }
    }

    // ---- Guards ---------------------------------------------------------

    if (!activePrepId && !prepLoading) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[300px] gap-4 text-center">
                <p className="text-muted-foreground">
                    Select or create a preparation to use the AI War Game.
                </p>
            </div>
        );
    }

    if (prepLoading || (view === "dashboard" && sessionsQuery.isLoading)) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-10 w-64" />
                <Skeleton className="h-32 w-full" />
                <Skeleton className="h-32 w-full" />
            </div>
        );
    }

    // ---- View 2: Active Session -----------------------------------------

    if (view === "active" && selectedSessionId) {
        return (
            <ActiveSessionView
                session={sessionQuery.data ?? null}
                isLoading={sessionQuery.isLoading}
                canEdit={canEdit}
                onBack={goToDashboard}
                onGenerateAttack={(roundType) => generateAttack.mutate(roundType)}
                onSubmitResponse={(roundType, response) =>
                    submitResponse.mutate({ roundType, response })
                }
                onFinalize={() => finalizeSession.mutate()}
                isAttacking={generateAttack.isPending}
                isResponding={submitResponse.isPending}
                isFinalizing={finalizeSession.isPending}
                onViewReport={() => setView("report")}
            />
        );
    }

    // ---- View 3: Battle Report ------------------------------------------

    if (view === "report" && selectedSessionId && sessionQuery.data?.report) {
        return (
            <BattleReportView
                session={sessionQuery.data}
                report={sessionQuery.data.report}
                isLoading={sessionQuery.isLoading}
                onBack={goToDashboard}
            />
        );
    }

    // ---- View 1: Dashboard ----------------------------------------------

    const sessions = sessionsQuery.data ?? [];

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">War Game</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Adversarial case simulation
                    </p>
                </div>
                {canEdit && (
                    <Button onClick={() => setDialogOpen(true)}>
                        + New War Game
                    </Button>
                )}
            </div>

            {/* Past Sessions */}
            {sessions.length > 0 ? (
                <div className="space-y-2">
                    <h3 className="text-sm font-medium text-muted-foreground">
                        Past Sessions
                    </h3>
                    {sessions.map((s) => (
                        <Card
                            key={s.id}
                            className="cursor-pointer hover:border-brand-indigo/40 transition-colors"
                            onClick={() => openSession(s)}
                        >
                            <CardContent className="py-3 flex items-center gap-4">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm font-medium">
                                            {formatDate(s.created_at)}
                                        </span>
                                        <Badge
                                            variant="outline"
                                            className={WAR_GAME_DIFFICULTY_COLORS[s.difficulty] ?? ""}
                                        >
                                            {DIFFICULTY_DESCRIPTIONS[s.difficulty]?.label ?? s.difficulty}
                                        </Badge>
                                        <span className="text-xs text-muted-foreground">
                                            Round {Math.min(s.current_round + 1, 5)}/5
                                        </span>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2 shrink-0">
                                    {s.status === "completed" && s.report ? (
                                        <>
                                            <Badge
                                                variant="outline"
                                                className={scoreColor(s.report.overall_score)}
                                            >
                                                Score: {s.report.overall_score}
                                            </Badge>
                                            <Badge
                                                variant="outline"
                                                className={VERDICT_COLORS[s.report.verdict] ?? ""}
                                            >
                                                {s.report.verdict.replace(/_/g, " ")}
                                            </Badge>
                                        </>
                                    ) : (
                                        <StatusBadge status={s.status} />
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            ) : (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        No war game sessions yet. Click &quot;+ New War Game&quot; to begin
                        an adversarial simulation.
                    </CardContent>
                </Card>
            )}

            {/* New War Game Dialog */}
            <NewWarGameDialog
                open={dialogOpen}
                onOpenChange={setDialogOpen}
                selectedDifficulty={selectedDifficulty}
                onSelectDifficulty={setSelectedDifficulty}
                onStart={() => createSession.mutate(selectedDifficulty)}
                isPending={createSession.isPending}
            />
        </div>
    );
}

// ---- New War Game Dialog ------------------------------------------------

function NewWarGameDialog({
    open,
    onOpenChange,
    selectedDifficulty,
    onSelectDifficulty,
    onStart,
    isPending,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    selectedDifficulty: string;
    onSelectDifficulty: (d: string) => void;
    onStart: () => void;
    isPending: boolean;
}) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>New War Game</DialogTitle>
                    <DialogDescription>
                        Select the difficulty level for the adversarial simulation.
                        Higher difficulty means a more aggressive opposing counsel.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-3 py-2">
                    {Object.entries(DIFFICULTY_DESCRIPTIONS).map(([key, { label, description }]) => (
                        <button
                            key={key}
                            type="button"
                            onClick={() => onSelectDifficulty(key)}
                            className={`w-full text-left rounded-lg border p-4 transition-colors ${
                                selectedDifficulty === key
                                    ? "border-brand-indigo bg-brand-indigo/10"
                                    : "border-border hover:border-border/80 hover:bg-accent/30"
                            }`}
                        >
                            <div className="flex items-center gap-2 mb-1">
                                <div
                                    className={`w-3 h-3 rounded-full border-2 ${
                                        selectedDifficulty === key
                                            ? "border-brand-indigo bg-brand-indigo"
                                            : "border-muted-foreground"
                                    }`}
                                />
                                <span className="text-sm font-semibold">{label}</span>
                                <Badge
                                    variant="outline"
                                    className={`text-[10px] ${WAR_GAME_DIFFICULTY_COLORS[key] ?? ""}`}
                                >
                                    {label}
                                </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground ml-5">
                                {description}
                            </p>
                        </button>
                    ))}
                </div>

                <DialogFooter>
                    <Button
                        variant="outline"
                        onClick={() => onOpenChange(false)}
                    >
                        Cancel
                    </Button>
                    <Button onClick={onStart} disabled={isPending}>
                        {isPending ? "Creating..." : "Start War Game"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

// ---- View 2: Active Session View ----------------------------------------

function ActiveSessionView({
    session,
    isLoading,
    canEdit,
    onBack,
    onGenerateAttack,
    onSubmitResponse,
    onFinalize,
    isAttacking,
    isResponding,
    isFinalizing,
    onViewReport,
}: {
    session: WarGameSession | null;
    isLoading: boolean;
    canEdit: boolean;
    onBack: () => void;
    onGenerateAttack: (roundType: string) => void;
    onSubmitResponse: (roundType: string, response: string) => void;
    onFinalize: () => void;
    isAttacking: boolean;
    isResponding: boolean;
    isFinalizing: boolean;
    onViewReport: () => void;
}) {
    const [responseText, setResponseText] = useState("");

    if (isLoading || !session) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-10 w-48" />
                <div className="grid grid-cols-[200px_1fr] gap-6">
                    <div className="space-y-3">
                        {Array.from({ length: 5 }).map((_, i) => (
                            <Skeleton key={i} className="h-14 w-full" />
                        ))}
                    </div>
                    <Skeleton className="h-96 w-full" />
                </div>
            </div>
        );
    }

    const currentRoundIndex = session.current_round;
    const currentRound = session.rounds[currentRoundIndex] ?? null;
    const currentRoundType = ROUND_ORDER[currentRoundIndex] ?? "theory";
    const allRoundsComplete = session.rounds.every((r) => r.status === "completed");
    const isSessionFinalized = session.status === "completed" && session.report;

    // Calculate running score
    const completedRounds = session.rounds.filter((r) => r.status === "completed" && r.evaluation);
    const runningScore =
        completedRounds.length > 0
            ? Math.round(
                  completedRounds.reduce((sum, r) => sum + (r.evaluation?.score ?? 0), 0) /
                      completedRounds.length,
              )
            : 0;

    return (
        <div className="space-y-4">
            {/* Top Bar */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Button variant="ghost" size="sm" onClick={onBack}>
                        ← Back to Sessions
                    </Button>
                    <Badge
                        variant="outline"
                        className={WAR_GAME_DIFFICULTY_COLORS[session.difficulty] ?? ""}
                    >
                        {DIFFICULTY_DESCRIPTIONS[session.difficulty]?.label ?? session.difficulty}
                    </Badge>
                    {completedRounds.length > 0 && (
                        <Badge variant="outline" className={scoreColor(runningScore)}>
                            Score: {runningScore}
                        </Badge>
                    )}
                </div>
                {/* Round progress indicators */}
                <div className="flex items-center gap-1.5">
                    {ROUND_ORDER.map((type, idx) => {
                        const round = session.rounds[idx];
                        const isComplete = round?.status === "completed";
                        const isCurrent = idx === currentRoundIndex;
                        return (
                            <div
                                key={type}
                                className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold border-2 transition-colors ${
                                    isComplete
                                        ? "bg-green-500/20 border-green-500 text-green-400"
                                        : isCurrent
                                          ? "bg-brand-indigo/20 border-brand-indigo text-brand-indigo"
                                          : "bg-muted/30 border-muted-foreground/30 text-muted-foreground"
                                }`}
                                title={ROUND_LABELS[type]}
                            >
                                {idx + 1}
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Main content: sidebar + center */}
            <div className="grid grid-cols-[220px_1fr] gap-6">
                {/* Left Stepper */}
                <div className="space-y-2">
                    {ROUND_ORDER.map((type, idx) => {
                        const round = session.rounds[idx];
                        const isComplete = round?.status === "completed";
                        const isCurrent = idx === currentRoundIndex;
                        const score = round?.evaluation?.score;

                        return (
                            <div
                                key={type}
                                className={`rounded-lg border p-3 transition-colors ${
                                    isCurrent
                                        ? "border-brand-indigo bg-brand-indigo/5"
                                        : isComplete
                                          ? "border-green-500/30 bg-green-500/5"
                                          : "border-border bg-card/30"
                                }`}
                            >
                                <div className="flex items-center justify-between">
                                    <span className={`text-xs font-semibold ${
                                        isCurrent
                                            ? "text-brand-indigo"
                                            : isComplete
                                              ? "text-green-400"
                                              : "text-muted-foreground"
                                    }`}>
                                        Round {idx + 1}
                                    </span>
                                    {isComplete && score !== undefined && (
                                        <Badge
                                            variant="outline"
                                            className={`text-[10px] ${scoreColor(score)}`}
                                        >
                                            {score}
                                        </Badge>
                                    )}
                                </div>
                                <p className={`text-sm mt-0.5 ${
                                    isCurrent ? "font-medium" : "text-muted-foreground"
                                }`}>
                                    {ROUND_LABELS[type]}
                                </p>
                            </div>
                        );
                    })}
                </div>

                {/* Center Content */}
                <div className="space-y-4">
                    {/* If session finalized, show button to view report */}
                    {isSessionFinalized ? (
                        <Card>
                            <CardContent className="py-8 text-center space-y-4">
                                <p className="text-lg font-semibold">War Game Complete</p>
                                <p className="text-sm text-muted-foreground">
                                    All rounds have been played and the battle report has been generated.
                                </p>
                                <Button onClick={onViewReport}>
                                    View Battle Report
                                </Button>
                            </CardContent>
                        </Card>
                    ) : !currentRound || currentRound.status === "pending" ? (
                        /* Round pending -- generate attack */
                        <Card>
                            <CardContent className="py-8 text-center space-y-4">
                                <p className="text-lg font-semibold">
                                    {ROUND_LABELS[currentRoundType]}
                                </p>
                                <p className="text-sm text-muted-foreground">
                                    Ready to begin Round {currentRoundIndex + 1}.
                                    The AI opposing counsel will generate an attack.
                                </p>
                                {canEdit && (
                                    <Button
                                        onClick={() => onGenerateAttack(currentRoundType)}
                                        disabled={isAttacking}
                                    >
                                        {isAttacking ? "Generating Attack..." : "Generate Attack"}
                                    </Button>
                                )}
                            </CardContent>
                        </Card>
                    ) : currentRound.status === "attacking" ? (
                        /* Attack loading */
                        <Card>
                            <CardContent className="py-8 space-y-4">
                                <p className="text-sm font-medium text-muted-foreground">
                                    Generating attack for {ROUND_LABELS[currentRoundType]}...
                                </p>
                                <div className="space-y-3">
                                    <Skeleton className="h-4 w-full" />
                                    <Skeleton className="h-4 w-3/4" />
                                    <Skeleton className="h-4 w-5/6" />
                                    <Skeleton className="h-4 w-2/3" />
                                </div>
                            </CardContent>
                        </Card>
                    ) : currentRound.status === "awaiting_response" ? (
                        /* Attack rendered + response textarea */
                        <div className="space-y-4">
                            {/* Attack Card */}
                            <Card className="border-red-500/30 bg-red-500/5">
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm text-red-400 flex items-center gap-2">
                                        Opposing Counsel Attack - {ROUND_LABELS[currentRoundType]}
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="text-sm whitespace-pre-wrap leading-relaxed">
                                        {currentRound.attack}
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Response area -- not shown for jury round */}
                            {currentRoundType !== "jury" ? (
                                <Card>
                                    <CardHeader className="pb-2">
                                        <CardTitle className="text-sm">Your Response</CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-3">
                                        <textarea
                                            value={responseText}
                                            onChange={(e) => setResponseText(e.target.value)}
                                            placeholder="Draft your response to the opposing counsel's attack..."
                                            className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:border-ring min-h-[200px] resize-y dark:bg-input/30"
                                        />
                                        {canEdit && (
                                            <Button
                                                onClick={() => {
                                                    if (!responseText.trim()) {
                                                        toast.error("Please write a response");
                                                        return;
                                                    }
                                                    onSubmitResponse(currentRoundType, responseText.trim());
                                                    setResponseText("");
                                                }}
                                                disabled={isResponding || !responseText.trim()}
                                            >
                                                {isResponding ? "Submitting..." : "Submit Response"}
                                            </Button>
                                        )}
                                    </CardContent>
                                </Card>
                            ) : (
                                /* Jury round -- no response needed */
                                <Card>
                                    <CardContent className="py-6 text-center">
                                        <p className="text-sm text-muted-foreground">
                                            The jury is deliberating based on all evidence presented.
                                            No response required.
                                        </p>
                                        {canEdit && (
                                            <Button
                                                className="mt-3"
                                                onClick={() => onSubmitResponse(currentRoundType, "")}
                                                disabled={isResponding}
                                            >
                                                {isResponding ? "Deliberating..." : "Begin Jury Deliberation"}
                                            </Button>
                                        )}
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                    ) : currentRound.status === "evaluating" ? (
                        /* Evaluation loading */
                        <Card>
                            <CardContent className="py-8 space-y-4">
                                <p className="text-sm font-medium text-muted-foreground">
                                    Evaluating your response...
                                </p>
                                <div className="space-y-3">
                                    <Skeleton className="h-4 w-full" />
                                    <Skeleton className="h-4 w-2/3" />
                                    <Skeleton className="h-4 w-4/5" />
                                </div>
                            </CardContent>
                        </Card>
                    ) : currentRound.status === "completed" && currentRound.evaluation ? (
                        /* Evaluation results */
                        <RoundEvaluation
                            round={currentRound}
                            roundType={currentRoundType}
                            roundIndex={currentRoundIndex}
                            isLastRound={currentRoundIndex >= 4}
                            allComplete={allRoundsComplete}
                            canEdit={canEdit}
                            onNextRound={() => {
                                // Advancing happens server-side; trigger attack for next round
                                const nextType = ROUND_ORDER[currentRoundIndex + 1];
                                if (nextType) {
                                    onGenerateAttack(nextType);
                                }
                            }}
                            onFinalize={onFinalize}
                            isFinalizing={isFinalizing}
                            isAttacking={isAttacking}
                        />
                    ) : null}
                </div>
            </div>
        </div>
    );
}

// ---- Round Evaluation Component -----------------------------------------

function RoundEvaluation({
    round,
    roundType,
    roundIndex,
    isLastRound,
    allComplete,
    canEdit,
    onNextRound,
    onFinalize,
    isFinalizing,
    isAttacking,
}: {
    round: WarGameRound;
    roundType: string;
    roundIndex: number;
    isLastRound: boolean;
    allComplete: boolean;
    canEdit: boolean;
    onNextRound: () => void;
    onFinalize: () => void;
    isFinalizing: boolean;
    isAttacking: boolean;
}) {
    const evaluation = round.evaluation!;
    const [showAttack, setShowAttack] = useState(false);

    return (
        <div className="space-y-4">
            {/* Score Badge */}
            <Card>
                <CardContent className="py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <span className="text-sm font-medium text-muted-foreground">
                                {ROUND_LABELS[roundType]} Score
                            </span>
                            <Badge
                                variant="outline"
                                className={`text-lg px-3 py-0.5 ${scoreColor(evaluation.score)}`}
                            >
                                {evaluation.score}
                            </Badge>
                        </div>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="text-xs"
                            onClick={() => setShowAttack(!showAttack)}
                        >
                            {showAttack ? "Hide Attack" : "Show Attack"}
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* Collapsible attack text */}
            {showAttack && round.attack && (
                <Card className="border-red-500/30 bg-red-500/5">
                    <CardContent className="py-3">
                        <p className="text-xs font-medium text-red-400 mb-2">
                            Opposing Counsel Attack
                        </p>
                        <div className="text-sm whitespace-pre-wrap leading-relaxed text-muted-foreground">
                            {round.attack}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Strengths */}
            {evaluation.strengths.length > 0 && (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-green-400">Strengths</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <ul className="space-y-1.5">
                            {evaluation.strengths.map((s, i) => (
                                <li key={i} className="flex items-start gap-2 text-sm">
                                    <span className="text-green-400 mt-0.5 shrink-0">+</span>
                                    <span>{s}</span>
                                </li>
                            ))}
                        </ul>
                    </CardContent>
                </Card>
            )}

            {/* Vulnerabilities */}
            {evaluation.vulnerabilities.length > 0 && (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-red-400">Vulnerabilities</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <ul className="space-y-1.5">
                            {evaluation.vulnerabilities.map((v, i) => (
                                <li key={i} className="flex items-start gap-2 text-sm">
                                    <span className="text-red-400 mt-0.5 shrink-0">-</span>
                                    <span>{v}</span>
                                </li>
                            ))}
                        </ul>
                    </CardContent>
                </Card>
            )}

            {/* Evidence round: rulings table */}
            {roundType === "evidence" && evaluation.rulings && evaluation.rulings.length > 0 && (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Evidence Rulings</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-border">
                                        <th className="text-left py-2 pr-4 text-xs font-medium text-muted-foreground">Item</th>
                                        <th className="text-left py-2 pr-4 text-xs font-medium text-muted-foreground">Ruling</th>
                                        <th className="text-left py-2 text-xs font-medium text-muted-foreground">Reasoning</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {evaluation.rulings.map((r, i) => (
                                        <tr key={i} className="border-b border-border/50">
                                            <td className="py-2 pr-4 font-medium">{r.item}</td>
                                            <td className="py-2 pr-4">
                                                <Badge
                                                    variant="outline"
                                                    className={
                                                        r.ruling === "admitted"
                                                            ? "bg-green-500/15 text-green-400 border-green-500/30"
                                                            : "bg-red-500/15 text-red-400 border-red-500/30"
                                                    }
                                                >
                                                    {r.ruling}
                                                </Badge>
                                            </td>
                                            <td className="py-2 text-muted-foreground">{r.reasoning}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Witness round: credibility scores */}
            {roundType === "witnesses" && evaluation.witness_scores && evaluation.witness_scores.length > 0 && (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Witness Credibility</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-3">
                            {evaluation.witness_scores.map((ws, i) => (
                                <div key={i} className="flex items-start justify-between border-b border-border/50 pb-2 last:border-0">
                                    <div className="flex-1">
                                        <p className="text-sm font-medium">{ws.name}</p>
                                        {ws.vulnerabilities.length > 0 && (
                                            <ul className="mt-1 space-y-0.5">
                                                {ws.vulnerabilities.map((v, j) => (
                                                    <li key={j} className="text-xs text-muted-foreground flex items-start gap-1">
                                                        <span className="text-red-400 shrink-0">-</span>
                                                        {v}
                                                    </li>
                                                ))}
                                            </ul>
                                        )}
                                    </div>
                                    <Badge
                                        variant="outline"
                                        className={scoreColor(ws.credibility)}
                                    >
                                        {ws.credibility}
                                    </Badge>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Elements round: element coverage */}
            {roundType === "elements" && evaluation.element_coverage && evaluation.element_coverage.length > 0 && (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Element Coverage</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-border">
                                        <th className="text-left py-2 pr-4 text-xs font-medium text-muted-foreground">Charge</th>
                                        <th className="text-left py-2 pr-4 text-xs font-medium text-muted-foreground">Element</th>
                                        <th className="text-left py-2 pr-4 text-xs font-medium text-muted-foreground">Covered</th>
                                        <th className="text-left py-2 text-xs font-medium text-muted-foreground">Gap</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {evaluation.element_coverage.map((ec, i) => (
                                        <tr key={i} className="border-b border-border/50">
                                            <td className="py-2 pr-4 font-medium">{ec.charge}</td>
                                            <td className="py-2 pr-4">{ec.element}</td>
                                            <td className="py-2 pr-4">
                                                <Badge
                                                    variant="outline"
                                                    className={
                                                        ec.covered
                                                            ? "bg-green-500/15 text-green-400 border-green-500/30"
                                                            : "bg-red-500/15 text-red-400 border-red-500/30"
                                                    }
                                                >
                                                    {ec.covered ? "Yes" : "No"}
                                                </Badge>
                                            </td>
                                            <td className="py-2 text-muted-foreground">
                                                {ec.gap || "\u2014"}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Navigation button */}
            {canEdit && (
                <div className="flex gap-2">
                    {isLastRound || allComplete ? (
                        <Button onClick={onFinalize} disabled={isFinalizing}>
                            {isFinalizing ? "Generating Report..." : "Generate Battle Report"}
                        </Button>
                    ) : (
                        <Button onClick={onNextRound} disabled={isAttacking}>
                            {isAttacking ? "Loading Next Round..." : `Next Round: ${ROUND_LABELS[ROUND_ORDER[roundIndex + 1]] ?? ""} \u2192`}
                        </Button>
                    )}
                </div>
            )}
        </div>
    );
}

// ---- View 3: Battle Report View ----------------------------------------

function BattleReportView({
    session,
    report,
    isLoading,
    onBack,
}: {
    session: WarGameSession;
    report: WarGameReport;
    isLoading: boolean;
    onBack: () => void;
}) {
    const [expandedVuln, setExpandedVuln] = useState<number | null>(null);

    if (isLoading) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-10 w-48" />
                <Skeleton className="h-40 w-full" />
                <Skeleton className="h-60 w-full" />
            </div>
        );
    }

    // Determine verdict color
    const verdictColorClass = VERDICT_COLORS[report.verdict] ?? "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";

    return (
        <div className="space-y-6">
            {/* Back Button */}
            <Button variant="ghost" size="sm" onClick={onBack}>
                ← Back to Sessions
            </Button>

            {/* Verdict Banner */}
            <Card className={`border-2 ${verdictColorClass.replace(/bg-[^ ]+/, "").trim()}`}>
                <CardContent className="py-8 text-center">
                    <p className="text-xs uppercase tracking-widest text-muted-foreground mb-2">
                        Simulation Verdict
                    </p>
                    <p className={`text-3xl font-bold capitalize ${verdictColorClass.split(" ").find((c) => c.startsWith("text-")) ?? ""}`}>
                        {report.verdict.replace(/_/g, " ")}
                    </p>
                    <Badge
                        variant="outline"
                        className={WAR_GAME_DIFFICULTY_COLORS[session.difficulty] ?? ""}
                    >
                        {DIFFICULTY_DESCRIPTIONS[session.difficulty]?.label ?? session.difficulty} Difficulty
                    </Badge>
                </CardContent>
            </Card>

            {/* Overall Score + Round Breakdown */}
            <div className="space-y-3">
                <div className="flex items-center gap-4">
                    <div className="text-center">
                        <p className="text-xs text-muted-foreground mb-1">Overall Score</p>
                        <p className={`text-5xl font-bold tabular-nums ${scoreTextColor(report.overall_score)}`}>
                            {report.overall_score}
                        </p>
                    </div>
                    <div className="flex-1 grid grid-cols-5 gap-2">
                        {report.round_scores.map((rs) => (
                            <Card key={rs.type} className="text-center">
                                <CardContent className="py-3 px-2">
                                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1">
                                        {ROUND_LABELS[rs.type] ?? rs.type}
                                    </p>
                                    <p className={`text-xl font-bold tabular-nums ${scoreTextColor(rs.score)}`}>
                                        {rs.score}
                                    </p>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </div>
            </div>

            {/* Executive Summary */}
            {report.executive_summary && (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Executive Summary</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">
                            {report.executive_summary}
                        </p>
                    </CardContent>
                </Card>
            )}

            {/* Vulnerability Report */}
            {report.vulnerabilities.length > 0 && (
                <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-muted-foreground">
                        Vulnerability Report
                    </h3>
                    {report.vulnerabilities.map((vuln) => (
                        <Card key={vuln.rank}>
                            <CardContent className="py-3">
                                <div className="flex items-start justify-between">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <Badge
                                                variant="outline"
                                                className={SEVERITY_BADGE_COLORS[vuln.severity] ?? ""}
                                            >
                                                {vuln.severity}
                                            </Badge>
                                            <span className="text-sm font-medium">{vuln.area}</span>
                                            <span className="text-xs text-muted-foreground">
                                                #{vuln.rank}
                                            </span>
                                        </div>
                                        <p className="text-sm text-muted-foreground">
                                            {vuln.description}
                                        </p>

                                        {/* Collapsible exploit scenario */}
                                        <button
                                            type="button"
                                            onClick={() =>
                                                setExpandedVuln(expandedVuln === vuln.rank ? null : vuln.rank)
                                            }
                                            className="text-xs text-brand-indigo mt-2 hover:underline"
                                        >
                                            {expandedVuln === vuln.rank ? "Hide" : "Show"} exploit scenario
                                        </button>
                                        {expandedVuln === vuln.rank && (
                                            <div className="mt-2 p-3 rounded-md bg-red-500/5 border border-red-500/20">
                                                <p className="text-xs font-medium text-red-400 mb-1">
                                                    Exploit Scenario
                                                </p>
                                                <p className="text-sm text-muted-foreground">
                                                    {vuln.exploit_scenario}
                                                </p>
                                            </div>
                                        )}

                                        {/* Mitigation */}
                                        <div className="mt-2 p-3 rounded-md bg-green-500/5 border border-green-500/20">
                                            <p className="text-xs font-medium text-green-400 mb-1">
                                                Mitigation Strategy
                                            </p>
                                            <p className="text-sm text-muted-foreground">
                                                {vuln.mitigation}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Contingency Playbook */}
            {report.contingency_cards.length > 0 && (
                <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-muted-foreground">
                        Contingency Playbook
                    </h3>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                        {report.contingency_cards.map((card, idx) => (
                            <Card key={idx}>
                                <CardContent className="py-3 space-y-2">
                                    <div className="flex items-start justify-between">
                                        <p className="text-sm font-medium flex-1">
                                            <span className="text-amber-400">If:</span>{" "}
                                            {card.trigger}
                                        </p>
                                        <Badge
                                            variant="outline"
                                            className={SEVERITY_BADGE_COLORS[card.risk_level] ?? ""}
                                        >
                                            {card.risk_level}
                                        </Badge>
                                    </div>
                                    <p className="text-sm">
                                        <span className="text-green-400 font-medium">Then:</span>{" "}
                                        {card.response}
                                    </p>
                                    {card.authority && (
                                        <p className="text-xs text-muted-foreground">
                                            <span className="font-medium">Authority:</span>{" "}
                                            {card.authority}
                                        </p>
                                    )}
                                    {card.evidence_to_cite && (
                                        <p className="text-xs text-muted-foreground">
                                            <span className="font-medium">Evidence:</span>{" "}
                                            {card.evidence_to_cite}
                                        </p>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </div>
            )}

            {/* Jury Breakdown */}
            {report.juror_verdicts.length > 0 && (
                <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-muted-foreground">
                        Jury Breakdown
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {report.juror_verdicts.map((juror, idx) => {
                            const voteNorm = juror.vote.toLowerCase().replace(/[\s_]/g, "_");
                            const voteColorClass = VERDICT_COLORS[voteNorm] ?? "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";

                            return (
                                <Card key={idx}>
                                    <CardContent className="py-3">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="text-sm font-medium">
                                                {juror.juror}
                                            </span>
                                            <Badge variant="outline" className={voteColorClass}>
                                                {juror.vote.replace(/_/g, " ")}
                                            </Badge>
                                        </div>
                                        <p className="text-xs text-muted-foreground leading-relaxed">
                                            {juror.reasoning}
                                        </p>
                                    </CardContent>
                                </Card>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Bottom back button */}
            <div className="pt-2">
                <Button variant="outline" onClick={onBack}>
                    ← Back to Sessions
                </Button>
            </div>
        </div>
    );
}
