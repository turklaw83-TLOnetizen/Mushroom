// ---- Mock Examination Simulator -----------------------------------------
// Interactive AI witness examination practice with coaching and scoring.
"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { usePrep } from "@/hooks/use-prep";
import { useMockExam, type MockExamMessage, type CoachingNote } from "@/hooks/use-mock-exam";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { ScorecardView, type Scorecard } from "@/components/mock-exam/scorecard-view";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from "@/components/ui/dialog";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

// ---- Types ----------------------------------------------------------------

interface Witness {
    name: string;
    type: string;
    role?: string;
    goal?: string;
}

interface SessionSummary {
    id: string;
    witness_name: string;
    witness_type: string;
    exam_type: string;
    opposing_counsel_mode: boolean;
    created_at: string;
    ended_at: string | null;
    message_count: number;
    status: string;
    scorecard_summary?: { overall_score: number; summary: string } | null;
}

interface SessionDetail {
    session_id: string;
    witness_name: string;
    witness_type: string;
    exam_type: string;
    opposing_counsel_mode: boolean;
    messages: MockExamMessage[];
    coaching_notes: CoachingNote[];
    scorecard: Scorecard | null;
}

// ---- Main Page ------------------------------------------------------------

export default function MockExamPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { activePrepId, isLoading: prepLoading } = usePrep();
    const { getToken } = useAuth();

    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
    const [showSetup, setShowSetup] = useState(false);
    const [viewingScorecard, setViewingScorecard] = useState<SessionDetail | null>(null);
    const [showCompare, setShowCompare] = useState(false);
    const [compareA, setCompareA] = useState<string>("");
    const [compareB, setCompareB] = useState<string>("");
    const [detailA, setDetailA] = useState<SessionDetail | null>(null);
    const [detailB, setDetailB] = useState<SessionDetail | null>(null);
    const [compareLoading, setCompareLoading] = useState(false);

    const basePath = activePrepId
        ? `/cases/${caseId}/preparations/${activePrepId}/mock-exam`
        : null;

    // Fetch sessions list
    const sessionsQuery = useQuery({
        queryKey: ["mock-exam-sessions", caseId, activePrepId],
        queryFn: () => api.get<SessionSummary[]>(`${basePath}/sessions`, { getToken }),
        enabled: !!basePath,
    });

    // Fetch witnesses
    const witnessesQuery = useQuery({
        queryKey: ["witnesses", caseId, activePrepId],
        queryFn: () =>
            api.get<Witness[]>(
                `/cases/${caseId}/preparations/${activePrepId}/witnesses`,
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    const handleSessionClick = async (session: SessionSummary) => {
        if (session.status === "completed") {
            // Load full session to show scorecard
            try {
                const data = await api.get<SessionDetail>(
                    `${basePath}/sessions/${session.id}`,
                    { getToken },
                );
                setViewingScorecard(data);
            } catch {
                toast.error("Failed to load session");
            }
        } else {
            // Resume active session
            setActiveSessionId(session.id);
        }
    };

    // No prep selected
    if (!activePrepId && !prepLoading) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[300px] gap-4 text-center">
                <p className="text-muted-foreground">
                    Select or create a preparation to use Mock Examination.
                </p>
            </div>
        );
    }

    // Loading
    if (prepLoading || sessionsQuery.isLoading) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-10 w-64" />
                <Skeleton className="h-32 w-full" />
                <Skeleton className="h-32 w-full" />
            </div>
        );
    }

    // Active exam session
    if (activeSessionId && basePath) {
        return (
            <ExamSession
                caseId={caseId}
                prepId={activePrepId!}
                sessionId={activeSessionId}
                basePath={basePath}
                onEnd={() => {
                    setActiveSessionId(null);
                    sessionsQuery.refetch();
                }}
            />
        );
    }

    // Viewing completed scorecard
    if (viewingScorecard?.scorecard) {
        return (
            <div className="space-y-4">
                <div className="flex items-center gap-3">
                    <Button variant="ghost" size="sm" onClick={() => setViewingScorecard(null)}>
                        ← Back
                    </Button>
                    <h2 className="text-lg font-semibold">Session Scorecard</h2>
                </div>
                <ScorecardView
                    scorecard={viewingScorecard.scorecard}
                    examType={viewingScorecard.exam_type}
                    witnessName={viewingScorecard.witness_name}
                />
            </div>
        );
    }

    const sessions = sessionsQuery.data ?? [];
    const witnesses = witnessesQuery.data ?? [];

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">Mock Examination</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Practice direct and cross examination with AI witnesses
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {sessions.filter(s => s.status === "completed").length >= 2 && (
                        <Button variant="outline" size="sm" onClick={() => setShowCompare(true)}>
                            Compare Sessions
                        </Button>
                    )}
                    <Button onClick={() => setShowSetup(true)} disabled={witnesses.length === 0}>
                        + New Session
                    </Button>
                </div>
            </div>

            {/* No witnesses warning */}
            {witnesses.length === 0 && (
                <Card className="border-dashed border-amber-500/30">
                    <CardContent className="py-6 text-center">
                        <p className="text-sm text-muted-foreground">
                            <span aria-hidden="true">⚠️ </span>
                            No witnesses defined yet. Add witnesses in the{" "}
                            <strong>Witnesses</strong> tab, then run analysis to populate
                            examination data.
                        </p>
                    </CardContent>
                </Card>
            )}

            {/* Sessions list */}
            {sessions.length > 0 ? (
                <div className="space-y-2">
                    <h3 className="text-sm font-medium text-muted-foreground">Past Sessions</h3>
                    {sessions.map((s) => (
                        <Card
                            key={s.id}
                            className="cursor-pointer hover:border-brand-indigo/40 transition-colors"
                            onClick={() => handleSessionClick(s)}
                        >
                            <CardContent className="py-3 flex items-center gap-4">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm font-medium truncate">
                                            {s.witness_name}
                                        </span>
                                        <Badge variant="secondary" className="text-xs shrink-0">
                                            {s.witness_type}
                                        </Badge>
                                        <Badge
                                            variant="outline"
                                            className="text-xs shrink-0"
                                        >
                                            {s.exam_type === "cross" ? "Cross" : "Direct"}
                                        </Badge>
                                        {s.opposing_counsel_mode && (
                                            <Badge variant="outline" className="text-xs shrink-0">
                                                OC
                                            </Badge>
                                        )}
                                    </div>
                                    <p className="text-xs text-muted-foreground mt-0.5">
                                        {new Date(s.created_at).toLocaleDateString()} ·{" "}
                                        {s.message_count} questions
                                    </p>
                                </div>
                                <div className="flex items-center gap-2 shrink-0">
                                    {s.status === "completed" && s.scorecard_summary ? (
                                        <Badge
                                            variant={
                                                s.scorecard_summary.overall_score >= 80
                                                    ? "default"
                                                    : s.scorecard_summary.overall_score >= 60
                                                      ? "secondary"
                                                      : "destructive"
                                            }
                                            className="text-xs"
                                        >
                                            Score: {s.scorecard_summary.overall_score}
                                        </Badge>
                                    ) : (
                                        <Badge variant="outline" className="text-xs">
                                            {s.status === "active" ? "In Progress" : s.status}
                                        </Badge>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            ) : witnesses.length > 0 ? (
                <Card className="border-dashed">
                    <CardContent className="py-8 text-center">
                        <p className="text-sm text-muted-foreground">
                            No examination sessions yet. Click &quot;+ New Session&quot; to start
                            practicing.
                        </p>
                    </CardContent>
                </Card>
            ) : null}

            {/* Setup dialog */}
            <SessionSetupDialog
                open={showSetup}
                onOpenChange={setShowSetup}
                witnesses={witnesses}
                basePath={basePath!}
                onCreated={(id) => {
                    setActiveSessionId(id);
                    setShowSetup(false);
                    sessionsQuery.refetch();
                }}
            />

            {/* Compare Sessions dialog */}
            <SessionCompareDialog
                open={showCompare}
                onOpenChange={(open) => {
                    setShowCompare(open);
                    if (!open) { setDetailA(null); setDetailB(null); setCompareA(""); setCompareB(""); }
                }}
                sessions={sessions.filter(s => s.status === "completed")}
                compareA={compareA}
                compareB={compareB}
                onCompareAChange={setCompareA}
                onCompareBChange={setCompareB}
                detailA={detailA}
                detailB={detailB}
                loading={compareLoading}
                onCompare={async () => {
                    if (!compareA || !compareB || !basePath) return;
                    setCompareLoading(true);
                    try {
                        const [a, b] = await Promise.all([
                            api.get<SessionDetail>(`${basePath}/sessions/${compareA}`, { getToken }),
                            api.get<SessionDetail>(`${basePath}/sessions/${compareB}`, { getToken }),
                        ]);
                        setDetailA(a);
                        setDetailB(b);
                    } catch {
                        toast.error("Failed to load session details");
                    } finally {
                        setCompareLoading(false);
                    }
                }}
            />
        </div>
    );
}

// ---- Session Setup Dialog -------------------------------------------------

function SessionSetupDialog({
    open,
    onOpenChange,
    witnesses,
    basePath,
    onCreated,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    witnesses: Witness[];
    basePath: string;
    onCreated: (sessionId: string) => void;
}) {
    const { getToken } = useAuth();
    const [witnessName, setWitnessName] = useState("");
    const [examType, setExamType] = useState("cross");
    const [opposingCounsel, setOpposingCounsel] = useState(true);

    const createMutation = useMutationWithToast<{
        witness_name: string;
        exam_type: string;
        opposing_counsel_mode: boolean;
    }>({
        mutationFn: (data) => api.post<{ session_id: string }>(`${basePath}/sessions`, data, { getToken }),
        successMessage: "Examination started",
        onSuccess: (data: unknown) => {
            const result = data as { session_id: string };
            onCreated(result.session_id);
        },
    });

    // Auto-toggle opposing counsel based on exam type
    useEffect(() => {
        setOpposingCounsel(examType === "cross");
    }, [examType]);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>New Mock Examination</DialogTitle>
                    <DialogDescription>
                        Choose a witness and examination type to begin practice.
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-2">
                    {/* Witness selector */}
                    <div>
                        <label className="text-sm font-medium mb-1.5 block">Witness</label>
                        <Select value={witnessName} onValueChange={setWitnessName}>
                            <SelectTrigger>
                                <SelectValue placeholder="Select a witness" />
                            </SelectTrigger>
                            <SelectContent>
                                {witnesses.map((w) => (
                                    <SelectItem key={w.name} value={w.name}>
                                        {w.name}{" "}
                                        <span className="text-muted-foreground">({w.type})</span>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Exam type */}
                    <div>
                        <label className="text-sm font-medium mb-1.5 block">Examination Type</label>
                        <div className="flex gap-2">
                            <Button
                                variant={examType === "cross" ? "default" : "outline"}
                                size="sm"
                                className="flex-1"
                                onClick={() => setExamType("cross")}
                            >
                                Cross-Examination
                            </Button>
                            <Button
                                variant={examType === "direct" ? "default" : "outline"}
                                size="sm"
                                className="flex-1"
                                onClick={() => setExamType("direct")}
                            >
                                Direct Examination
                            </Button>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                            {examType === "cross"
                                ? "Practice questioning a hostile or opposing witness"
                                : "Practice questioning a friendly witness"}
                        </p>
                    </div>

                    {/* Opposing counsel toggle */}
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium">Opposing Counsel</p>
                            <p className="text-xs text-muted-foreground">
                                AI objects to improper questions
                            </p>
                        </div>
                        <Button
                            variant={opposingCounsel ? "default" : "outline"}
                            size="sm"
                            onClick={() => setOpposingCounsel(!opposingCounsel)}
                        >
                            {opposingCounsel ? "On" : "Off"}
                        </Button>
                    </div>

                    {/* Start button */}
                    <Button
                        className="w-full"
                        disabled={!witnessName || createMutation.isPending}
                        onClick={() =>
                            createMutation.mutate({
                                witness_name: witnessName,
                                exam_type: examType,
                                opposing_counsel_mode: opposingCounsel,
                            })
                        }
                    >
                        {createMutation.isPending ? "Starting..." : "Start Examination"}
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}

// ---- Session Compare Dialog -----------------------------------------------

function SessionCompareDialog({
    open,
    onOpenChange,
    sessions,
    compareA,
    compareB,
    onCompareAChange,
    onCompareBChange,
    detailA,
    detailB,
    loading,
    onCompare,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    sessions: SessionSummary[];
    compareA: string;
    compareB: string;
    onCompareAChange: (id: string) => void;
    onCompareBChange: (id: string) => void;
    detailA: SessionDetail | null;
    detailB: SessionDetail | null;
    loading: boolean;
    onCompare: () => void;
}) {
    const fmtSession = (s: SessionSummary) =>
        `${s.witness_name} (${s.exam_type === "cross" ? "Cross" : "Direct"}) - ${new Date(s.created_at).toLocaleDateString()}`;

    const scorecardA = detailA?.scorecard;
    const scorecardB = detailB?.scorecard;
    const allCategories = scorecardA && scorecardB
        ? [...new Set([...Object.keys(scorecardA.categories), ...Object.keys(scorecardB.categories)])]
        : [];

    const delta = (a: number, b: number) => {
        if (b > a) return <span className="text-emerald-400 ml-1">+{b - a}</span>;
        if (b < a) return <span className="text-red-400 ml-1">{b - a}</span>;
        return <span className="text-muted-foreground ml-1">=</span>;
    };

    const LABELS: Record<string, string> = {
        question_technique: "Question Technique",
        impeachment_effectiveness: "Impeachment",
        evidence_usage: "Evidence Usage",
        objection_avoidance: "Objection Avoidance",
        narrative_control: "Narrative Control",
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Compare Sessions</DialogTitle>
                    <DialogDescription>
                        Select two completed sessions to compare scores side by side.
                    </DialogDescription>
                </DialogHeader>
                <div className="grid grid-cols-2 gap-4 py-2">
                    <div>
                        <label className="text-sm font-medium mb-1.5 block">Session A</label>
                        <Select value={compareA} onValueChange={onCompareAChange}>
                            <SelectTrigger><SelectValue placeholder="Pick session" /></SelectTrigger>
                            <SelectContent>
                                {sessions.map(s => (
                                    <SelectItem key={s.id} value={s.id}>{fmtSession(s)}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <div>
                        <label className="text-sm font-medium mb-1.5 block">Session B</label>
                        <Select value={compareB} onValueChange={onCompareBChange}>
                            <SelectTrigger><SelectValue placeholder="Pick session" /></SelectTrigger>
                            <SelectContent>
                                {sessions.map(s => (
                                    <SelectItem key={s.id} value={s.id}>{fmtSession(s)}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                </div>
                <Button
                    className="w-full"
                    disabled={!compareA || !compareB || compareA === compareB || loading}
                    onClick={onCompare}
                >
                    {loading ? "Loading..." : "Compare"}
                </Button>

                {scorecardA && scorecardB && (
                    <div className="space-y-3 pt-2">
                        {/* Overall */}
                        <Card>
                            <CardContent className="py-3">
                                <div className="grid grid-cols-3 text-center">
                                    <div>
                                        <p className="text-xs text-muted-foreground">Session A</p>
                                        <p className="text-2xl font-bold">{scorecardA.overall_score}</p>
                                    </div>
                                    <div className="flex flex-col items-center justify-center">
                                        <p className="text-xs text-muted-foreground">Overall</p>
                                        {delta(scorecardA.overall_score, scorecardB.overall_score)}
                                    </div>
                                    <div>
                                        <p className="text-xs text-muted-foreground">Session B</p>
                                        <p className="text-2xl font-bold">{scorecardB.overall_score}</p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                        {/* Categories */}
                        {allCategories.map(cat => {
                            const aScore = scorecardA.categories[cat]?.score ?? 0;
                            const bScore = scorecardB.categories[cat]?.score ?? 0;
                            return (
                                <div key={cat} className="grid grid-cols-3 items-center text-sm px-2">
                                    <span className="text-right font-medium tabular-nums">{aScore}</span>
                                    <span className="text-center text-xs text-muted-foreground">
                                        {LABELS[cat] || cat}{delta(aScore, bScore)}
                                    </span>
                                    <span className="font-medium tabular-nums">{bScore}</span>
                                </div>
                            );
                        })}
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

// ---- Active Exam Session --------------------------------------------------

function ExamSession({
    caseId,
    prepId,
    sessionId,
    basePath,
    onEnd,
}: {
    caseId: string;
    prepId: string;
    sessionId: string;
    basePath: string;
    onEnd: () => void;
}) {
    const { getToken } = useAuth();
    const {
        messages,
        coachingNotes,
        isWitnessTyping,
        streamingText,
        connected,
        lastRuling,
        sendQuestion,
    } = useMockExam(caseId, prepId, sessionId);

    const [input, setInput] = useState("");
    const [isEnding, setIsEnding] = useState(false);
    const [scorecard, setScorecard] = useState<Scorecard | null>(null);
    const [showCoaching, setShowCoaching] = useState(true);
    const chatEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    // Auto-scroll to bottom
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, streamingText]);

    // Focus input
    useEffect(() => {
        if (!isWitnessTyping) inputRef.current?.focus();
    }, [isWitnessTyping]);

    const handleSend = () => {
        if (input.trim() && !isWitnessTyping) {
            sendQuestion(input.trim());
            setInput("");
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleEndSession = async () => {
        setIsEnding(true);
        try {
            const result = await api.post<Scorecard>(
                `${basePath}/sessions/${sessionId}/end`,
                {},
                { getToken },
            );
            setScorecard(result);
            toast.success("Session scored");
        } catch {
            toast.error("Failed to generate scorecard");
        } finally {
            setIsEnding(false);
        }
    };

    // Derive session info from first system message
    const systemMsg = messages.find((m) => m.role === "system");
    const witnessName = systemMsg?.content.match(/examining (.+?) \(/)?.[1] ?? "Witness";
    const examType = systemMsg?.content.includes("cross") ? "cross" : "direct";

    // If scorecard is ready, show it
    if (scorecard) {
        return (
            <div className="space-y-4">
                <div className="flex items-center gap-3">
                    <Button variant="ghost" size="sm" onClick={onEnd}>
                        ← Back to Sessions
                    </Button>
                </div>
                <ScorecardView
                    scorecard={scorecard}
                    examType={examType}
                    witnessName={witnessName}
                />
                <div className="flex gap-2">
                    <Button variant="outline" onClick={onEnd}>
                        Back to Sessions
                    </Button>
                </div>
            </div>
        );
    }

    const attorneyQuestionCount = messages.filter((m) => m.role === "attorney").length;

    return (
        <div className="flex flex-col h-[calc(100vh-200px)]">
            {/* Header Bar */}
            <div className="flex items-center justify-between pb-3 border-b border-border mb-3">
                <div className="flex items-center gap-3">
                    <Button variant="ghost" size="sm" onClick={onEnd}>
                        ← Back
                    </Button>
                    <span className="font-semibold">{witnessName}</span>
                    <Badge variant="secondary" className="text-xs">
                        {examType === "cross" ? "Cross" : "Direct"}
                    </Badge>
                    {connected ? (
                        <Badge variant="outline" className="text-xs text-emerald-400 border-emerald-500/30">
                            Connected
                        </Badge>
                    ) : (
                        <Badge variant="destructive" className="text-xs">Disconnected</Badge>
                    )}
                    <span className="text-xs text-muted-foreground">
                        {attorneyQuestionCount} questions
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        className="text-xs md:hidden"
                        onClick={() => setShowCoaching(!showCoaching)}
                    >
                        {showCoaching ? "Hide" : "Show"} Coaching
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleEndSession}
                        disabled={isEnding || attorneyQuestionCount < 1}
                    >
                        {isEnding ? "Scoring..." : "End & Score"}
                    </Button>
                </div>
            </div>

            {/* Two-panel layout */}
            <div className="flex flex-1 gap-4 min-h-0">
                {/* Chat Panel */}
                <div className="flex-1 flex flex-col min-w-0">
                    {/* Messages */}
                    <div className="flex-1 overflow-y-auto space-y-3 pr-2">
                        {messages
                            .filter((m) => m.role !== "system")
                            .map((msg) => (
                                <ChatBubble key={msg.id} message={msg} lastRuling={msg.role === "objection" ? lastRuling : null} />
                            ))}
                        {/* Streaming witness response */}
                        {isWitnessTyping && streamingText && (
                            <div className="flex justify-start">
                                <div className="max-w-[80%] bg-muted rounded-lg px-3 py-2 text-sm whitespace-pre-wrap">
                                    {streamingText}
                                    <span className="animate-pulse">▊</span>
                                </div>
                            </div>
                        )}
                        {isWitnessTyping && !streamingText && (
                            <div className="flex justify-start">
                                <div className="bg-muted rounded-lg px-3 py-2 text-sm text-muted-foreground">
                                    <span className="animate-pulse">Witness is thinking...</span>
                                </div>
                            </div>
                        )}
                        <div ref={chatEndRef} />
                    </div>

                    {/* Input */}
                    <div className="flex gap-2 pt-3 border-t border-border mt-auto">
                        <textarea
                            ref={inputRef}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder={
                                isWitnessTyping
                                    ? "Waiting for witness..."
                                    : "Ask your question..."
                            }
                            disabled={isWitnessTyping || !connected}
                            className="flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[40px] max-h-[120px]"
                            rows={1}
                        />
                        <Button
                            onClick={handleSend}
                            disabled={!input.trim() || isWitnessTyping || !connected}
                            className="shrink-0"
                        >
                            Send
                        </Button>
                    </div>
                </div>

                {/* Coaching Sidebar */}
                {showCoaching && (
                    <div className="w-72 shrink-0 hidden md:flex flex-col border-l border-border pl-4">
                        <h3 className="text-sm font-semibold mb-2 text-muted-foreground">
                            Coaching
                        </h3>
                        <div className="flex-1 overflow-y-auto space-y-2">
                            {coachingNotes.length === 0 ? (
                                <p className="text-xs text-muted-foreground italic">
                                    Coaching notes will appear here as you ask questions.
                                </p>
                            ) : (
                                coachingNotes.map((note, i) => (
                                    <CoachingCard key={i} note={note} />
                                ))
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

// ---- Chat Bubble ----------------------------------------------------------

function ChatBubble({
    message,
    lastRuling,
}: {
    message: MockExamMessage;
    lastRuling: { ruling: string; explanation: string } | null;
}) {
    if (message.role === "attorney") {
        return (
            <div className="flex justify-end">
                <div className="max-w-[80%] bg-brand-indigo/20 text-foreground rounded-lg px-3 py-2 text-sm">
                    <div className="text-xs text-muted-foreground mb-1 font-medium">You</div>
                    {message.content}
                </div>
            </div>
        );
    }

    if (message.role === "witness") {
        return (
            <div className="flex justify-start">
                <div className="max-w-[80%] bg-muted rounded-lg px-3 py-2 text-sm whitespace-pre-wrap">
                    <div className="text-xs text-muted-foreground mb-1 font-medium">Witness</div>
                    {message.content}
                </div>
            </div>
        );
    }

    if (message.role === "objection") {
        const ruling = lastRuling ?? (message.metadata as { ruling_suggestion?: string } | undefined);
        const rText = ruling && "ruling" in ruling ? ruling.ruling : (ruling as { ruling_suggestion?: string })?.ruling_suggestion;
        return (
            <div className="flex justify-center">
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-2 text-sm text-center max-w-[90%]">
                    <span className="font-semibold text-red-400">{message.content}</span>
                    {rText && (
                        <Badge
                            variant={rText === "sustained" ? "destructive" : "secondary"}
                            className="ml-2 text-xs"
                        >
                            {rText === "sustained" ? "Sustained" : "Overruled"}
                        </Badge>
                    )}
                </div>
            </div>
        );
    }

    return null;
}

// ---- Coaching Card --------------------------------------------------------

function CoachingCard({ note }: { note: CoachingNote }) {
    const colors = {
        info: "border-blue-500/30 bg-blue-500/5",
        warning: "border-amber-500/30 bg-amber-500/5",
        critical: "border-red-500/30 bg-red-500/5",
    };

    const labels = {
        technique_tip: "Tip",
        objection_warning: "Objectionable",
        impeachment_opportunity: "Impeach",
        door_opened: "Door Opened",
    };

    return (
        <div className={`border rounded-md px-2.5 py-2 text-xs ${colors[note.severity] || colors.info}`}>
            <Badge
                variant="outline"
                className={`text-[10px] mb-1 ${
                    note.severity === "critical"
                        ? "border-red-500/50 text-red-400"
                        : note.severity === "warning"
                          ? "border-amber-500/50 text-amber-400"
                          : "border-blue-500/50 text-blue-400"
                }`}
            >
                {labels[note.type] || note.type}
            </Badge>
            <p className="text-muted-foreground leading-relaxed">{note.content}</p>
        </div>
    );
}
