"use client";
// ---- Quality & Cost Analytics Page ---------------------------------------
// Analysis quality scores, draft quality rubrics, and LLM cost breakdown.

import { useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

// ---- Types ----------------------------------------------------------------

interface ModuleScore {
    module: string;
    score: number;
    grade: string;
    details?: string;
}

interface AnalysisQuality {
    overall_score: number;
    overall_grade: string;
    modules: ModuleScore[];
}

interface RubricBreakdown {
    structure: number;
    citations: number;
    argumentation: number;
    style: number;
    completeness: number;
}

interface DraftScore {
    draft_name: string;
    score: number;
    grade: string;
    rubric: RubricBreakdown;
    created_at?: string;
}

interface DraftQuality {
    overall_score: number;
    overall_grade: string;
    drafts: DraftScore[];
}

interface CostByProvider {
    provider: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    cost: number;
}

interface CostByNode {
    node: string;
    calls: number;
    input_tokens: number;
    output_tokens: number;
    cost: number;
}

interface CostPerRun {
    run_id: string;
    started_at: string;
    total_cost: number;
    total_tokens: number;
}

interface CostData {
    total_cost: number;
    total_tokens: number;
    total_input_tokens: number;
    total_output_tokens: number;
    by_provider: CostByProvider[];
    by_node: CostByNode[];
    per_run: CostPerRun[];
}

// ---- Helpers --------------------------------------------------------------

function gradeColor(grade: string): string {
    switch (grade?.toUpperCase()) {
        case "A": return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
        case "B": return "bg-blue-500/15 text-blue-400 border-blue-500/30";
        case "C": return "bg-yellow-500/15 text-yellow-400 border-yellow-500/30";
        case "D": return "bg-orange-500/15 text-orange-400 border-orange-500/30";
        case "F": return "bg-red-500/15 text-red-400 border-red-500/30";
        default: return "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";
    }
}

function gradeTextColor(grade: string): string {
    switch (grade?.toUpperCase()) {
        case "A": return "text-emerald-400";
        case "B": return "text-blue-400";
        case "C": return "text-yellow-400";
        case "D": return "text-orange-400";
        case "F": return "text-red-400";
        default: return "text-zinc-400";
    }
}

function scoreToGrade(score: number): string {
    if (score >= 90) return "A";
    if (score >= 80) return "B";
    if (score >= 70) return "C";
    if (score >= 60) return "D";
    return "F";
}

function formatTokens(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return String(n);
}

function formatCost(n: number): string {
    if (n < 0.01) return "<$0.01";
    return `$${n.toFixed(2)}`;
}

// ---- Score Card Component -------------------------------------------------

function ScoreCard({
    label,
    score,
    grade,
    details,
}: {
    label: string;
    score: number;
    grade: string;
    details?: string;
}) {
    return (
        <Card>
            <CardContent className="py-4">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium capitalize">
                        {label.replace(/_/g, " ")}
                    </span>
                    <div className="flex items-center gap-2">
                        <span className={cn("text-sm font-bold", gradeTextColor(grade))}>
                            {score}
                        </span>
                        <Badge className={cn("text-xs", gradeColor(grade))}>
                            {grade}
                        </Badge>
                    </div>
                </div>
                <Progress value={score} className="h-2" />
                {details && (
                    <p className="text-xs text-muted-foreground mt-2">{details}</p>
                )}
            </CardContent>
        </Card>
    );
}

// ---- Overall Score Header -------------------------------------------------

function OverallScore({
    score,
    grade,
    label,
}: {
    score: number;
    grade: string;
    label: string;
}) {
    return (
        <Card className="glass-card">
            <CardContent className="py-6">
                <div className="flex items-center gap-6">
                    <div className="text-center">
                        <div className={cn("text-4xl font-bold", gradeTextColor(grade))}>
                            {score}
                        </div>
                        <div className={cn("text-2xl font-bold", gradeTextColor(grade))}>
                            {grade}
                        </div>
                    </div>
                    <div className="flex-1">
                        <h3 className="text-lg font-semibold">{label}</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            {score >= 80
                                ? "Excellent quality across all dimensions."
                                : score >= 60
                                    ? "Good quality with room for improvement."
                                    : "Quality needs attention in several areas."}
                        </p>
                        <Progress value={score} className="h-3 mt-3" />
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

// ---- Rubric Breakdown Component -------------------------------------------

function RubricCard({ draft }: { draft: DraftScore }) {
    const rubricKeys: (keyof RubricBreakdown)[] = [
        "structure", "citations", "argumentation", "style", "completeness",
    ];

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium">{draft.draft_name}</CardTitle>
                    <div className="flex items-center gap-2">
                        <span className={cn("text-sm font-bold", gradeTextColor(draft.grade))}>
                            {draft.score}
                        </span>
                        <Badge className={cn("text-xs", gradeColor(draft.grade))}>
                            {draft.grade}
                        </Badge>
                    </div>
                </div>
                {draft.created_at && (
                    <p className="text-xs text-muted-foreground">{draft.created_at}</p>
                )}
            </CardHeader>
            <CardContent className="space-y-2">
                {rubricKeys.map((key) => {
                    const val = draft.rubric[key];
                    const g = scoreToGrade(val);
                    return (
                        <div key={key}>
                            <div className="flex items-center justify-between text-xs mb-1">
                                <span className="capitalize text-muted-foreground">{key}</span>
                                <span className={cn("font-semibold", gradeTextColor(g))}>{val}</span>
                            </div>
                            <Progress value={val} className="h-1.5" />
                        </div>
                    );
                })}
            </CardContent>
        </Card>
    );
}

// ---- Loading Skeleton -----------------------------------------------------

function TabSkeleton() {
    return (
        <div className="space-y-4">
            <Skeleton className="h-28 w-full" />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-24 w-full" />
                ))}
            </div>
        </div>
    );
}

// ---- Main Page ------------------------------------------------------------

export default function QualityPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();

    // Analysis quality query
    const analysisQuery = useQuery({
        queryKey: ["quality-analysis", caseId],
        queryFn: () => api.get<AnalysisQuality>(`/cases/${caseId}/quality/analysis`, { getToken }),
    });

    // Draft quality query
    const draftQuery = useQuery({
        queryKey: ["quality-drafts", caseId],
        queryFn: () => api.get<DraftQuality>(`/cases/${caseId}/quality/drafts`, { getToken }),
    });

    // LLM costs query
    const costQuery = useQuery({
        queryKey: ["quality-costs", caseId],
        queryFn: () => api.get<CostData>(`/cases/${caseId}/quality/costs`, { getToken }),
    });

    // Sort nodes by cost descending for display
    const sortedNodes = useMemo(() => {
        if (!costQuery.data?.by_node) return [];
        return [...costQuery.data.by_node].sort((a, b) => b.cost - a.cost);
    }, [costQuery.data]);

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h2 className="text-xl font-bold tracking-tight">Quality & Cost Analytics</h2>
                <p className="text-sm text-muted-foreground mt-1">
                    Analysis scores, draft rubrics, and LLM cost breakdown
                </p>
            </div>

            <Tabs defaultValue="analysis" className="space-y-4">
                <TabsList variant="line">
                    <TabsTrigger value="analysis">Analysis Quality</TabsTrigger>
                    <TabsTrigger value="drafts">Draft Quality</TabsTrigger>
                    <TabsTrigger value="costs">LLM Costs</TabsTrigger>
                </TabsList>

                {/* ---- Analysis Quality Tab ---- */}
                <TabsContent value="analysis" className="space-y-4">
                    {analysisQuery.isLoading ? (
                        <TabSkeleton />
                    ) : analysisQuery.isError ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                Failed to load analysis quality data.
                            </CardContent>
                        </Card>
                    ) : !analysisQuery.data ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No analysis quality data available. Run analysis first.
                            </CardContent>
                        </Card>
                    ) : (
                        <>
                            <OverallScore
                                score={analysisQuery.data.overall_score}
                                grade={analysisQuery.data.overall_grade}
                                label="Overall Analysis Quality"
                            />
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {analysisQuery.data.modules.map((mod) => (
                                    <ScoreCard
                                        key={mod.module}
                                        label={mod.module}
                                        score={mod.score}
                                        grade={mod.grade}
                                        details={mod.details}
                                    />
                                ))}
                            </div>
                        </>
                    )}
                </TabsContent>

                {/* ---- Draft Quality Tab ---- */}
                <TabsContent value="drafts" className="space-y-4">
                    {draftQuery.isLoading ? (
                        <TabSkeleton />
                    ) : draftQuery.isError ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                Failed to load draft quality data.
                            </CardContent>
                        </Card>
                    ) : !draftQuery.data ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No draft quality data available. Generate drafts first.
                            </CardContent>
                        </Card>
                    ) : (
                        <>
                            <OverallScore
                                score={draftQuery.data.overall_score}
                                grade={draftQuery.data.overall_grade}
                                label="Overall Draft Quality"
                            />
                            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                                Rubric Breakdown by Draft ({draftQuery.data.drafts.length})
                            </h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {draftQuery.data.drafts.map((draft, i) => (
                                    <RubricCard key={i} draft={draft} />
                                ))}
                            </div>
                        </>
                    )}
                </TabsContent>

                {/* ---- LLM Costs Tab ---- */}
                <TabsContent value="costs" className="space-y-4">
                    {costQuery.isLoading ? (
                        <TabSkeleton />
                    ) : costQuery.isError ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                Failed to load cost data.
                            </CardContent>
                        </Card>
                    ) : !costQuery.data ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No cost data available. Run analysis first.
                            </CardContent>
                        </Card>
                    ) : (
                        <>
                            {/* Cost Summary */}
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <Card>
                                    <CardContent className="pt-4 pb-3">
                                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                            Total Cost
                                        </p>
                                        <p className="text-2xl font-bold mt-1">
                                            {formatCost(costQuery.data.total_cost)}
                                        </p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="pt-4 pb-3">
                                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                            Total Tokens
                                        </p>
                                        <p className="text-2xl font-bold mt-1">
                                            {formatTokens(costQuery.data.total_tokens)}
                                        </p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="pt-4 pb-3">
                                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                            Input Tokens
                                        </p>
                                        <p className="text-2xl font-bold mt-1">
                                            {formatTokens(costQuery.data.total_input_tokens)}
                                        </p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="pt-4 pb-3">
                                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                            Output Tokens
                                        </p>
                                        <p className="text-2xl font-bold mt-1">
                                            {formatTokens(costQuery.data.total_output_tokens)}
                                        </p>
                                    </CardContent>
                                </Card>
                            </div>

                            {/* Cost by Provider */}
                            {costQuery.data.by_provider.length > 0 && (
                                <Card>
                                    <CardHeader className="pb-3">
                                        <CardTitle className="text-base">Cost by Provider</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="divide-y">
                                            <div className="grid grid-cols-5 gap-4 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                                <span>Provider</span>
                                                <span>Model</span>
                                                <span className="text-right">Input</span>
                                                <span className="text-right">Output</span>
                                                <span className="text-right">Cost</span>
                                            </div>
                                            {costQuery.data.by_provider.map((p, i) => (
                                                <div key={i} className="grid grid-cols-5 gap-4 py-2.5 text-sm">
                                                    <span className="font-medium capitalize">{p.provider}</span>
                                                    <span className="text-muted-foreground font-mono text-xs">
                                                        {p.model}
                                                    </span>
                                                    <span className="text-right tabular-nums">
                                                        {formatTokens(p.input_tokens)}
                                                    </span>
                                                    <span className="text-right tabular-nums">
                                                        {formatTokens(p.output_tokens)}
                                                    </span>
                                                    <span className="text-right font-semibold tabular-nums">
                                                        {formatCost(p.cost)}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            )}

                            {/* Cost by Node */}
                            {sortedNodes.length > 0 && (
                                <Card>
                                    <CardHeader className="pb-3">
                                        <CardTitle className="text-base">Cost by Analysis Node</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="divide-y">
                                            <div className="grid grid-cols-5 gap-4 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                                <span>Node</span>
                                                <span className="text-right">Calls</span>
                                                <span className="text-right">Input</span>
                                                <span className="text-right">Output</span>
                                                <span className="text-right">Cost</span>
                                            </div>
                                            {sortedNodes.map((n, i) => {
                                                const pct = costQuery.data!.total_cost > 0
                                                    ? (n.cost / costQuery.data!.total_cost) * 100
                                                    : 0;
                                                return (
                                                    <div key={i} className="py-2.5">
                                                        <div className="grid grid-cols-5 gap-4 text-sm">
                                                            <span className="font-medium capitalize">
                                                                {n.node.replace(/_/g, " ")}
                                                            </span>
                                                            <span className="text-right tabular-nums text-muted-foreground">
                                                                {n.calls}
                                                            </span>
                                                            <span className="text-right tabular-nums">
                                                                {formatTokens(n.input_tokens)}
                                                            </span>
                                                            <span className="text-right tabular-nums">
                                                                {formatTokens(n.output_tokens)}
                                                            </span>
                                                            <span className="text-right font-semibold tabular-nums">
                                                                {formatCost(n.cost)}
                                                            </span>
                                                        </div>
                                                        <Progress
                                                            value={pct}
                                                            className="h-1 mt-1.5"
                                                        />
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </CardContent>
                                </Card>
                            )}

                            {/* Cost per Analysis Run */}
                            {costQuery.data.per_run.length > 0 && (
                                <Card>
                                    <CardHeader className="pb-3">
                                        <CardTitle className="text-base">Cost per Analysis Run</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="divide-y">
                                            <div className="grid grid-cols-4 gap-4 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                                <span>Run</span>
                                                <span>Started</span>
                                                <span className="text-right">Tokens</span>
                                                <span className="text-right">Cost</span>
                                            </div>
                                            {costQuery.data.per_run.map((run, i) => (
                                                <div key={i} className="grid grid-cols-4 gap-4 py-2.5 text-sm">
                                                    <span className="font-mono text-xs text-muted-foreground">
                                                        {run.run_id.slice(0, 8)}
                                                    </span>
                                                    <span className="text-muted-foreground text-xs">
                                                        {run.started_at}
                                                    </span>
                                                    <span className="text-right tabular-nums">
                                                        {formatTokens(run.total_tokens)}
                                                    </span>
                                                    <span className="text-right font-semibold tabular-nums">
                                                        {formatCost(run.total_cost)}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            )}
                        </>
                    )}
                </TabsContent>
            </Tabs>
        </div>
    );
}
