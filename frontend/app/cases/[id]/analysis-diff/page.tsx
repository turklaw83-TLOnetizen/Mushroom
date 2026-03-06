// ---- Analysis Version Comparison ------------------------------------------
// Compare two preparations side-by-side: strategy, devil's advocate, findings.
"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type { Preparation } from "@/types/api";

// ---- Types ---------------------------------------------------------------

interface StrategyResponse {
    strategy_notes?: string;
    devils_advocate_notes?: string;
    case_summary?: string;
    key_findings?: string;
    investigation_plan?: unknown[];
    consistency_check?: string;
    [key: string]: unknown;
}

type DiffStatus = "new" | "removed" | "modified" | "unchanged";

interface SectionComparison {
    key: string;
    label: string;
    icon: string;
    contentA: string | null;
    contentB: string | null;
    status: DiffStatus;
}

// ---- Diff Helpers --------------------------------------------------------

function getDiffStatus(a: string | null, b: string | null): DiffStatus {
    const hasA = a !== null && a.trim().length > 0;
    const hasB = b !== null && b.trim().length > 0;

    if (!hasA && !hasB) return "unchanged";
    if (!hasA && hasB) return "new";
    if (hasA && !hasB) return "removed";
    if (a!.trim() === b!.trim()) return "unchanged";
    return "modified";
}

function statusBadge(status: DiffStatus) {
    switch (status) {
        case "new":
            return (
                <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30 text-xs">
                    New
                </Badge>
            );
        case "removed":
            return (
                <Badge className="bg-red-500/15 text-red-400 border-red-500/30 text-xs">
                    Removed
                </Badge>
            );
        case "modified":
            return (
                <Badge className="bg-amber-500/15 text-amber-400 border-amber-500/30 text-xs">
                    Modified
                </Badge>
            );
        case "unchanged":
            return (
                <Badge className="bg-zinc-500/15 text-zinc-400 border-zinc-500/30 text-xs">
                    Unchanged
                </Badge>
            );
    }
}

function extractText(data: unknown): string | null {
    if (typeof data === "string" && data.trim().length > 0) return data;
    if (Array.isArray(data) && data.length > 0) return JSON.stringify(data, null, 2);
    if (data && typeof data === "object" && Object.keys(data).length > 0) {
        return JSON.stringify(data, null, 2);
    }
    return null;
}

function truncatePreview(text: string | null, maxLen: number = 300): string {
    if (!text) return "";
    if (text.length <= maxLen) return text;
    return text.slice(0, maxLen) + "...";
}

// ---- Section Definitions -------------------------------------------------

const ANALYSIS_SECTIONS = [
    { key: "strategy_notes", label: "Strategy Notes", icon: "target" },
    { key: "devils_advocate_notes", label: "Devil's Advocate", icon: "zap" },
    { key: "case_summary", label: "Case Summary", icon: "file-text" },
    { key: "key_findings", label: "Key Findings", icon: "search" },
    { key: "consistency_check", label: "Consistency Check", icon: "check-circle" },
    { key: "investigation_plan", label: "Investigation Plan", icon: "clipboard" },
] as const;

// ---- Content Panel -------------------------------------------------------

function ContentPanel({
    label,
    content,
    isEmpty,
}: {
    label: string;
    content: string | null;
    isEmpty: boolean;
}) {
    const [expanded, setExpanded] = useState(false);

    if (isEmpty || !content) {
        return (
            <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-muted-foreground mb-2">{label}</p>
                <div className="border rounded-lg border-dashed p-4 text-center">
                    <p className="text-xs text-muted-foreground italic">
                        No data in this preparation
                    </p>
                </div>
            </div>
        );
    }

    const isLong = content.length > 500;
    const displayText = expanded ? content : truncatePreview(content, 500);

    return (
        <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-muted-foreground mb-2">{label}</p>
            <div className="border rounded-lg p-3 bg-muted/20 overflow-auto max-h-[400px]">
                <pre className="text-xs whitespace-pre-wrap break-words font-sans leading-relaxed">
                    {displayText}
                </pre>
                {isLong && (
                    <Button
                        variant="ghost"
                        size="sm"
                        className="mt-2 text-xs h-6 px-2"
                        onClick={() => setExpanded(!expanded)}
                    >
                        {expanded ? "Show less" : "Show more"}
                    </Button>
                )}
            </div>
        </div>
    );
}

// ---- Comparison Card -----------------------------------------------------

function ComparisonCard({ section }: { section: SectionComparison }) {
    const borderColor =
        section.status === "new"
            ? "border-l-emerald-500"
            : section.status === "removed"
                ? "border-l-red-500"
                : section.status === "modified"
                    ? "border-l-amber-500"
                    : "border-l-zinc-500/30";

    return (
        <Card className={cn("border-l-4", borderColor)}>
            <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center justify-between">
                    <span className="flex items-center gap-2">
                        {section.label}
                    </span>
                    {statusBadge(section.status)}
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <ContentPanel
                        label="Preparation A"
                        content={section.contentA}
                        isEmpty={!section.contentA}
                    />
                    <ContentPanel
                        label="Preparation B"
                        content={section.contentB}
                        isEmpty={!section.contentB}
                    />
                </div>
            </CardContent>
        </Card>
    );
}

// ---- Summary Stats -------------------------------------------------------

function DiffSummary({ sections }: { sections: SectionComparison[] }) {
    const counts = useMemo(() => {
        const result = { new: 0, removed: 0, modified: 0, unchanged: 0 };
        sections.forEach((s) => {
            result[s.status]++;
        });
        return result;
    }, [sections]);

    return (
        <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-1.5 text-sm">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                <span className="text-muted-foreground">New:</span>
                <span className="font-semibold">{counts.new}</span>
            </div>
            <div className="flex items-center gap-1.5 text-sm">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
                <span className="text-muted-foreground">Removed:</span>
                <span className="font-semibold">{counts.removed}</span>
            </div>
            <div className="flex items-center gap-1.5 text-sm">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                <span className="text-muted-foreground">Modified:</span>
                <span className="font-semibold">{counts.modified}</span>
            </div>
            <div className="flex items-center gap-1.5 text-sm">
                <span className="w-2.5 h-2.5 rounded-full bg-zinc-500" />
                <span className="text-muted-foreground">Unchanged:</span>
                <span className="font-semibold">{counts.unchanged}</span>
            </div>
        </div>
    );
}

// ---- Main Page -----------------------------------------------------------

export default function AnalysisDiffPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();

    const [selectedPrepA, setSelectedPrepA] = useState<string | null>(null);
    const [selectedPrepB, setSelectedPrepB] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState("all");

    // Fetch preparations list
    const { data: preparations, isLoading: prepsLoading } = useQuery({
        queryKey: ["cases", caseId, "preparations"],
        queryFn: () =>
            api.get<Preparation[]>(`/cases/${caseId}/preparations`, { getToken }),
    });

    // Fetch strategy data for Prep A
    const { data: dataA, isLoading: dataALoading } = useQuery({
        queryKey: ["strategy", caseId, selectedPrepA],
        queryFn: () =>
            api.get<StrategyResponse>(
                `/cases/${caseId}/preparations/${selectedPrepA}/strategy`,
                { getToken },
            ),
        enabled: !!selectedPrepA,
    });

    // Fetch strategy data for Prep B
    const { data: dataB, isLoading: dataBLoading } = useQuery({
        queryKey: ["strategy", caseId, selectedPrepB],
        queryFn: () =>
            api.get<StrategyResponse>(
                `/cases/${caseId}/preparations/${selectedPrepB}/strategy`,
                { getToken },
            ),
        enabled: !!selectedPrepB,
    });

    // Build section comparisons
    const sections = useMemo((): SectionComparison[] => {
        if (!selectedPrepA || !selectedPrepB) return [];

        return ANALYSIS_SECTIONS.map((sec) => {
            const rawA = dataA ? dataA[sec.key] : undefined;
            const rawB = dataB ? dataB[sec.key] : undefined;
            const contentA = extractText(rawA);
            const contentB = extractText(rawB);
            const status = getDiffStatus(contentA, contentB);

            return {
                key: sec.key,
                label: sec.label,
                icon: sec.icon,
                contentA,
                contentB,
                status,
            };
        });
    }, [selectedPrepA, selectedPrepB, dataA, dataB]);

    // Filtered sections by tab
    const filteredSections = useMemo(() => {
        if (activeTab === "all") return sections;
        return sections.filter((s) => s.status === activeTab);
    }, [sections, activeTab]);

    const prepList = preparations || [];
    const isLoading = dataALoading || dataBLoading;
    const bothSelected = selectedPrepA && selectedPrepB;
    const prepAName = prepList.find((p) => p.id === selectedPrepA)?.name ?? selectedPrepA;
    const prepBName = prepList.find((p) => p.id === selectedPrepB)?.name ?? selectedPrepB;

    // ---- Loading ----
    if (prepsLoading) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-8 w-72" />
                <Skeleton className="h-40 rounded-lg" />
                <Skeleton className="h-40 rounded-lg" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* ---- Header ---- */}
            <div>
                <h1 className="text-xl font-semibold tracking-tight">
                    Analysis Version Comparison
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Compare analysis results between two preparations to track changes
                </p>
            </div>

            {/* ---- Preparation Selectors ---- */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Select Preparations</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Prep A Selector */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-muted-foreground">
                                Preparation A (Base)
                            </label>
                            <Select
                                value={selectedPrepA ?? ""}
                                onValueChange={(v) => setSelectedPrepA(v)}
                            >
                                <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Select base preparation..." />
                                </SelectTrigger>
                                <SelectContent>
                                    {prepList.map((p) => (
                                        <SelectItem
                                            key={p.id}
                                            value={p.id}
                                            disabled={p.id === selectedPrepB}
                                        >
                                            <span className="flex items-center gap-2">
                                                {p.name}
                                                <span className="text-muted-foreground text-xs">
                                                    ({p.type})
                                                </span>
                                            </span>
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            {selectedPrepA && (
                                <div className="flex items-center gap-2">
                                    <Badge variant="outline" className="text-xs">
                                        {prepList.find((p) => p.id === selectedPrepA)?.type}
                                    </Badge>
                                    {prepList.find((p) => p.id === selectedPrepA)?.created_at && (
                                        <span className="text-xs text-muted-foreground">
                                            Created{" "}
                                            {new Date(
                                                prepList.find((p) => p.id === selectedPrepA)!.created_at!,
                                            ).toLocaleDateString()}
                                        </span>
                                    )}
                                </div>
                            )}
                        </div>

                        {/* Prep B Selector */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-muted-foreground">
                                Preparation B (Compare)
                            </label>
                            <Select
                                value={selectedPrepB ?? ""}
                                onValueChange={(v) => setSelectedPrepB(v)}
                            >
                                <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Select comparison preparation..." />
                                </SelectTrigger>
                                <SelectContent>
                                    {prepList.map((p) => (
                                        <SelectItem
                                            key={p.id}
                                            value={p.id}
                                            disabled={p.id === selectedPrepA}
                                        >
                                            <span className="flex items-center gap-2">
                                                {p.name}
                                                <span className="text-muted-foreground text-xs">
                                                    ({p.type})
                                                </span>
                                            </span>
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            {selectedPrepB && (
                                <div className="flex items-center gap-2">
                                    <Badge variant="outline" className="text-xs">
                                        {prepList.find((p) => p.id === selectedPrepB)?.type}
                                    </Badge>
                                    {prepList.find((p) => p.id === selectedPrepB)?.created_at && (
                                        <span className="text-xs text-muted-foreground">
                                            Created{" "}
                                            {new Date(
                                                prepList.find((p) => p.id === selectedPrepB)!.created_at!,
                                            ).toLocaleDateString()}
                                        </span>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    {selectedPrepA && selectedPrepB && selectedPrepA === selectedPrepB && (
                        <p className="text-xs text-amber-400 mt-3">
                            Select two different preparations to compare.
                        </p>
                    )}
                </CardContent>
            </Card>

            {/* ---- Loading Indicator ---- */}
            {bothSelected && isLoading && (
                <div className="space-y-3">
                    <Skeleton className="h-6 w-48" />
                    <Skeleton className="h-32 rounded-lg" />
                    <Skeleton className="h-32 rounded-lg" />
                    <Skeleton className="h-32 rounded-lg" />
                </div>
            )}

            {/* ---- Comparison Results ---- */}
            {bothSelected && !isLoading && sections.length > 0 && (
                <>
                    {/* Summary Bar */}
                    <Card>
                        <CardContent className="py-4">
                            <div className="flex items-center justify-between flex-wrap gap-4">
                                <div>
                                    <p className="text-sm font-medium">
                                        Comparing:{" "}
                                        <span className="text-muted-foreground">{prepAName}</span>
                                        {" vs "}
                                        <span className="text-muted-foreground">{prepBName}</span>
                                    </p>
                                </div>
                                <DiffSummary sections={sections} />
                            </div>
                        </CardContent>
                    </Card>

                    {/* Filter Tabs */}
                    <Tabs value={activeTab} onValueChange={setActiveTab}>
                        <TabsList variant="line">
                            <TabsTrigger value="all">
                                All
                                <Badge variant="secondary" className="ml-1.5 text-[10px] py-0 px-1.5">
                                    {sections.length}
                                </Badge>
                            </TabsTrigger>
                            <TabsTrigger value="modified">
                                Modified
                                <Badge className="ml-1.5 text-[10px] py-0 px-1.5 bg-amber-500/15 text-amber-400">
                                    {sections.filter((s) => s.status === "modified").length}
                                </Badge>
                            </TabsTrigger>
                            <TabsTrigger value="new">
                                New
                                <Badge className="ml-1.5 text-[10px] py-0 px-1.5 bg-emerald-500/15 text-emerald-400">
                                    {sections.filter((s) => s.status === "new").length}
                                </Badge>
                            </TabsTrigger>
                            <TabsTrigger value="removed">
                                Removed
                                <Badge className="ml-1.5 text-[10px] py-0 px-1.5 bg-red-500/15 text-red-400">
                                    {sections.filter((s) => s.status === "removed").length}
                                </Badge>
                            </TabsTrigger>
                            <TabsTrigger value="unchanged">
                                Unchanged
                                <Badge variant="secondary" className="ml-1.5 text-[10px] py-0 px-1.5">
                                    {sections.filter((s) => s.status === "unchanged").length}
                                </Badge>
                            </TabsTrigger>
                        </TabsList>

                        {/* Sections */}
                        <TabsContent value={activeTab} className="space-y-4 mt-4">
                            {filteredSections.length === 0 ? (
                                <Card className="border-dashed">
                                    <CardContent className="py-8 text-center">
                                        <p className="text-sm text-muted-foreground">
                                            No sections match the selected filter.
                                        </p>
                                    </CardContent>
                                </Card>
                            ) : (
                                filteredSections.map((section) => (
                                    <ComparisonCard key={section.key} section={section} />
                                ))
                            )}
                        </TabsContent>
                    </Tabs>
                </>
            )}

            {/* ---- Empty States ---- */}
            {prepList.length === 0 && (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center">
                        <p className="text-muted-foreground">
                            No preparations found for this case.
                        </p>
                        <p className="text-sm text-muted-foreground mt-1">
                            Create preparations and run analysis to enable comparison.
                        </p>
                    </CardContent>
                </Card>
            )}

            {prepList.length === 1 && (
                <Card className="border-dashed">
                    <CardContent className="py-8 text-center">
                        <p className="text-sm text-muted-foreground">
                            Only one preparation found. Create at least two preparations
                            to compare analysis results.
                        </p>
                    </CardContent>
                </Card>
            )}

            {bothSelected && !isLoading && !dataA && !dataB && (
                <Card className="border-dashed">
                    <CardContent className="py-8 text-center">
                        <p className="text-sm text-muted-foreground">
                            No analysis data found for either preparation.
                            Run analysis on at least one preparation to see results.
                        </p>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
