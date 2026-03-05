// ---- Analysis Tab (Full AI Pipeline + Result Display) --------------------
// Sub-tabs: Pipeline | Summary | Devil's Advocate | Investigation | Readiness | Chat
"use client";

import { useState, useMemo, useCallback } from "react";
import { useParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { usePrep } from "@/hooks/use-prep";
import { useRole } from "@/hooks/use-role";
import { usePrepState } from "@/hooks/use-prep-state";
import { useWorkerStatus } from "@/hooks/use-worker-status";
import { useAnalysisProgress } from "@/hooks/use-analysis-progress";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { useKeyboardShortcuts } from "@/hooks/use-keyboard-shortcuts";
import { ResultSection } from "@/components/analysis/result-section";
import { MarkdownContent } from "@/components/analysis/markdown-content";
import { AiChat } from "@/components/analysis/ai-chat";
import { ModuleNotes } from "@/components/shared/module-notes";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { api } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { InvestigationItem } from "@/hooks/use-prep-state";

// ---- Module Definitions -------------------------------------------------

const analysisModules = [
    { key: "case_summary", label: "Case Summary", icon: "📋", description: "Overall case narrative and key findings" },
    { key: "charges", label: "Charges Analysis", icon: "⚖️", description: "Charge elements, statutes, and defenses" },
    { key: "timeline", label: "Timeline", icon: "📅", description: "Chronological sequence of events" },
    { key: "witnesses", label: "Witness Analysis", icon: "👤", description: "Witness profiles, goals, and credibility" },
    { key: "evidence_foundations", label: "Evidence", icon: "🔍", description: "Admissibility analysis and foundations" },
    { key: "legal_elements", label: "Legal Elements", icon: "📜", description: "Elements of each charge and element-by-element analysis" },
    { key: "consistency_check", label: "Consistency Check", icon: "✓", description: "Cross-reference witness statements and evidence" },
    { key: "investigation_plan", label: "Investigation Plan", icon: "🔬", description: "Action items for further investigation" },
    { key: "cross_examination_plan", label: "Cross Examination", icon: "❓", description: "Question strategies for opposing witnesses" },
    { key: "direct_examination_plan", label: "Direct Examination", icon: "💬", description: "Question outlines for friendly witnesses" },
    { key: "strategy_notes", label: "Strategy", icon: "🎯", description: "Defense strategy recommendations" },
    { key: "devils_advocate_notes", label: "Devil's Advocate", icon: "😈", description: "Prosecution's strongest arguments" },
    { key: "entities", label: "Entities", icon: "🏷️", description: "People, places, and organizations mentioned" },
    { key: "voir_dire", label: "Voir Dire", icon: "🗳️", description: "Jury selection strategy and questions" },
];

// ---- Helpers ------------------------------------------------------------

function statusColor(status: string): string {
    switch (status) {
        case "complete": return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
        case "running": return "bg-blue-500/15 text-blue-400 border-blue-500/30 animate-pulse";
        case "error": return "bg-red-500/15 text-red-400 border-red-500/30";
        default: return "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";
    }
}

function ProgressBar({ percent, label }: { percent: number; label?: string }) {
    const clamped = Math.min(100, Math.max(0, percent));
    return (
        <div className="space-y-1.5">
            {label && (
                <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground font-medium">{label}</p>
                    <p className="text-xs font-semibold tabular-nums">{Math.round(clamped)}%</p>
                </div>
            )}
            <div className="analysis-progress">
                <Progress value={clamped} className="h-2.5" />
            </div>
        </div>
    );
}

// ---- Module Detail Modal ------------------------------------------------

interface ModuleDetailProps {
    label: string;
    icon: string;
    description: string;
    data: unknown;
    onClose: () => void;
}

function ModuleDetail({ label, icon, description, data, onClose }: ModuleDetailProps) {
    const renderValue = (val: unknown): React.ReactNode => {
        if (val === null || val === undefined || val === "")
            return <p className="text-sm text-muted-foreground italic">Analysis not yet run for this module.</p>;

        if (typeof val === "string") {
            if (val.length === 0) return <p className="text-sm text-muted-foreground italic">Empty</p>;
            return <MarkdownContent content={val} />;
        }

        if (Array.isArray(val)) {
            if (val.length === 0) return <p className="text-sm text-muted-foreground italic">No items</p>;
            return (
                <div className="space-y-2">
                    {val.map((item, i) => (
                        <Card key={i} className="bg-accent/20 border-dashed">
                            <CardContent className="py-3">
                                {typeof item === "object" && item !== null ? (
                                    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
                                        {Object.entries(item as Record<string, unknown>).map(([k, v]) => (
                                            <div key={k} className="contents">
                                                <dt className="font-medium text-muted-foreground capitalize">{k.replace(/_/g, " ")}</dt>
                                                <dd>{String(v)}</dd>
                                            </div>
                                        ))}
                                    </dl>
                                ) : (
                                    <span className="text-sm">{String(item)}</span>
                                )}
                            </CardContent>
                        </Card>
                    ))}
                </div>
            );
        }

        if (typeof val === "object" && val !== null) {
            const obj = val as Record<string, unknown>;
            return (
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
                    {Object.entries(obj).map(([k, v]) => (
                        <div key={k} className="contents">
                            <dt className="font-medium text-muted-foreground capitalize">{k.replace(/_/g, " ")}</dt>
                            <dd className="whitespace-pre-wrap">{typeof v === "object" ? JSON.stringify(v, null, 2) : String(v)}</dd>
                        </div>
                    ))}
                </dl>
            );
        }

        return <p className="text-sm">{String(val)}</p>;
    };

    return (
        <div
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={onClose}
        >
            <Card
                className="w-full max-w-3xl max-h-[85vh] overflow-auto shadow-2xl"
                onClick={(e) => e.stopPropagation()}
            >
                <CardHeader className="flex flex-row items-start justify-between sticky top-0 bg-card z-10 border-b">
                    <div>
                        <CardTitle className="flex items-center gap-2 text-lg">
                            <span>{icon}</span> {label}
                        </CardTitle>
                        <p className="text-sm text-muted-foreground mt-1">{description}</p>
                    </div>
                    <Button variant="ghost" size="icon" onClick={onClose} className="shrink-0" aria-label="Close">
                        <span aria-hidden="true">✕</span>
                    </Button>
                </CardHeader>
                <CardContent className="pt-4">{renderValue(data)}</CardContent>
            </Card>
        </div>
    );
}

// ---- Priority Badge Helper -----------------------------------------------

function priorityBadge(priority: string) {
    switch (priority?.toLowerCase()) {
        case "high":
        case "critical":
            return <Badge className="bg-red-500/15 text-red-400 border-red-500/30 text-xs">{priority}</Badge>;
        case "medium":
            return <Badge className="bg-amber-500/15 text-amber-400 border-amber-500/30 text-xs">{priority}</Badge>;
        default:
            return <Badge variant="outline" className="text-xs">{priority || "Normal"}</Badge>;
    }
}

// ---- Readiness Grade Helper -----------------------------------------------

function readinessGrade(score: number): { letter: string; color: string } {
    if (score >= 90) return { letter: "A", color: "text-emerald-400" };
    if (score >= 80) return { letter: "B", color: "text-blue-400" };
    if (score >= 70) return { letter: "C", color: "text-yellow-400" };
    if (score >= 60) return { letter: "D", color: "text-orange-400" };
    return { letter: "F", color: "text-red-400" };
}

// ---- Main Page ----------------------------------------------------------

export default function AnalysisPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, preparations, isLoading: prepLoading } = usePrep();
    const { canEdit } = useRole();
    const { status: workerStatus, reconnect } = useWorkerStatus(caseId);
    const [selectedModule, setSelectedModule] = useState<string | null>(null);

    const isAnalysisRunning = workerStatus.analysis.status === "running";
    const isIngestionRunning = workerStatus.ingestion.status === "running";

    // Poll progress while analysis is running
    const { progress } = useAnalysisProgress(caseId, activePrepId, isAnalysisRunning);

    // Shared prep state (analysis results)
    const { state: analysisState, sections, isLoading: stateLoading } = usePrepState(
        caseId,
        activePrepId,
        { refetchInterval: isAnalysisRunning ? 5000 : false },
    );

    // Count completed modules
    const completedCount = useMemo(() => {
        return analysisModules.filter((mod) => {
            const data = analysisState[mod.key];
            return data !== undefined && data !== null && data !== "" &&
                (Array.isArray(data) ? data.length > 0 : true);
        }).length;
    }, [analysisState]);

    // Start Analysis mutation
    const startAnalysis = useMutationWithToast({
        mutationFn: () =>
            api.post(`/cases/${caseId}/analysis/start`, {
                prep_id: activePrepId,
                force_rerun: false,
            }, { getToken }),
        successMessage: "Analysis started — modules will update as they complete",
        errorMessage: "Failed to start analysis",
        onSuccess: () => reconnect(),
    });

    // Stop Analysis mutation
    const stopAnalysis = useMutationWithToast({
        mutationFn: () =>
            api.post(`/cases/${caseId}/analysis/stop?prep_id=${activePrepId}`, {}, { getToken }),
        successMessage: "Analysis stopping...",
        errorMessage: "Failed to stop analysis",
    });

    // Start Ingestion mutation
    const startIngestion = useMutationWithToast({
        mutationFn: () =>
            api.post(`/cases/${caseId}/analysis/ingestion/start`, {
                force_ocr: false,
            }, { getToken }),
        successMessage: "Document ingestion started",
        errorMessage: "Failed to start ingestion",
        onSuccess: () => reconnect(),
    });

    // Keyboard shortcuts
    useKeyboardShortcuts({
        onEscape: () => setSelectedModule(null),
    });

    const selectedMod = analysisModules.find((m) => m.key === selectedModule);

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">No preparations found. Create one to run analysis.</p>
            </div>
        );
    }

    // Readiness score data
    const readinessData = sections.readinessScore;
    const readinessNum = typeof readinessData === "number"
        ? readinessData
        : (readinessData as { overall_score?: number } | null)?.overall_score ?? null;

    return (
        <Tabs defaultValue="pipeline" className="space-y-4">
            <TabsList variant="line">
                <TabsTrigger value="pipeline">Pipeline</TabsTrigger>
                <TabsTrigger value="summary">
                    Summary {sections.caseSummary && <span className="ml-1 text-emerald-400" aria-hidden="true">●</span>}
                </TabsTrigger>
                <TabsTrigger value="devils-advocate">
                    Devil&apos;s Advocate {sections.devilsAdvocate && <span className="ml-1 text-emerald-400" aria-hidden="true">●</span>}
                </TabsTrigger>
                <TabsTrigger value="investigation">
                    Investigation {sections.investigationPlan.length > 0 && <Badge variant="secondary" className="ml-1 text-[10px] py-0 px-1">{sections.investigationPlan.length}</Badge>}
                </TabsTrigger>
                <TabsTrigger value="readiness">
                    Readiness {readinessNum !== null && <Badge variant="secondary" className="ml-1 text-[10px] py-0 px-1">{readinessNum}</Badge>}
                </TabsTrigger>
                <TabsTrigger value="chat">
                    💬 Chat
                </TabsTrigger>
            </TabsList>

            {/* ---- Pipeline Tab ---- */}
            <TabsContent value="pipeline" className="space-y-6">
                {/* Worker Status + Controls */}
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base flex items-center justify-between">
                            <span>AI Analysis Engine</span>
                            <Badge variant="outline" className={statusColor(workerStatus.analysis.status)}>
                                {workerStatus.analysis.status}
                            </Badge>
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {isAnalysisRunning && (
                            <div className="space-y-2">
                                <ProgressBar
                                    percent={progress.progress * 100}
                                    label={progress.current_module
                                        ? `${progress.module_description || progress.current_module}`
                                        : "Initializing..."
                                    }
                                />
                                {progress.completed_modules && (
                                    <p className="text-xs text-muted-foreground">
                                        {progress.completed_modules.length}/{progress.total_modules || "?"} modules complete
                                        {progress.tokens_used ? ` · ${progress.tokens_used.toLocaleString()} tokens` : ""}
                                    </p>
                                )}
                            </div>
                        )}

                        <div className="flex gap-4 text-sm text-muted-foreground">
                            <span className="flex items-center gap-1.5">
                                Ingestion: <Badge variant="outline" className={statusColor(workerStatus.ingestion.status)}>{workerStatus.ingestion.status}</Badge>
                            </span>
                            <span className="flex items-center gap-1.5">
                                OCR: <Badge variant="outline" className={statusColor(workerStatus.ocr.status)}>{workerStatus.ocr.status}</Badge>
                            </span>
                            <span className="text-xs ml-auto">
                                {completedCount}/{analysisModules.length} modules populated
                            </span>
                        </div>

                        {canEdit && (
                            <div className="flex gap-2 pt-1">
                                {!isAnalysisRunning ? (
                                    <Button
                                        size="sm"
                                        onClick={() => startAnalysis.mutate({})}
                                        disabled={startAnalysis.isPending || !activePrepId}
                                    >
                                        {startAnalysis.isPending ? "Starting..." : "Run Analysis"}
                                    </Button>
                                ) : (
                                    <Button
                                        size="sm"
                                        variant="destructive"
                                        onClick={() => stopAnalysis.mutate({})}
                                        disabled={stopAnalysis.isPending}
                                    >
                                        {stopAnalysis.isPending ? "Stopping..." : "Stop"}
                                    </Button>
                                )}
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => startIngestion.mutate({})}
                                    disabled={isIngestionRunning || startIngestion.isPending}
                                >
                                    {isIngestionRunning ? "Ingesting..." : startIngestion.isPending ? "Starting..." : "Ingest Documents"}
                                </Button>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {preparations.length > 0 && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span>Active preparation:</span>
                        <Badge variant="secondary">{preparations.find(p => p.id === activePrepId)?.name || activePrepId}</Badge>
                    </div>
                )}

                {/* Module Grid */}
                <div>
                    <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                        Analysis Modules ({completedCount}/{analysisModules.length})
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                        {analysisModules.map((mod) => {
                            const data = analysisState[mod.key];
                            const hasData = data !== undefined && data !== null && data !== "" &&
                                (Array.isArray(data) ? data.length > 0 : true);
                            const isCurrentlyProcessing = isAnalysisRunning && progress.current_module === mod.key;

                            return (
                                <Card
                                    key={mod.key}
                                    className={cn(
                                        "transition-all cursor-pointer hover:shadow-md",
                                        isCurrentlyProcessing
                                            ? "border-[oklch(0.55_0.23_264_/_50%)] shadow-[oklch(0.55_0.23_264_/_10%)] shadow-md animate-pulse"
                                            : hasData
                                                ? "glass-card"
                                                : "border-dashed opacity-60 hover:opacity-100 hover:bg-accent/30",
                                    )}
                                    onClick={() => setSelectedModule(mod.key)}
                                >
                                    <CardContent className="py-4">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span aria-hidden="true">{mod.icon}</span>
                                            <span className="text-sm font-medium">{mod.label}</span>
                                            {isCurrentlyProcessing && (
                                                <span className="ml-auto text-xs text-blue-400">processing</span>
                                            )}
                                            {hasData && !isCurrentlyProcessing && (
                                                <span className="ml-auto text-xs text-emerald-400" aria-hidden="true">✓</span>
                                            )}
                                        </div>
                                        <p className="text-xs text-muted-foreground">
                                            {isCurrentlyProcessing
                                                ? progress.module_description || "Processing..."
                                                : hasData
                                                    ? Array.isArray(data)
                                                        ? `${(data as unknown[]).length} items`
                                                        : typeof data === "string"
                                                            ? `${data.length.toLocaleString()} chars`
                                                            : "Data available"
                                                    : mod.description}
                                        </p>
                                    </CardContent>
                                </Card>
                            );
                        })}
                    </div>
                </div>

                {selectedMod && (
                    <ModuleDetail
                        label={selectedMod.label}
                        icon={selectedMod.icon}
                        description={selectedMod.description}
                        data={analysisState[selectedMod.key]}
                        onClose={() => setSelectedModule(null)}
                    />
                )}
            </TabsContent>

            {/* ---- Summary Tab ---- */}
            <TabsContent value="summary">
                <ResultSection
                    title="Case Summary"
                    icon="📋"
                    isEmpty={!sections.caseSummary}
                    isLoading={stateLoading}
                >
                    <MarkdownContent content={sections.caseSummary!} />
                </ResultSection>
                <ModuleNotes caseId={caseId} prepId={activePrepId} moduleKey="case_summary" />
            </TabsContent>

            {/* ---- Devil's Advocate Tab ---- */}
            <TabsContent value="devils-advocate">
                <ResultSection
                    title="Devil's Advocate"
                    icon="😈"
                    isEmpty={!sections.devilsAdvocate}
                    isLoading={stateLoading}
                    emptyMessage="Run analysis to generate the prosecution's strongest arguments against your case."
                >
                    <MarkdownContent content={sections.devilsAdvocate!} />
                </ResultSection>
                <ModuleNotes caseId={caseId} prepId={activePrepId} moduleKey="devils_advocate" />
            </TabsContent>

            {/* ---- Investigation Plan Tab ---- */}
            <TabsContent value="investigation" className="space-y-4">
                <ResultSection
                    title="Investigation Plan"
                    icon="🔬"
                    isEmpty={sections.investigationPlan.length === 0}
                    isLoading={stateLoading}
                    emptyMessage="Run analysis to generate investigation action items."
                >
                    <div className="space-y-3">
                        {sections.investigationPlan
                            .filter((item: InvestigationItem) => !item._ai_suggests_remove)
                            .map((item: InvestigationItem, i: number) => (
                            <Card key={i} className="bg-accent/20 border-dashed">
                                <CardContent className="py-3">
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="flex-1">
                                            <p className="text-sm font-medium">{item.action}</p>
                                            {item.rationale && (
                                                <p className="text-xs text-muted-foreground mt-1">{item.rationale}</p>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-2 shrink-0">
                                            {priorityBadge(item.priority)}
                                            {item.status && (
                                                <Badge variant="outline" className="text-xs">{item.status}</Badge>
                                            )}
                                        </div>
                                    </div>
                                    {item.assigned_to && (
                                        <p className="text-xs text-muted-foreground mt-2">Assigned: {item.assigned_to}</p>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </ResultSection>
                <ModuleNotes caseId={caseId} prepId={activePrepId} moduleKey="investigation_plan" />
            </TabsContent>

            {/* ---- Readiness Tab ---- */}
            <TabsContent value="readiness">
                <ResultSection
                    title="Case Readiness"
                    icon="🎯"
                    isEmpty={readinessNum === null}
                    isLoading={stateLoading}
                    emptyMessage="Run analysis to calculate case readiness score."
                >
                    {readinessNum !== null && (
                        <div className="space-y-6">
                            {/* Overall Score */}
                            <div className="flex items-center gap-6">
                                <div className="text-center">
                                    <div className={`text-5xl font-bold ${readinessGrade(readinessNum).color}`}>
                                        {readinessNum}
                                    </div>
                                    <div className={`text-2xl font-bold ${readinessGrade(readinessNum).color}`}>
                                        {readinessGrade(readinessNum).letter}
                                    </div>
                                </div>
                                <div className="flex-1">
                                    <h3 className="text-lg font-semibold">Overall Readiness</h3>
                                    <p className="text-sm text-muted-foreground mt-1">
                                        {readinessNum >= 80
                                            ? "Case is well-prepared for trial."
                                            : readinessNum >= 60
                                                ? "Case preparation is progressing. Review gaps below."
                                                : "Significant preparation work remains."}
                                    </p>
                                    <Progress value={readinessNum} className="h-3 mt-3" />
                                </div>
                            </div>

                            {/* Category Breakdown */}
                            {typeof readinessData === "object" && readinessData !== null &&
                                "categories" in readinessData &&
                                readinessData.categories && (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {Object.entries(readinessData.categories).map(([key, cat]) => (
                                        <Card key={key}>
                                            <CardContent className="py-3">
                                                <div className="flex items-center justify-between mb-2">
                                                    <span className="text-sm font-medium capitalize">
                                                        {key.replace(/_/g, " ")}
                                                    </span>
                                                    <span className={`text-sm font-bold ${readinessGrade(cat.score).color}`}>
                                                        {cat.score}
                                                    </span>
                                                </div>
                                                <Progress value={cat.score} className="h-2" />
                                                {cat.notes && (
                                                    <p className="text-xs text-muted-foreground mt-2">{cat.notes}</p>
                                                )}
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </ResultSection>
            </TabsContent>

            {/* ---- Chat Tab ---- */}
            <TabsContent value="chat">
                <AiChat caseId={caseId} prepId={activePrepId} contextModule="general" />
            </TabsContent>
        </Tabs>
    );
}
