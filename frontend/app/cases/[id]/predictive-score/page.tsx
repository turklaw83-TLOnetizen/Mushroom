// ---- Predictive Case Score Page ------------------------------------------
// Multi-dimensional case strength dashboard with radar-style dimension
// cards, trend indicators, strengths/vulnerabilities, and score history.
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { routes } from "@/lib/api-routes";
import { queryKeys } from "@/lib/query-keys";
import { formatDate, formatRelativeTime } from "@/lib/constants";
import { usePrep } from "@/hooks/use-prep";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { PredictiveScore, ScoreHistoryEntry } from "@/types/api";

// ---- Constants ----------------------------------------------------------

const DIMENSION_LABELS: Record<string, string> = {
    evidence_strength: "Evidence Strength",
    witness_reliability: "Witness Reliability",
    element_coverage: "Element Coverage",
    legal_authority: "Legal Authority",
    narrative_coherence: "Narrative Coherence",
    adversarial_resilience: "Adversarial Resilience",
};

const DIMENSION_ICONS: Record<string, string> = {
    evidence_strength: "E",
    witness_reliability: "W",
    element_coverage: "C",
    legal_authority: "L",
    narrative_coherence: "N",
    adversarial_resilience: "A",
};

// ---- Score color helpers ------------------------------------------------

function scoreColor(score: number): string {
    if (score >= 80) return "text-emerald-400";
    if (score >= 60) return "text-blue-400";
    if (score >= 40) return "text-amber-400";
    return "text-red-400";
}

function scoreBgColor(score: number): string {
    if (score >= 80) return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
    if (score >= 60) return "bg-blue-500/15 text-blue-400 border-blue-500/30";
    if (score >= 40) return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    return "bg-red-500/15 text-red-400 border-red-500/30";
}

function scoreProgressColor(score: number): string {
    if (score >= 80) return "[&>div]:bg-emerald-500";
    if (score >= 60) return "[&>div]:bg-blue-500";
    if (score >= 40) return "[&>div]:bg-amber-500";
    return "[&>div]:bg-red-500";
}

function gradeColor(grade: string): string {
    switch (grade?.toUpperCase()) {
        case "A": return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
        case "B": return "bg-blue-500/15 text-blue-400 border-blue-500/30";
        case "C": return "bg-amber-500/15 text-amber-400 border-amber-500/30";
        case "D": return "bg-orange-500/15 text-orange-400 border-orange-500/30";
        case "F": return "bg-red-500/15 text-red-400 border-red-500/30";
        default: return "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";
    }
}

function trendArrow(trend: string | null): { icon: string; label: string; color: string } {
    switch (trend) {
        case "improving":
            return { icon: "\u2191", label: "Improving", color: "text-emerald-400" };
        case "declining":
            return { icon: "\u2193", label: "Declining", color: "text-red-400" };
        case "stable":
            return { icon: "\u2192", label: "Stable", color: "text-blue-400" };
        default:
            return { icon: "\u2014", label: "No trend data", color: "text-muted-foreground" };
    }
}

function impactBadgeColor(impact: string): string {
    switch (impact?.toLowerCase()) {
        case "high": return "bg-red-500/15 text-red-400 border-red-500/30";
        case "medium": return "bg-amber-500/15 text-amber-400 border-amber-500/30";
        case "low": return "bg-blue-500/15 text-blue-400 border-blue-500/30";
        default: return "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";
    }
}

// ---- Overall Score Hero -------------------------------------------------

function OverallScoreHero({
    score,
    data,
}: {
    score: PredictiveScore;
    data: PredictiveScore;
}) {
    const trend = trendArrow(data.trend);

    return (
        <Card className="glass-card">
            <CardContent className="py-6">
                <div className="flex flex-col sm:flex-row items-center gap-6">
                    {/* Big score */}
                    <div className="text-center min-w-[120px]">
                        <div className={cn("text-5xl font-bold tabular-nums", scoreColor(score.overall_score))}>
                            {score.overall_score}
                        </div>
                        <Badge className={cn("text-sm mt-2", gradeColor(score.overall_grade))}>
                            {score.overall_grade}
                        </Badge>
                    </div>

                    {/* Label and trend */}
                    <div className="flex-1 text-center sm:text-left">
                        <h3 className="text-lg font-semibold">{score.overall_label}</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            Multi-dimensional case strength assessment
                        </p>
                        <Progress
                            value={score.overall_score}
                            className={cn("h-3 mt-3", scoreProgressColor(score.overall_score))}
                        />
                    </div>

                    {/* Trend */}
                    <div className="text-center min-w-[100px]">
                        <span className={cn("text-2xl font-bold", trend.color)}>
                            {trend.icon}
                        </span>
                        <p className={cn("text-xs mt-1", trend.color)}>{trend.label}</p>
                        {data.previous_score !== null && (
                            <p className="text-xs text-muted-foreground mt-0.5">
                                Previous: {data.previous_score}
                            </p>
                        )}
                    </div>
                </div>

                {score.computed_at && (
                    <p className="text-xs text-muted-foreground mt-4 text-center sm:text-left">
                        Computed {formatRelativeTime(score.computed_at)}
                    </p>
                )}
            </CardContent>
        </Card>
    );
}

// ---- Dimension Card -----------------------------------------------------

function DimensionCard({
    dimensionKey,
    dimension,
}: {
    dimensionKey: string;
    dimension: { score: number; grade: string; signals: string[]; concerns: string[] };
}) {
    const label = DIMENSION_LABELS[dimensionKey] || dimensionKey.replace(/_/g, " ");
    const icon = DIMENSION_ICONS[dimensionKey] || "?";

    return (
        <Card className="hover:border-primary/20 transition-colors">
            <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className={cn(
                            "flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold",
                            scoreBgColor(dimension.score),
                        )}>
                            {icon}
                        </div>
                        <CardTitle className="text-sm font-medium">{label}</CardTitle>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className={cn("text-sm font-bold tabular-nums", scoreColor(dimension.score))}>
                            {dimension.score}
                        </span>
                        <Badge className={cn("text-xs", gradeColor(dimension.grade))}>
                            {dimension.grade}
                        </Badge>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="space-y-3">
                <Progress
                    value={dimension.score}
                    className={cn("h-2", scoreProgressColor(dimension.score))}
                />

                {/* Signals (green bullets) */}
                {dimension.signals.length > 0 && (
                    <div className="space-y-1">
                        {dimension.signals.map((signal, i) => (
                            <div key={i} className="flex items-start gap-2 text-xs">
                                <span className="text-emerald-400 mt-0.5 shrink-0">+</span>
                                <span className="text-muted-foreground">{signal}</span>
                            </div>
                        ))}
                    </div>
                )}

                {/* Concerns (red bullets) */}
                {dimension.concerns.length > 0 && (
                    <div className="space-y-1">
                        {dimension.concerns.map((concern, i) => (
                            <div key={i} className="flex items-start gap-2 text-xs">
                                <span className="text-red-400 mt-0.5 shrink-0">-</span>
                                <span className="text-muted-foreground">{concern}</span>
                            </div>
                        ))}
                    </div>
                )}

                {dimension.signals.length === 0 && dimension.concerns.length === 0 && (
                    <p className="text-xs text-muted-foreground italic">
                        No detailed signals available
                    </p>
                )}
            </CardContent>
        </Card>
    );
}

// ---- Strengths Section --------------------------------------------------

function StrengthsSection({
    strengths,
}: {
    strengths: PredictiveScore["top_strengths"];
}) {
    if (!strengths?.length) return null;

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-base">Top Strengths</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-2">
                    {strengths.map((s, i) => (
                        <div
                            key={i}
                            className="flex items-start gap-3 py-2 border-b last:border-0"
                        >
                            <span className="text-emerald-400 text-sm font-bold shrink-0 mt-0.5">
                                #{i + 1}
                            </span>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm">{s.signal}</p>
                                <p className="text-xs text-muted-foreground mt-0.5">
                                    {DIMENSION_LABELS[s.dimension] || s.dimension}
                                </p>
                            </div>
                            <Badge className={cn("text-[10px] shrink-0", impactBadgeColor(s.impact))}>
                                {s.impact}
                            </Badge>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

// ---- Vulnerabilities Section --------------------------------------------

function VulnerabilitiesSection({
    vulnerabilities,
}: {
    vulnerabilities: PredictiveScore["top_vulnerabilities"];
}) {
    if (!vulnerabilities?.length) return null;

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-base">Top Vulnerabilities</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-3">
                    {vulnerabilities.map((v, i) => (
                        <div
                            key={i}
                            className="py-2 border-b last:border-0"
                        >
                            <div className="flex items-start gap-3">
                                <span className="text-red-400 text-sm font-bold shrink-0 mt-0.5">
                                    #{i + 1}
                                </span>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm">{v.concern}</p>
                                    <p className="text-xs text-muted-foreground mt-0.5">
                                        {DIMENSION_LABELS[v.dimension] || v.dimension}
                                    </p>
                                </div>
                                <Badge className={cn("text-[10px] shrink-0", impactBadgeColor(v.impact))}>
                                    {v.impact}
                                </Badge>
                            </div>
                            {v.suggested_action && (
                                <div className="ml-8 mt-1.5 text-xs text-blue-400 bg-blue-500/10 rounded px-2 py-1">
                                    Action: {v.suggested_action}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

// ---- Score History Timeline ---------------------------------------------

function ScoreHistory({
    history,
    isLoading,
}: {
    history: ScoreHistoryEntry[];
    isLoading: boolean;
}) {
    if (isLoading) {
        return <Skeleton className="h-32 w-full" />;
    }

    if (!history?.length) return null;

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-base">
                    Score History ({history.length} snapshot{history.length !== 1 ? "s" : ""})
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="space-y-2">
                    {history.map((entry, i) => (
                        <div
                            key={i}
                            className="flex items-center gap-4 py-2 border-b last:border-0"
                        >
                            <div className={cn(
                                "text-lg font-bold tabular-nums w-12 text-center",
                                scoreColor(entry.overall_score),
                            )}>
                                {entry.overall_score}
                            </div>
                            <Badge className={cn("text-xs", gradeColor(entry.overall_grade))}>
                                {entry.overall_grade}
                            </Badge>
                            <span className="text-sm text-muted-foreground flex-1">
                                {entry.overall_label}
                            </span>
                            <span className="text-xs text-muted-foreground shrink-0">
                                {formatDate(entry.computed_at)}
                            </span>
                            {/* Mini dimension breakdown */}
                            {entry.dimension_scores && (
                                <div className="hidden lg:flex items-center gap-1">
                                    {Object.entries(entry.dimension_scores).map(([dim, val]) => (
                                        <span
                                            key={dim}
                                            className={cn("text-[10px] font-mono px-1 rounded", scoreColor(val as number))}
                                            title={DIMENSION_LABELS[dim] || dim}
                                        >
                                            {DIMENSION_ICONS[dim]}:{val}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

// ---- Loading Skeleton ---------------------------------------------------

function PageSkeleton() {
    return (
        <div className="space-y-6">
            <Skeleton className="h-36 w-full" />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-48 w-full" />
                ))}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Skeleton className="h-40 w-full" />
                <Skeleton className="h-40 w-full" />
            </div>
        </div>
    );
}

// ---- Main Page ----------------------------------------------------------

export default function PredictiveScorePage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const { activePrepId } = usePrep();

    // Fetch current score
    const scoreQuery = useQuery({
        queryKey: [...queryKeys.predictiveScore.score(caseId, activePrepId || "")],
        queryFn: () =>
            api.get<{ status: string; score: PredictiveScore }>(
                routes.predictiveScore.score(caseId, activePrepId!),
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    // Fetch score history
    const historyQuery = useQuery({
        queryKey: [...queryKeys.predictiveScore.history(caseId, activePrepId || "")],
        queryFn: () =>
            api.get<{ status: string; history: ScoreHistoryEntry[]; total_snapshots: number }>(
                routes.predictiveScore.history(caseId, activePrepId!),
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    // Refresh score mutation
    const refreshMutation = useMutation({
        mutationFn: () =>
            api.get<{ status: string; score: PredictiveScore }>(
                routes.predictiveScore.score(caseId, activePrepId!) + "?save=true",
                { getToken },
            ),
        onSuccess: () => {
            toast.success("Score refreshed");
            queryClient.invalidateQueries({
                queryKey: [...queryKeys.predictiveScore.score(caseId, activePrepId || "")],
            });
            queryClient.invalidateQueries({
                queryKey: [...queryKeys.predictiveScore.history(caseId, activePrepId || "")],
            });
        },
        onError: () => toast.error("Failed to refresh score"),
    });

    const score = scoreQuery.data?.score;
    const history = historyQuery.data?.history ?? [];

    // No prep selected
    if (!activePrepId) {
        return (
            <div className="space-y-6">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">Predictive Case Score</h2>
                    <p className="text-sm text-muted-foreground mt-1">
                        Multi-dimensional case strength analysis
                    </p>
                </div>
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        Select a preparation to view the predictive case score.
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">Predictive Case Score</h2>
                    <p className="text-sm text-muted-foreground mt-1">
                        Multi-dimensional case strength analysis
                    </p>
                </div>
                <Button
                    onClick={() => refreshMutation.mutate()}
                    disabled={refreshMutation.isPending}
                    variant="outline"
                    size="sm"
                >
                    {refreshMutation.isPending ? "Computing..." : "Refresh Score"}
                </Button>
            </div>

            {scoreQuery.isLoading ? (
                <PageSkeleton />
            ) : scoreQuery.isError ? (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        Failed to load predictive score. Make sure analysis has been run.
                    </CardContent>
                </Card>
            ) : !score ? (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center space-y-3">
                        <p className="text-muted-foreground">
                            No predictive score available. Run analysis first, then compute the score.
                        </p>
                        <Button
                            onClick={() => refreshMutation.mutate()}
                            disabled={refreshMutation.isPending}
                        >
                            {refreshMutation.isPending ? "Computing..." : "Compute Score"}
                        </Button>
                    </CardContent>
                </Card>
            ) : (
                <>
                    {/* Overall Score Hero */}
                    <OverallScoreHero score={score} data={score} />

                    {/* Six Dimension Cards — 2x3 grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {Object.entries(score.dimensions).map(([key, dim]) => (
                            <DimensionCard
                                key={key}
                                dimensionKey={key}
                                dimension={dim}
                            />
                        ))}
                    </div>

                    {/* Strengths and Vulnerabilities */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <StrengthsSection strengths={score.top_strengths} />
                        <VulnerabilitiesSection vulnerabilities={score.top_vulnerabilities} />
                    </div>

                    {/* Score History */}
                    <ScoreHistory history={history} isLoading={historyQuery.isLoading} />
                </>
            )}
        </div>
    );
}
