"use client";
// ---- Cost Analytics Dashboard ---------------------------------------------
// Global LLM cost tracking, per-case breakdowns, and top spenders.
export const dynamic = "force-dynamic";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { Case, CaseListResponse } from "@/types/api";

// ---- Types ----------------------------------------------------------------

interface ModelBreakdown {
    model: string;
    tokens_in: number;
    tokens_out: number;
    cost: number;
}

interface CostSummary {
    total_tokens_in: number;
    total_tokens_out: number;
    total_cost: number;
    by_model: ModelBreakdown[];
}

interface CaseCosts {
    tokens_in: number;
    tokens_out: number;
    total_cost: number;
    by_model?: ModelBreakdown[];
}

// ---- Helpers --------------------------------------------------------------

/** Format cost with 4 decimal places for per-token cost display */
function fmtTokenCost(cost: number): string {
    return `$${cost.toFixed(4)}`;
}

function formatTokens(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return String(n);
}

// ---- Stat Card ------------------------------------------------------------

function StatCard({
    title,
    value,
    description,
    variant = "default",
}: {
    title: string;
    value: string | number;
    description?: string;
    variant?: "default" | "success" | "warning";
}) {
    const colors = {
        default: "border-border",
        success: "border-green-500/30 bg-green-500/5",
        warning: "border-amber-500/30 bg-amber-500/5",
    };
    return (
        <Card className={colors[variant]}>
            <CardContent className="pt-4 pb-3">
                <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">
                    {title}
                </p>
                <p className="text-2xl font-bold mt-1">{value}</p>
                {description && (
                    <p className="text-xs text-muted-foreground mt-1">{description}</p>
                )}
            </CardContent>
        </Card>
    );
}

// ---- Main Page ------------------------------------------------------------

export default function CostAnalyticsPage() {
    const { getToken } = useAuth();

    // Fetch all cases for per-case cost lookups
    const casesQuery = useQuery({
        queryKey: ["admin-cases-list"],
        queryFn: () =>
            api.get<CaseListResponse>("/cases?per_page=200", { getToken }),
    });

    const cases = casesQuery.data?.items ?? [];

    // Fetch the global cost summary (admin endpoint)
    // Try the first case to get global summary — the /summary endpoint aggregates across all cases
    const summaryQuery = useQuery({
        queryKey: ["admin-cost-summary"],
        queryFn: async () => {
            // Try the global summary endpoint first
            try {
                return await api.get<CostSummary>(
                    "/quality/costs/summary",
                    { getToken },
                );
            } catch {
                // Fallback: aggregate from per-case endpoints
                return null;
            }
        },
    });

    // Fetch per-case costs for all cases
    const perCaseCostsQuery = useQuery({
        queryKey: ["admin-per-case-costs", cases.map((c) => c.id)],
        queryFn: async () => {
            const results: Array<{ case_: Case; costs: CaseCosts }> = [];
            for (const c of cases) {
                try {
                    const costs = await api.get<CaseCosts>(
                        `/cases/${c.id}/quality/costs`,
                        { getToken },
                    );
                    results.push({ case_: c, costs });
                } catch {
                    // Skip cases with no cost data
                }
            }
            return results;
        },
        enabled: cases.length > 0,
    });

    const perCaseCosts = perCaseCostsQuery.data ?? [];

    // Compute aggregated summary from per-case data if global endpoint unavailable
    const summary: CostSummary | null = summaryQuery.data ?? (() => {
        if (perCaseCosts.length === 0) return null;
        const modelMap = new Map<string, ModelBreakdown>();
        let totalIn = 0;
        let totalOut = 0;
        let totalCost = 0;
        for (const { costs } of perCaseCosts) {
            totalIn += costs.tokens_in;
            totalOut += costs.tokens_out;
            totalCost += costs.total_cost;
            if (costs.by_model) {
                for (const mb of costs.by_model) {
                    const existing = modelMap.get(mb.model);
                    if (existing) {
                        existing.tokens_in += mb.tokens_in;
                        existing.tokens_out += mb.tokens_out;
                        existing.cost += mb.cost;
                    } else {
                        modelMap.set(mb.model, { ...mb });
                    }
                }
            }
        }
        return {
            total_tokens_in: totalIn,
            total_tokens_out: totalOut,
            total_cost: totalCost,
            by_model: Array.from(modelMap.values()),
        };
    })();

    // Sort per-case costs by total descending for the "top spenders" section
    const sortedBySpend = [...perCaseCosts].sort(
        (a, b) => b.costs.total_cost - a.costs.total_cost,
    );
    const top5 = sortedBySpend.slice(0, 5);

    const isLoading = casesQuery.isLoading || summaryQuery.isLoading;

    return (
        <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Cost Analytics</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    LLM token usage, cost breakdown by model, and per-case spending
                </p>
            </div>

            {/* Global Summary Cards */}
            {isLoading ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-24 rounded-lg" />
                    ))}
                </div>
            ) : summary ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard
                        title="Total Cost"
                        value={fmtTokenCost(summary.total_cost)}
                        variant="warning"
                    />
                    <StatCard
                        title="Tokens In"
                        value={formatTokens(summary.total_tokens_in)}
                        description="Input / prompt tokens"
                    />
                    <StatCard
                        title="Tokens Out"
                        value={formatTokens(summary.total_tokens_out)}
                        description="Output / completion tokens"
                    />
                    <StatCard
                        title="Cases Tracked"
                        value={perCaseCosts.length}
                        description={`of ${cases.length} total cases`}
                    />
                </div>
            ) : (
                <Card className="border-dashed">
                    <CardContent className="py-8 text-center text-muted-foreground">
                        No cost data available yet. Run analyses to generate cost tracking data.
                    </CardContent>
                </Card>
            )}

            {/* Model Breakdown */}
            {summary && summary.by_model.length > 0 && (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Cost by Model</CardTitle>
                        <CardDescription>Breakdown of spend across LLM providers</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="divide-y">
                            <div className="grid grid-cols-5 gap-4 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                <span>Model</span>
                                <span className="text-right">Tokens In</span>
                                <span className="text-right">Tokens Out</span>
                                <span className="text-right">Cost</span>
                                <span className="text-right">Share</span>
                            </div>
                            {summary.by_model
                                .sort((a, b) => b.cost - a.cost)
                                .map((mb) => (
                                    <div
                                        key={mb.model}
                                        className="grid grid-cols-5 gap-4 py-2.5 text-sm"
                                    >
                                        <span className="font-medium font-mono text-xs truncate">
                                            {mb.model}
                                        </span>
                                        <span className="text-right text-muted-foreground">
                                            {formatTokens(mb.tokens_in)}
                                        </span>
                                        <span className="text-right text-muted-foreground">
                                            {formatTokens(mb.tokens_out)}
                                        </span>
                                        <span className="text-right font-medium">
                                            {fmtTokenCost(mb.cost)}
                                        </span>
                                        <span className="text-right text-muted-foreground">
                                            {summary.total_cost > 0
                                                ? `${((mb.cost / summary.total_cost) * 100).toFixed(1)}%`
                                                : "—"}
                                        </span>
                                    </div>
                                ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Per-Case Cost Table */}
            {perCaseCostsQuery.isLoading ? (
                <div className="space-y-2">
                    {Array.from({ length: 5 }).map((_, i) => (
                        <Skeleton key={i} className="h-12 w-full rounded-lg" />
                    ))}
                </div>
            ) : perCaseCosts.length > 0 ? (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Per-Case Costs</CardTitle>
                        <CardDescription>
                            Token usage and cost for each case with analysis data
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="divide-y">
                            <div className="grid grid-cols-5 gap-4 py-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                <span className="col-span-2">Case</span>
                                <span className="text-right">Tokens In</span>
                                <span className="text-right">Tokens Out</span>
                                <span className="text-right">Total Cost</span>
                            </div>
                            {sortedBySpend.map(({ case_, costs }) => (
                                <div
                                    key={case_.id}
                                    className="grid grid-cols-5 gap-4 py-2.5 text-sm items-center"
                                >
                                    <div className="col-span-2 min-w-0">
                                        <p className="font-medium truncate">{case_.name}</p>
                                        <p className="text-xs text-muted-foreground truncate">
                                            {case_.case_type}
                                            {case_.client_name ? ` · ${case_.client_name}` : ""}
                                        </p>
                                    </div>
                                    <span className="text-right text-muted-foreground">
                                        {formatTokens(costs.tokens_in)}
                                    </span>
                                    <span className="text-right text-muted-foreground">
                                        {formatTokens(costs.tokens_out)}
                                    </span>
                                    <span className="text-right font-medium">
                                        {fmtTokenCost(costs.total_cost)}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            ) : null}

            {/* Top 5 Most Expensive Cases */}
            {top5.length > 0 && (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Top 5 Most Expensive Cases</CardTitle>
                        <CardDescription>
                            Cases with the highest cumulative LLM spend
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        {top5.map(({ case_, costs }, idx) => {
                            const maxCost = top5[0]?.costs.total_cost || 1;
                            const pct = (costs.total_cost / maxCost) * 100;
                            return (
                                <div key={case_.id} className="space-y-1.5">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2 min-w-0">
                                            <Badge
                                                variant="outline"
                                                className="text-[10px] shrink-0"
                                            >
                                                #{idx + 1}
                                            </Badge>
                                            <span className="text-sm font-medium truncate">
                                                {case_.name}
                                            </span>
                                        </div>
                                        <span className="text-sm font-mono font-medium shrink-0 ml-3">
                                            {fmtTokenCost(costs.total_cost)}
                                        </span>
                                    </div>
                                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                                        <div
                                            className="h-full rounded-full bg-primary/60 transition-all"
                                            style={{ width: `${pct}%` }}
                                        />
                                    </div>
                                </div>
                            );
                        })}
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
