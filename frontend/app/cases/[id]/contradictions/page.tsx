// ---- Cross-Document Contradiction Matrix ---------------------------------
// Systematic comparison of all case documents to find contradictions,
// inconsistencies, and impeachment opportunities. Three views:
//   1. Dashboard  — saved matrix results + "Run Analysis" button
//   2. Running    — progress display during analysis
//   3. Results    — full matrix visualization with filters and tabs
"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { routes } from "@/lib/api-routes";
import { queryKeys } from "@/lib/query-keys";
import {
    formatDate,
    formatLabel,
    CONTRADICTION_SEVERITY_COLORS,
    CONTRADICTION_CATEGORY_COLORS,
    RELATIONSHIP_COLORS,
} from "@/lib/constants";
import { usePrep } from "@/hooks/use-prep";
import { useRole } from "@/hooks/use-role";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import type {
    ContradictionMatrix,
    ContradictionFinding,
    DocumentComparison,
} from "@/types/api";

// ---- Types / Constants ---------------------------------------------------

type ViewMode = "dashboard" | "running" | "results";
type ResultTab = "contradictions" | "by-document" | "by-entity";

const SEVERITY_ORDER: Record<string, number> = { critical: 0, significant: 1, minor: 2 };
const IMPEACHMENT_LABELS: Record<string, string> = {
    high: "High Impeachment Value",
    medium: "Medium Impeachment Value",
    low: "Low Impeachment Value",
};

// ---- Main Page -----------------------------------------------------------

export default function ContradictionMatrixPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { activePrepId, isLoading: prepLoading } = usePrep();
    const { getToken } = useAuth();
    const { canEdit } = useRole();
    const queryClient = useQueryClient();

    const [view, setView] = useState<ViewMode>("dashboard");
    const [resultTab, setResultTab] = useState<ResultTab>("contradictions");
    const [severityFilter, setSeverityFilter] = useState<string>("all");
    const [categoryFilter, setCategoryFilter] = useState<string>("all");
    const [docFilter, setDocFilter] = useState<string>("all");
    const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());

    // ---- Data Fetching --------------------------------------------------

    const matrixQuery = useQuery({
        queryKey: [...queryKeys.contradictions.matrix(caseId, activePrepId ?? "")],
        queryFn: () =>
            api.get<ContradictionMatrix>(
                routes.contradictions.matrix(caseId, activePrepId!),
                { getToken },
            ),
        enabled: !!activePrepId,
        retry: false,
    });

    // ---- Mutations ------------------------------------------------------

    const runAnalysis = useMutation<ContradictionMatrix, Error>({
        mutationFn: () =>
            api.post<ContradictionMatrix>(
                routes.contradictions.matrix(caseId, activePrepId!),
                {},
                { getToken },
            ),
        onMutate: () => {
            setView("running");
        },
        onSuccess: (data) => {
            toast.success("Contradiction matrix complete", {
                description: `Found ${data.total_contradictions} contradictions across ${data.pairs_compared} document pairs`,
            });
            queryClient.invalidateQueries({
                queryKey: [...queryKeys.contradictions.matrix(caseId, activePrepId!)],
            });
            setView("results");
        },
        onError: (err) => {
            toast.error("Contradiction analysis failed", {
                description: err.message,
            });
            setView("dashboard");
        },
    });

    const deleteMatrix = useMutation({
        mutationFn: () =>
            api.delete(
                routes.contradictions.matrix(caseId, activePrepId!),
                { getToken },
            ),
        onSuccess: () => {
            toast.success("Matrix deleted");
            queryClient.invalidateQueries({
                queryKey: [...queryKeys.contradictions.matrix(caseId, activePrepId!)],
            });
            setView("dashboard");
        },
    });

    // ---- Derived data ---------------------------------------------------

    const matrix = matrixQuery.data;

    const allContradictions = useMemo(() => {
        if (!matrix?.matrix) return [];
        const all: (ContradictionFinding & { doc_a: string; doc_b: string })[] = [];
        for (const pair of matrix.matrix) {
            for (const c of pair.contradictions ?? []) {
                all.push({ ...c, doc_a: pair.doc_a, doc_b: pair.doc_b });
            }
        }
        return all.sort((a, b) =>
            (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3)
        );
    }, [matrix]);

    const filteredContradictions = useMemo(() => {
        let items = allContradictions;
        if (severityFilter !== "all") {
            items = items.filter((c) => c.severity === severityFilter);
        }
        if (categoryFilter !== "all") {
            items = items.filter((c) => c.category === categoryFilter);
        }
        if (docFilter !== "all") {
            items = items.filter((c) => c.doc_a === docFilter || c.doc_b === docFilter);
        }
        return items;
    }, [allContradictions, severityFilter, categoryFilter, docFilter]);

    const uniqueDocuments = useMemo(() => {
        if (!matrix?.matrix) return [];
        const docs = new Set<string>();
        for (const pair of matrix.matrix) {
            docs.add(pair.doc_a);
            docs.add(pair.doc_b);
        }
        return Array.from(docs).sort();
    }, [matrix]);

    const uniqueCategories = useMemo(() => {
        const cats = new Set<string>();
        for (const c of allContradictions) {
            cats.add(c.category);
        }
        return Array.from(cats).sort();
    }, [allContradictions]);

    const toggleExpand = (key: string) => {
        setExpandedCards((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
        });
    };

    // ---- Guards ---------------------------------------------------------

    if (prepLoading || matrixQuery.isLoading) {
        return (
            <div className="space-y-6">
                <div className="flex items-center justify-between">
                    <Skeleton className="h-7 w-72" />
                    <div className="flex items-center gap-2">
                        <Skeleton className="h-3 w-32" />
                        <Skeleton className="h-8 w-16" />
                    </div>
                </div>
                <Skeleton className="h-20 w-full rounded-lg" />
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Card key={i}>
                            <CardContent className="p-4 text-center space-y-2">
                                <Skeleton className="h-8 w-10 mx-auto" />
                                <Skeleton className="h-3 w-24 mx-auto" />
                            </CardContent>
                        </Card>
                    ))}
                </div>
                <div className="flex gap-1">
                    {Array.from({ length: 3 }).map((_, i) => (
                        <Skeleton key={i} className="h-8 w-28 rounded-md" />
                    ))}
                </div>
                <div className="space-y-3">
                    {Array.from({ length: 3 }).map((_, i) => (
                        <Card key={i}>
                            <CardContent className="p-4 space-y-3">
                                <div className="flex items-center gap-2">
                                    <Skeleton className="h-5 w-16 rounded-full" />
                                    <Skeleton className="h-5 w-24 rounded-full" />
                                    <Skeleton className="h-3 w-40" />
                                </div>
                                <div className="grid md:grid-cols-2 gap-3">
                                    <Skeleton className="h-20 w-full rounded-md" />
                                    <Skeleton className="h-20 w-full rounded-md" />
                                </div>
                                <Skeleton className="h-4 w-full" />
                                <Skeleton className="h-4 w-3/4" />
                            </CardContent>
                        </Card>
                    ))}
                </div>
            </div>
        );
    }

    if (!activePrepId) {
        return (
            <div className="text-center py-12">
                <h2 className="text-lg font-semibold mb-2">No Preparation Selected</h2>
                <p className="text-sm text-muted-foreground">
                    Select or create a preparation to run contradiction analysis.
                </p>
            </div>
        );
    }

    // Auto-switch to results if matrix already loaded
    if (view === "dashboard" && matrix && !matrixQuery.isError) {
        // Show results if we have data
    }

    // ---- Running View ---------------------------------------------------

    if (view === "running") {
        return (
            <div className="space-y-6">
                <h2 className="text-xl font-bold tracking-tight">
                    Cross-Document Contradiction Matrix
                </h2>
                <Card>
                    <CardContent className="py-12 text-center space-y-4">
                        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-400" />
                        <h3 className="text-lg font-semibold">
                            Running Contradiction Analysis
                        </h3>
                        <p className="text-sm text-muted-foreground max-w-md mx-auto">
                            Comparing documents pairwise using AI. This may take several
                            minutes depending on the number of documents.
                        </p>
                        <div className="flex justify-center gap-6 text-xs text-muted-foreground pt-4">
                            <div className="flex items-center gap-2">
                                <span className="h-2 w-2 rounded-full bg-green-400 animate-pulse" />
                                Inventory
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="h-2 w-2 rounded-full bg-blue-400 animate-pulse" />
                                Pair Selection
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
                                Comparisons
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="h-2 w-2 rounded-full bg-purple-400 animate-pulse" />
                                Synthesis
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        );
    }

    // ---- Dashboard View (no results yet) --------------------------------

    if (matrixQuery.isError || !matrix) {
        return (
            <div className="space-y-6">
                <h2 className="text-xl font-bold tracking-tight">
                    Cross-Document Contradiction Matrix
                </h2>
                <EmptyState
                    icon="&#x1f50d;"
                    title="No Contradiction Matrix Found"
                    description="Run a contradiction analysis to systematically compare all case documents and identify inconsistencies, timeline discrepancies, and impeachment opportunities."
                    action={canEdit ? {
                        label: runAnalysis.isPending ? "Starting..." : "Run Contradiction Analysis",
                        onClick: () => runAnalysis.mutate(),
                    } : undefined}
                />
            </div>
        );
    }

    // ---- Results View ---------------------------------------------------

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold tracking-tight">
                    Cross-Document Contradiction Matrix
                </h2>
                <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                        Generated {formatDate(matrix.generated_at)}
                    </span>
                    {canEdit && (
                        <>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => runAnalysis.mutate()}
                                disabled={runAnalysis.isPending}
                            >
                                Re-run
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                    if (!window.confirm("Delete the entire contradiction matrix? This action cannot be undone.")) return;
                                    deleteMatrix.mutate();
                                }}
                                disabled={deleteMatrix.isPending}
                                className="text-destructive hover:text-destructive"
                            >
                                Delete
                            </Button>
                        </>
                    )}
                </div>
            </div>

            {/* Executive Summary */}
            {matrix.executive_summary && (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Executive Summary</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-sm leading-relaxed text-muted-foreground">
                            {matrix.executive_summary}
                        </p>
                    </CardContent>
                </Card>
            )}

            {/* Score Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <ScoreCard
                    label="Total Contradictions"
                    value={matrix.total_contradictions}
                    color="text-red-400"
                />
                <ScoreCard
                    label="Critical Findings"
                    value={matrix.critical_findings}
                    color="text-orange-400"
                />
                <ScoreCard
                    label="Documents Analyzed"
                    value={matrix.document_count}
                    color="text-blue-400"
                />
                <ScoreCard
                    label="Pairs Compared"
                    value={matrix.pairs_compared}
                    color="text-purple-400"
                />
            </div>

            {/* Tab Selector */}
            <div className="flex gap-1 p-1 bg-muted rounded-lg w-fit">
                {(
                    [
                        ["contradictions", "Contradictions"],
                        ["by-document", "By Document"],
                        ["by-entity", "By Entity"],
                    ] as [ResultTab, string][]
                ).map(([key, label]) => (
                    <button
                        key={key}
                        onClick={() => setResultTab(key)}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                            resultTab === key
                                ? "bg-background text-foreground shadow-sm"
                                : "text-muted-foreground hover:text-foreground"
                        }`}
                    >
                        {label}
                    </button>
                ))}
            </div>

            {/* Contradictions Tab */}
            {resultTab === "contradictions" && (
                <div className="space-y-4">
                    {/* Filter Bar */}
                    <div className="flex flex-wrap gap-3 items-center">
                        <FilterSelect
                            label="Severity"
                            value={severityFilter}
                            onChange={setSeverityFilter}
                            options={[
                                { value: "all", label: "All Severities" },
                                { value: "critical", label: "Critical" },
                                { value: "significant", label: "Significant" },
                                { value: "minor", label: "Minor" },
                            ]}
                        />
                        <FilterSelect
                            label="Category"
                            value={categoryFilter}
                            onChange={setCategoryFilter}
                            options={[
                                { value: "all", label: "All Categories" },
                                ...uniqueCategories.map((c) => ({
                                    value: c,
                                    label: formatLabel(c),
                                })),
                            ]}
                        />
                        <FilterSelect
                            label="Document"
                            value={docFilter}
                            onChange={setDocFilter}
                            options={[
                                { value: "all", label: "All Documents" },
                                ...uniqueDocuments.map((d) => ({
                                    value: d,
                                    label: d.length > 30 ? d.slice(0, 30) + "..." : d,
                                })),
                            ]}
                        />
                        <span className="text-xs text-muted-foreground ml-auto">
                            {filteredContradictions.length} result{filteredContradictions.length !== 1 ? "s" : ""}
                        </span>
                    </div>

                    {/* Contradiction Cards */}
                    {filteredContradictions.length === 0 ? (
                        <EmptyState
                            icon="\uD83D\uDD0D"
                            title="No contradictions match the current filters"
                            description="Try adjusting your severity, category, or document filters."
                        />
                    ) : (
                        filteredContradictions.map((c, idx) => {
                            const key = `c-${idx}`;
                            const isExpanded = expandedCards.has(key);
                            return (
                                <Card key={key} className="overflow-hidden">
                                    <CardContent className="p-4 space-y-3">
                                        {/* Header row */}
                                        <div className="flex items-start justify-between gap-3">
                                            <div className="flex items-center gap-2 flex-wrap">
                                                <Badge
                                                    variant="outline"
                                                    className={
                                                        CONTRADICTION_SEVERITY_COLORS[c.severity] ??
                                                        "bg-zinc-500/15 text-zinc-400 border-zinc-500/30"
                                                    }
                                                >
                                                    {c.severity}
                                                </Badge>
                                                <Badge
                                                    variant="outline"
                                                    className={
                                                        CONTRADICTION_CATEGORY_COLORS[c.category] ??
                                                        "bg-zinc-500/15 text-zinc-400 border-zinc-500/30"
                                                    }
                                                >
                                                    {formatLabel(c.category)}
                                                </Badge>
                                                <span className="text-xs text-muted-foreground">
                                                    {c.doc_a} vs {c.doc_b}
                                                </span>
                                            </div>
                                            <Badge
                                                variant="secondary"
                                                className="text-[10px] shrink-0"
                                            >
                                                {IMPEACHMENT_LABELS[c.impeachment_value] ?? c.impeachment_value}
                                            </Badge>
                                        </div>

                                        {/* Content comparison */}
                                        <div className="grid md:grid-cols-2 gap-3">
                                            <div className="rounded-md bg-red-500/5 border border-red-500/10 p-3">
                                                <p className="text-[10px] font-medium text-red-400 mb-1 uppercase tracking-wider">
                                                    {c.doc_a}
                                                </p>
                                                <p className="text-sm">{c.doc_a_says}</p>
                                            </div>
                                            <div className="rounded-md bg-blue-500/5 border border-blue-500/10 p-3">
                                                <p className="text-[10px] font-medium text-blue-400 mb-1 uppercase tracking-wider">
                                                    {c.doc_b}
                                                </p>
                                                <p className="text-sm">{c.doc_b_says}</p>
                                            </div>
                                        </div>

                                        {/* Explanation */}
                                        <p className="text-sm text-muted-foreground">
                                            {c.explanation}
                                        </p>

                                        {/* Collapsible cross-exam question */}
                                        {c.suggested_question && (
                                            <div>
                                                <button
                                                    onClick={() => toggleExpand(key)}
                                                    className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                                                >
                                                    {isExpanded
                                                        ? "Hide suggested question"
                                                        : "Show suggested cross-exam question"}
                                                </button>
                                                {isExpanded && (
                                                    <div className="mt-2 rounded-md bg-indigo-500/5 border border-indigo-500/10 p-3">
                                                        <p className="text-sm italic">
                                                            &ldquo;{c.suggested_question}&rdquo;
                                                        </p>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            );
                        })
                    )}

                    {/* Impeachment Priorities */}
                    {matrix.impeachment_priorities && matrix.impeachment_priorities.length > 0 && (
                        <Card>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm">
                                    Impeachment Priorities
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-3">
                                    {matrix.impeachment_priorities.map((p, idx) => (
                                        <div
                                            key={idx}
                                            className="flex items-start gap-3 text-sm"
                                        >
                                            <span className="shrink-0 h-6 w-6 rounded-full bg-orange-500/15 text-orange-400 text-xs font-bold flex items-center justify-center">
                                                {p.rank}
                                            </span>
                                            <div>
                                                <span className="font-medium">
                                                    {p.target_document}
                                                </span>
                                                {p.against_document && (
                                                    <span className="text-muted-foreground">
                                                        {" "}vs {p.against_document}
                                                    </span>
                                                )}
                                                <p className="text-muted-foreground mt-0.5">
                                                    {p.why}
                                                </p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {/* Investigation Leads */}
                    {matrix.investigation_leads && matrix.investigation_leads.length > 0 && (
                        <Card>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm">
                                    Investigation Leads
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-3">
                                    {matrix.investigation_leads.map((lead, idx) => (
                                        <div
                                            key={idx}
                                            className="flex items-start gap-3 text-sm"
                                        >
                                            <Badge
                                                variant="outline"
                                                className={
                                                    lead.priority === "high"
                                                        ? "bg-red-500/15 text-red-400 border-red-500/30"
                                                        : lead.priority === "medium"
                                                          ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
                                                          : "bg-green-500/15 text-green-400 border-green-500/30"
                                                }
                                            >
                                                {lead.priority}
                                            </Badge>
                                            <div>
                                                <p className="font-medium">{lead.lead}</p>
                                                <p className="text-muted-foreground text-xs mt-0.5">
                                                    Based on: {lead.based_on}
                                                </p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}

            {/* By-Document Tab */}
            {resultTab === "by-document" && matrix.by_document && (
                <div className="space-y-3">
                    {Object.entries(matrix.by_document)
                        .sort(([, a], [, b]) => b.contradictions_found - a.contradictions_found)
                        .map(([docName, stats]) => (
                            <Card key={docName}>
                                <CardContent className="p-4">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-sm font-medium">{docName}</p>
                                            {stats.most_contradicted_by && (
                                                <p className="text-xs text-muted-foreground mt-0.5">
                                                    Most contradicted by: {stats.most_contradicted_by}
                                                </p>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Badge
                                                variant="outline"
                                                className={
                                                    stats.contradictions_found > 5
                                                        ? "bg-red-500/15 text-red-400 border-red-500/30"
                                                        : stats.contradictions_found > 0
                                                          ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
                                                          : "bg-green-500/15 text-green-400 border-green-500/30"
                                                }
                                            >
                                                {stats.contradictions_found} contradiction{stats.contradictions_found !== 1 ? "s" : ""}
                                            </Badge>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    {Object.keys(matrix.by_document).length === 0 && (
                        <EmptyState
                            icon="\uD83D\uDCC2"
                            title="No per-document data available"
                            description="Run the contradiction analysis to generate per-document breakdowns."
                        />
                    )}
                </div>
            )}

            {/* By-Entity Tab */}
            {resultTab === "by-entity" && matrix.by_entity && (
                <div className="space-y-3">
                    {Object.entries(matrix.by_entity)
                        .sort(([, a], [, b]) => b.length - a.length)
                        .map(([entity, items]) => (
                            <Card key={entity}>
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm flex items-center justify-between">
                                        <span>{entity}</span>
                                        <Badge variant="secondary" className="text-[10px]">
                                            {items.length} disagreement{items.length !== 1 ? "s" : ""}
                                        </Badge>
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-2">
                                        {items.map((item, idx) => (
                                            <div
                                                key={idx}
                                                className="text-sm rounded-md bg-muted/50 p-2"
                                            >
                                                <span className="text-muted-foreground">
                                                    {item.doc_a} vs {item.doc_b}:
                                                </span>{" "}
                                                {item.what_they_disagree_on}
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    {Object.keys(matrix.by_entity).length === 0 && (
                        <EmptyState
                            icon="\uD83C\uDFF7\uFE0F"
                            title="No entity-level data available"
                            description="Run the contradiction analysis to generate entity-level breakdowns."
                        />
                    )}
                </div>
            )}
        </div>
    );
}

// ---- Helper Components ---------------------------------------------------

function ScoreCard({
    label,
    value,
    color,
}: {
    label: string;
    value: number;
    color: string;
}) {
    return (
        <Card>
            <CardContent className="p-4 text-center">
                <p className={`text-2xl font-bold ${color}`}>{value}</p>
                <p className="text-xs text-muted-foreground mt-1">{label}</p>
            </CardContent>
        </Card>
    );
}

function FilterSelect({
    label,
    value,
    onChange,
    options,
}: {
    label: string;
    value: string;
    onChange: (v: string) => void;
    options: { value: string; label: string }[];
}) {
    return (
        <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="h-8 rounded-md border border-border bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
            aria-label={label}
        >
            {options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                    {opt.label}
                </option>
            ))}
        </select>
    );
}
