// ---- Legal Research Command Center ----------------------------------------
// Guided 4-step research workflow:
//   1. Research Focus   — define question + platform
//   2. Generated Queries — copy-paste-ready Boolean search queries
//   3. Paste Results     — paste raw Lexis+/Westlaw text
//   4. Analysis Report   — extracted cases, favorability, strategy
// Additional tabs: Cheat Sheet, Civil Tools
"use client";

import { useState, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { routes } from "@/lib/api-routes";
import { queryKeys } from "@/lib/query-keys";
import { usePrep } from "@/hooks/use-prep";
import { usePrepState } from "@/hooks/use-prep-state";
import { MarkdownContent } from "@/components/analysis/markdown-content";
import { ResultSection } from "@/components/analysis/result-section";
import { GenerateButton } from "@/components/analysis/generate-button";
import { ModuleNotes } from "@/components/shared/module-notes";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { LexisQuery, LexisAnalysisResult, LexisAnalysisCase } from "@/types/api";

// ---- Constants ----------------------------------------------------------

const PLATFORMS = [
    { value: "lexis", label: "Lexis+" },
    { value: "westlaw", label: "Westlaw" },
    { value: "scholar", label: "Google Scholar" },
    { value: "general", label: "General Research" },
] as const;

const FAVORABILITY_COLORS: Record<string, string> = {
    FAVORABLE: "bg-green-500/15 text-green-400 border-green-500/30",
    UNFAVORABLE: "bg-red-500/15 text-red-400 border-red-500/30",
    NEUTRAL: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
};

const STRENGTH_STARS: Record<string, number> = {
    HIGH: 5,
    MEDIUM: 3,
    LOW: 1,
};

type ResearchStep = 1 | 2 | 3 | 4;

// ---- Helpers ------------------------------------------------------------

function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text).then(
        () => toast.success("Copied to clipboard"),
        () => toast.error("Failed to copy"),
    );
}

function StrengthIndicator({ strength }: { strength: string }) {
    const filled = STRENGTH_STARS[strength] ?? 3;
    return (
        <span className="inline-flex gap-0.5" title={`Strength: ${strength}`}>
            {[1, 2, 3, 4, 5].map((i) => (
                <span
                    key={i}
                    className={`text-xs ${i <= filled ? "text-amber-400" : "text-zinc-600"}`}
                >
                    {i <= filled ? "\u2605" : "\u2606"}
                </span>
            ))}
        </span>
    );
}

function StepIndicator({ current, total }: { current: number; total: number }) {
    return (
        <div className="flex items-center gap-2 mb-6">
            {Array.from({ length: total }, (_, i) => {
                const step = i + 1;
                const isActive = step === current;
                const isCompleted = step < current;
                return (
                    <div key={step} className="flex items-center gap-2">
                        <div
                            className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                                isActive
                                    ? "bg-indigo-500 text-white"
                                    : isCompleted
                                    ? "bg-indigo-500/20 text-indigo-400 border border-indigo-500/40"
                                    : "bg-zinc-800 text-zinc-500 border border-zinc-700"
                            }`}
                        >
                            {isCompleted ? "\u2713" : step}
                        </div>
                        {step < total && (
                            <div
                                className={`w-8 h-0.5 ${
                                    isCompleted ? "bg-indigo-500/40" : "bg-zinc-700"
                                }`}
                            />
                        )}
                    </div>
                );
            })}
        </div>
    );
}

// ---- Platform Tips ------------------------------------------------------

const PLATFORM_TIPS: Record<string, string[]> = {
    lexis: [
        'Use /s for "within same sentence" and /p for "within same paragraph"',
        'w/n means "within N words" (e.g., w/5 = within 5 words)',
        "! is the root expander: negligen! matches negligent, negligence, negligently",
        "* is the universal character: wom*n matches woman, women",
        "Use AND, OR, NOT for Boolean logic",
    ],
    westlaw: [
        'Use /s for "within same sentence" and /p for "within same paragraph"',
        '+s means "within same sentence" and +p means "within same paragraph"',
        "! is the root expander: object! matches object, objection, objecting",
        "% is the BUT NOT operator (equivalent to AND NOT)",
        'Use quotation marks for exact phrases: "summary judgment"',
    ],
    scholar: [
        'Use quotation marks for exact phrases: "due process"',
        "Use - to exclude terms: self-defense -gun",
        "Use OR to search for alternatives: negligence OR carelessness",
        'Use site: to limit to specific domains: site:law.cornell.edu',
        'Use intitle: to find terms in the title: intitle:"motion to suppress"',
    ],
    general: [
        "Combine terms with quotes for exact matching",
        "Use Boolean operators: AND, OR, NOT",
        "Include jurisdiction and year to narrow results",
        "Search for specific statutes by number",
        "Include case names when searching for related precedent",
    ],
};

// ---- Main Page ----------------------------------------------------------

export default function ResearchPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const { activePrepId, isLoading: prepLoading } = usePrep();
    const { sections, isLoading: stateLoading } = usePrepState(caseId, activePrepId);

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">
                    Create a preparation first to view research.
                </p>
            </div>
        );
    }

    return (
        <Tabs defaultValue="command-center" className="space-y-4">
            <TabsList variant="line">
                <TabsTrigger value="command-center">
                    Research Command Center
                </TabsTrigger>
                <TabsTrigger value="legal-research">
                    AI Research{" "}
                    {sections.legalResearch && (
                        <span className="ml-1 text-emerald-400" aria-hidden="true">
                            {"\u25CF"}
                        </span>
                    )}
                </TabsTrigger>
                <TabsTrigger value="cheat-sheet">
                    Cheat Sheet{" "}
                    {sections.cheatSheet && (
                        <span className="ml-1 text-emerald-400" aria-hidden="true">
                            {"\u25CF"}
                        </span>
                    )}
                </TabsTrigger>
                <TabsTrigger value="civil-tools">
                    Civil Tools{" "}
                    <span className="ml-1 text-xs text-muted-foreground">
                        (Civil cases only)
                    </span>
                </TabsTrigger>
            </TabsList>

            {/* ---- Research Command Center ---- */}
            <TabsContent value="command-center">
                {activePrepId ? (
                    <ResearchCommandCenter
                        caseId={caseId}
                        prepId={activePrepId}
                    />
                ) : (
                    <Skeleton className="h-64 w-full" />
                )}
            </TabsContent>

            {/* ---- AI Legal Research Tab ---- */}
            <TabsContent value="legal-research">
                <ResultSection
                    title="Legal Research"
                    icon={"\uD83D\uDCDA"}
                    isEmpty={!sections.legalResearch}
                    isLoading={stateLoading}
                    emptyMessage="Run analysis to generate legal research with case law citations and statutory analysis."
                >
                    {sections.legalResearch && (
                        <MarkdownContent
                            content={
                                typeof sections.legalResearch === "string"
                                    ? sections.legalResearch
                                    : JSON.stringify(sections.legalResearch, null, 2)
                            }
                        />
                    )}
                </ResultSection>
                <ModuleNotes
                    caseId={caseId}
                    prepId={activePrepId}
                    moduleKey="legal_research"
                />
            </TabsContent>

            {/* ---- Cheat Sheet Tab ---- */}
            <TabsContent value="cheat-sheet">
                {sections.cheatSheet ? (
                    <ResultSection
                        title="Cheat Sheet"
                        icon={"\uD83D\uDCCB"}
                        isEmpty={false}
                        isLoading={stateLoading}
                    >
                        <MarkdownContent
                            content={
                                typeof sections.cheatSheet === "string"
                                    ? sections.cheatSheet
                                    : JSON.stringify(sections.cheatSheet, null, 2)
                            }
                        />
                    </ResultSection>
                ) : (
                    <GenerateButton
                        caseId={caseId}
                        prepId={activePrepId}
                        endpoint="cheat-sheet"
                        label="Cheat Sheet"
                        icon={"\uD83D\uDCCB"}
                        resultKey="cheat_sheet"
                        emptyMessage="Generate a quick-reference cheat sheet with key facts, citations, and courtroom reminders."
                    />
                )}
                <ModuleNotes
                    caseId={caseId}
                    prepId={activePrepId}
                    moduleKey="cheat_sheet"
                />
            </TabsContent>

            {/* ---- Civil Tools Tab ---- */}
            <TabsContent value="civil-tools">
                <CivilToolsPanel caseId={caseId} prepId={activePrepId} />
            </TabsContent>
        </Tabs>
    );
}

// ---- Research Command Center (guided workflow) --------------------------

function ResearchCommandCenter({
    caseId,
    prepId,
}: {
    caseId: string;
    prepId: string;
}) {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    // Step tracking
    const [currentStep, setCurrentStep] = useState<ResearchStep>(1);

    // Step 1 state
    const [researchFocus, setResearchFocus] = useState("");
    const [platform, setPlatform] = useState<string>("lexis");
    const [showTips, setShowTips] = useState(false);

    // Step 2 state — generated queries
    const [generatedQueries, setGeneratedQueries] = useState<LexisQuery[]>([]);

    // Step 3 state — pasted text
    const [pastedText, setPastedText] = useState("");
    const [queryContext, setQueryContext] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Step 4 state — analysis results
    const [analysisResult, setAnalysisResult] = useState<LexisAnalysisResult | null>(null);

    // Research history (accumulates during session)
    const [researchHistory, setResearchHistory] = useState<
        Array<{
            id: string;
            focus: string;
            platform: string;
            queriesCount: number;
            casesFound: number;
            timestamp: string;
        }>
    >([]);

    // ---- Mutations ----------------------------------------------------------

    const generateQueriesMutation = useMutation({
        mutationFn: () =>
            api.post<{
                status: string;
                result: { lexis_queries: LexisQuery[] };
            }>(
                routes.research.lexisQueries(caseId, prepId),
                { research_focus: researchFocus },
                { getToken },
            ),
        onSuccess: (data) => {
            const queries = data.result.lexis_queries ?? [];
            setGeneratedQueries(queries);
            // Build context string for analyze step
            setQueryContext(
                queries.map((q) => q.search_string).join("\n"),
            );
            setCurrentStep(2);
            toast.success(`Generated ${queries.length} search queries`);
            queryClient.invalidateQueries({
                queryKey: [...queryKeys.cases.prepState(caseId, prepId)],
            });
        },
        onError: (err: Error) => {
            toast.error("Query generation failed", {
                description: err.message,
            });
        },
    });

    const analyzeResultsMutation = useMutation({
        mutationFn: () =>
            api.post<{
                status: string;
                result: { lexis_analysis: LexisAnalysisResult };
            }>(
                routes.research.lexisAnalysis(caseId, prepId),
                {
                    pasted_text: pastedText,
                    query_context: queryContext,
                },
                { getToken },
            ),
        onSuccess: (data) => {
            const analysis = data.result.lexis_analysis;
            setAnalysisResult(analysis);
            setCurrentStep(4);

            // Add to research history
            setResearchHistory((prev) => [
                ...prev,
                {
                    id: `${Date.now()}`,
                    focus: researchFocus,
                    platform,
                    queriesCount: generatedQueries.length,
                    casesFound: analysis.cases?.length ?? 0,
                    timestamp: new Date().toLocaleString(),
                },
            ]);

            toast.success(
                `Analyzed ${analysis.cases?.length ?? 0} cases from research results`,
            );
            queryClient.invalidateQueries({
                queryKey: [...queryKeys.cases.prepState(caseId, prepId)],
            });
        },
        onError: (err: Error) => {
            toast.error("Analysis failed", { description: err.message });
        },
    });

    const cheatSheetMutation = useMutation({
        mutationFn: () =>
            api.post<{
                status: string;
                result: { cheat_sheet: string };
            }>(routes.research.cheatSheet(caseId, prepId), {}, { getToken }),
        onSuccess: () => {
            toast.success("Cheat sheet generated");
            queryClient.invalidateQueries({
                queryKey: [...queryKeys.cases.prepState(caseId, prepId)],
            });
        },
        onError: (err: Error) => {
            toast.error("Cheat sheet generation failed", {
                description: err.message,
            });
        },
    });

    // ---- New cycle handler --------------------------------------------------
    const startNewCycle = useCallback(
        (prefillFocus?: string) => {
            if (prefillFocus) setResearchFocus(prefillFocus);
            else setResearchFocus("");
            setGeneratedQueries([]);
            setPastedText("");
            setQueryContext("");
            setAnalysisResult(null);
            setCurrentStep(1);
        },
        [],
    );

    // ---- Render steps -------------------------------------------------------

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div>
                    <h2 className="text-lg font-semibold">
                        Legal Research Command Center
                    </h2>
                    <p className="text-sm text-muted-foreground mt-1">
                        Generate targeted search queries, run them on your
                        preferred platform, paste results back for AI analysis.
                    </p>
                </div>
                {currentStep > 1 && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => startNewCycle()}
                    >
                        New Research Cycle
                    </Button>
                )}
            </div>

            <StepIndicator current={currentStep} total={4} />

            {/* ---- Step 1: Research Focus ---- */}
            {currentStep === 1 && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">
                            Step 1: Define Research Focus
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div>
                            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">
                                What legal question are you researching?
                            </label>
                            <textarea
                                value={researchFocus}
                                onChange={(e) =>
                                    setResearchFocus(e.target.value)
                                }
                                placeholder="e.g., Fourth Amendment suppression of evidence obtained through a warrantless vehicle search during a traffic stop..."
                                className="w-full min-h-[100px] rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-y"
                            />
                        </div>
                        <div>
                            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">
                                Research Platform
                            </label>
                            <div className="flex flex-wrap gap-2">
                                {PLATFORMS.map((p) => (
                                    <button
                                        key={p.value}
                                        onClick={() => setPlatform(p.value)}
                                        className={`px-3 py-1.5 rounded-md text-sm font-medium border transition-colors ${
                                            platform === p.value
                                                ? "bg-indigo-500/15 text-indigo-400 border-indigo-500/40"
                                                : "bg-transparent text-muted-foreground border-input hover:border-muted-foreground/50"
                                        }`}
                                    >
                                        {p.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                        <div className="flex items-center gap-3 pt-2">
                            <Button
                                onClick={() =>
                                    generateQueriesMutation.mutate()
                                }
                                disabled={
                                    generateQueriesMutation.isPending ||
                                    !researchFocus.trim()
                                }
                            >
                                {generateQueriesMutation.isPending ? (
                                    <span className="flex items-center gap-2">
                                        <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                        Generating Queries...
                                    </span>
                                ) : (
                                    "Generate Search Queries"
                                )}
                            </Button>
                            {generateQueriesMutation.isError && (
                                <p className="text-xs text-red-400">
                                    Generation failed. Please try again.
                                </p>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* ---- Step 2: Generated Queries ---- */}
            {currentStep === 2 && (
                <div className="space-y-4">
                    <Card>
                        <CardHeader className="pb-2">
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-base">
                                    Step 2: Search Queries Ready
                                </CardTitle>
                                <Badge variant="outline" className="text-xs">
                                    {generatedQueries.length} queries
                                </Badge>
                            </div>
                            <p className="text-sm text-muted-foreground mt-1">
                                Copy each query and run it on{" "}
                                {PLATFORMS.find((p) => p.value === platform)
                                    ?.label ?? "your research platform"}
                                . Then paste the results in Step 3.
                            </p>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            {generatedQueries.map((q, i) => (
                                <QueryCard key={i} query={q} index={i} />
                            ))}
                        </CardContent>
                    </Card>

                    {/* Platform tips */}
                    <Card className="border-dashed">
                        <CardHeader className="pb-0">
                            <button
                                onClick={() => setShowTips(!showTips)}
                                className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors w-full text-left"
                            >
                                <span
                                    className={`transition-transform ${showTips ? "rotate-90" : ""}`}
                                >
                                    {"\u25B6"}
                                </span>
                                {PLATFORMS.find((p) => p.value === platform)
                                    ?.label ?? "Platform"}{" "}
                                Search Syntax Tips
                            </button>
                        </CardHeader>
                        {showTips && (
                            <CardContent className="pt-2">
                                <ul className="space-y-1.5">
                                    {(
                                        PLATFORM_TIPS[platform] ??
                                        PLATFORM_TIPS.general
                                    ).map((tip, i) => (
                                        <li
                                            key={i}
                                            className="text-xs text-muted-foreground flex gap-2"
                                        >
                                            <span className="text-indigo-400 shrink-0">
                                                {"\u2022"}
                                            </span>
                                            {tip}
                                        </li>
                                    ))}
                                </ul>
                            </CardContent>
                        )}
                    </Card>

                    {/* Advance to paste step */}
                    <div className="flex items-center gap-3">
                        <Button onClick={() => setCurrentStep(3)}>
                            I&apos;ve Run My Searches — Paste Results
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setCurrentStep(1)}
                        >
                            Back to Focus
                        </Button>
                    </div>
                </div>
            )}

            {/* ---- Step 3: Paste Results ---- */}
            {currentStep === 3 && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">
                            Step 3: Paste Research Results
                        </CardTitle>
                        <p className="text-sm text-muted-foreground mt-1">
                            Paste the raw text from your{" "}
                            {PLATFORMS.find((p) => p.value === platform)
                                ?.label ?? "research platform"}{" "}
                            search results below. The AI will extract cases,
                            holdings, and strategic recommendations.
                        </p>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {/* Context reminder */}
                        {generatedQueries.length > 0 && (
                            <div className="bg-accent/30 rounded-md p-3">
                                <p className="text-xs font-medium text-muted-foreground mb-1.5">
                                    Queries you ran:
                                </p>
                                <ul className="space-y-1">
                                    {generatedQueries.map((q, i) => (
                                        <li
                                            key={i}
                                            className="text-xs text-muted-foreground font-mono truncate"
                                        >
                                            {i + 1}. {q.search_string}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        <div>
                            <label className="text-sm font-medium text-muted-foreground mb-1.5 block">
                                Paste your search results here
                            </label>
                            <textarea
                                ref={textareaRef}
                                value={pastedText}
                                onChange={(e) => setPastedText(e.target.value)}
                                placeholder="Paste raw text from Lexis+, Westlaw, Google Scholar, or any legal research source..."
                                className="w-full min-h-[300px] rounded-md border border-input bg-transparent px-3 py-2 text-sm font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-y"
                            />
                            <p className="text-xs text-muted-foreground mt-1">
                                {pastedText.length > 0
                                    ? `${pastedText.length.toLocaleString()} characters`
                                    : "Supports raw text from any legal research platform"}
                            </p>
                        </div>

                        <div className="flex items-center gap-3 pt-2">
                            <Button
                                onClick={() =>
                                    analyzeResultsMutation.mutate()
                                }
                                disabled={
                                    analyzeResultsMutation.isPending ||
                                    pastedText.trim().length < 10
                                }
                            >
                                {analyzeResultsMutation.isPending ? (
                                    <span className="flex items-center gap-2">
                                        <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                        Analyzing Results...
                                    </span>
                                ) : (
                                    "Analyze Results"
                                )}
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setCurrentStep(2)}
                            >
                                Back to Queries
                            </Button>
                            {analyzeResultsMutation.isError && (
                                <p className="text-xs text-red-400">
                                    Analysis failed. Please try again.
                                </p>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* ---- Step 4: Analysis Report ---- */}
            {currentStep === 4 && analysisResult && (
                <AnalysisReport
                    result={analysisResult}
                    onStartNewCycle={startNewCycle}
                    onBack={() => setCurrentStep(3)}
                />
            )}

            {/* ---- Research History ---- */}
            {researchHistory.length > 0 && (
                <Card className="border-dashed">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm text-muted-foreground">
                            Research History (this session)
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-2">
                            {researchHistory.map((entry) => (
                                <div
                                    key={entry.id}
                                    className="flex items-center justify-between text-xs py-1.5 border-b border-border last:border-0"
                                >
                                    <div className="flex items-center gap-3 min-w-0">
                                        <Badge
                                            variant="outline"
                                            className="shrink-0 text-[10px]"
                                        >
                                            {
                                                PLATFORMS.find(
                                                    (p) =>
                                                        p.value ===
                                                        entry.platform,
                                                )?.label
                                            }
                                        </Badge>
                                        <span className="text-muted-foreground truncate">
                                            {entry.focus}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-3 shrink-0">
                                        <span className="text-muted-foreground">
                                            {entry.queriesCount} queries
                                        </span>
                                        <span className="text-muted-foreground">
                                            {entry.casesFound} cases
                                        </span>
                                        <span className="text-muted-foreground">
                                            {entry.timestamp}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            <ModuleNotes
                caseId={caseId}
                prepId={prepId}
                moduleKey="research_command_center"
            />
        </div>
    );
}

// ---- Query Card ---------------------------------------------------------

function QueryCard({ query, index }: { query: LexisQuery; index: number }) {
    return (
        <div className="rounded-lg border border-border bg-accent/10 p-4 space-y-3">
            <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-indigo-400">
                        #{index + 1}
                    </span>
                    <p className="text-sm text-foreground">
                        {query.description}
                    </p>
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    className="shrink-0 text-xs"
                    onClick={() => copyToClipboard(query.search_string)}
                >
                    Copy
                </Button>
            </div>

            {/* Search string */}
            <div className="bg-zinc-900/80 rounded-md p-3 border border-zinc-800">
                <code className="text-xs text-emerald-400 font-mono break-all whitespace-pre-wrap">
                    {query.search_string}
                </code>
            </div>

            {/* Filters and relevance */}
            <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                {query.filters?.jurisdiction && (
                    <span>
                        <span className="font-medium">Jurisdiction:</span>{" "}
                        {query.filters.jurisdiction}
                    </span>
                )}
                {query.filters?.date_range && (
                    <span>
                        <span className="font-medium">Date Range:</span>{" "}
                        {query.filters.date_range}
                    </span>
                )}
                {query.filters?.court_level && (
                    <span>
                        <span className="font-medium">Court Level:</span>{" "}
                        {query.filters.court_level}
                    </span>
                )}
            </div>

            {query.case_relevance && (
                <p className="text-xs text-muted-foreground italic">
                    {query.case_relevance}
                </p>
            )}
        </div>
    );
}

// ---- Analysis Report ----------------------------------------------------

function AnalysisReport({
    result,
    onStartNewCycle,
    onBack,
}: {
    result: LexisAnalysisResult;
    onStartNewCycle: (prefillFocus?: string) => void;
    onBack: () => void;
}) {
    const [expandedQuotes, setExpandedQuotes] = useState<Set<number>>(
        new Set(),
    );

    const toggleQuotes = (idx: number) => {
        setExpandedQuotes((prev) => {
            const next = new Set(prev);
            if (next.has(idx)) next.delete(idx);
            else next.add(idx);
            return next;
        });
    };

    const favorableCases =
        result.cases?.filter((c) => c.favorability === "FAVORABLE") ?? [];
    const unfavorableCases =
        result.cases?.filter((c) => c.favorability === "UNFAVORABLE") ?? [];
    const neutralCases =
        result.cases?.filter((c) => c.favorability === "NEUTRAL") ?? [];

    return (
        <div className="space-y-4">
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-base">
                            Step 4: Analysis Report
                        </CardTitle>
                        <div className="flex items-center gap-2">
                            <Badge
                                className="bg-green-500/15 text-green-400 border-green-500/30"
                                variant="outline"
                            >
                                {favorableCases.length} Favorable
                            </Badge>
                            <Badge
                                className="bg-red-500/15 text-red-400 border-red-500/30"
                                variant="outline"
                            >
                                {unfavorableCases.length} Unfavorable
                            </Badge>
                            <Badge
                                className="bg-zinc-500/15 text-zinc-400 border-zinc-500/30"
                                variant="outline"
                            >
                                {neutralCases.length} Neutral
                            </Badge>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    {/* Research memo summary */}
                    {result.summary && (
                        <div className="mb-6">
                            <h4 className="text-sm font-semibold mb-2">
                                Research Memo
                            </h4>
                            <div className="bg-accent/30 rounded-md p-4">
                                <MarkdownContent content={result.summary} />
                            </div>
                        </div>
                    )}

                    {/* Case cards */}
                    {result.cases && result.cases.length > 0 ? (
                        <div className="space-y-3">
                            <h4 className="text-sm font-semibold">
                                Extracted Cases ({result.cases.length})
                            </h4>
                            {result.cases.map((c, i) => (
                                <CaseAnalysisCard
                                    key={i}
                                    caseData={c}
                                    index={i}
                                    isQuotesExpanded={expandedQuotes.has(i)}
                                    onToggleQuotes={() => toggleQuotes(i)}
                                />
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-muted-foreground text-center py-8">
                            No cases were extracted from the pasted text.
                            Try pasting more detailed search results.
                        </p>
                    )}
                </CardContent>
            </Card>

            {/* Recommended follow-up searches */}
            {result.recommended_next_searches &&
                result.recommended_next_searches.length > 0 && (
                    <Card className="border-indigo-500/20">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm">
                                Recommended Follow-Up Searches
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-2">
                                {result.recommended_next_searches.map(
                                    (search, i) => (
                                        <button
                                            key={i}
                                            onClick={() =>
                                                onStartNewCycle(search)
                                            }
                                            className="w-full text-left flex items-center gap-3 p-2.5 rounded-md border border-border hover:bg-accent/30 transition-colors group"
                                        >
                                            <span className="text-indigo-400 text-xs shrink-0">
                                                {"\u2192"}
                                            </span>
                                            <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors">
                                                {search}
                                            </span>
                                        </button>
                                    ),
                                )}
                            </div>
                        </CardContent>
                    </Card>
                )}

            {/* Actions */}
            <div className="flex items-center gap-3">
                <Button onClick={() => onStartNewCycle()}>
                    Start New Research Cycle
                </Button>
                <Button variant="ghost" size="sm" onClick={onBack}>
                    Back to Paste Results
                </Button>
            </div>
        </div>
    );
}

// ---- Case Analysis Card -------------------------------------------------

function CaseAnalysisCard({
    caseData,
    index,
    isQuotesExpanded,
    onToggleQuotes,
}: {
    caseData: LexisAnalysisCase;
    index: number;
    isQuotesExpanded: boolean;
    onToggleQuotes: () => void;
}) {
    const favColor =
        FAVORABILITY_COLORS[caseData.favorability] ??
        FAVORABILITY_COLORS.NEUTRAL;

    return (
        <div className="rounded-lg border border-border p-4 space-y-3 hover:bg-accent/10 transition-colors">
            {/* Header: citation + badges */}
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <p className="text-sm font-semibold text-foreground">
                        {caseData.citation}
                    </p>
                    {(caseData.court || caseData.year) && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                            {[caseData.court, caseData.year]
                                .filter(Boolean)
                                .join(" | ")}
                        </p>
                    )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    <Badge
                        variant="outline"
                        className={`text-[10px] ${favColor}`}
                    >
                        {caseData.favorability}
                    </Badge>
                    {caseData.strength && (
                        <StrengthIndicator strength={caseData.strength} />
                    )}
                </div>
            </div>

            {/* Holding */}
            {caseData.holding && (
                <div>
                    <p className="text-xs font-medium text-muted-foreground mb-0.5">
                        Holding
                    </p>
                    <p className="text-sm text-foreground">
                        {caseData.holding}
                    </p>
                </div>
            )}

            {/* Relevant facts */}
            {caseData.relevant_facts && (
                <div>
                    <p className="text-xs font-medium text-muted-foreground mb-0.5">
                        Relevant Facts
                    </p>
                    <p className="text-sm text-muted-foreground">
                        {caseData.relevant_facts}
                    </p>
                </div>
            )}

            {/* Strategic use */}
            {caseData.strategic_use && (
                <div className="bg-indigo-500/5 rounded-md p-2.5 border border-indigo-500/10">
                    <p className="text-xs font-medium text-indigo-400 mb-0.5">
                        Strategic Use
                    </p>
                    <p className="text-sm text-foreground">
                        {caseData.strategic_use}
                    </p>
                </div>
            )}

            {/* Key quotes (collapsible) */}
            {caseData.key_quotes && caseData.key_quotes.length > 0 && (
                <div>
                    <button
                        onClick={onToggleQuotes}
                        className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
                    >
                        <span
                            className={`transition-transform ${isQuotesExpanded ? "rotate-90" : ""}`}
                        >
                            {"\u25B6"}
                        </span>
                        Key Quotes ({caseData.key_quotes.length})
                    </button>
                    {isQuotesExpanded && (
                        <div className="mt-2 space-y-2">
                            {caseData.key_quotes.map((quote, qi) => (
                                <div
                                    key={qi}
                                    className="flex gap-2 items-start group"
                                >
                                    <div className="border-l-2 border-indigo-500/40 pl-3 py-0.5">
                                        <p className="text-xs text-muted-foreground italic">
                                            &ldquo;{quote}&rdquo;
                                        </p>
                                    </div>
                                    <button
                                        onClick={() => copyToClipboard(quote)}
                                        className="text-[10px] text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-0.5"
                                        title="Copy quote"
                                    >
                                        Copy
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Copy citation */}
            <div className="flex justify-end">
                <button
                    onClick={() => copyToClipboard(caseData.citation)}
                    className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
                >
                    Copy Citation
                </button>
            </div>
        </div>
    );
}

// ---- Civil Tools Panel ---------------------------------------------------

function CivilToolsPanel({
    caseId,
    prepId,
}: {
    caseId: string;
    prepId: string | null;
}) {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    const [medChronoResult, setMedChronoResult] = useState<string | null>(null);
    const [demandLetterResult, setDemandLetterResult] = useState<string | null>(
        null,
    );

    const medChronoMutation = useMutation({
        mutationFn: () =>
            api.post<{ status: string; result: Record<string, unknown> }>(
                `/cases/${caseId}/preparations/${prepId}/generate/medical-chronology`,
                {},
                { getToken },
            ),
        onSuccess: (data) => {
            const result = data.result;
            const content = result.medical_chronology;
            setMedChronoResult(
                typeof content === "string"
                    ? content
                    : JSON.stringify(content, null, 2),
            );
            queryClient.invalidateQueries({
                queryKey: ["cases", caseId, "prep-state", prepId],
            });
            toast.success("Medical chronology generated");
        },
        onError: (err: Error) => {
            toast.error("Medical chronology failed", {
                description: err.message,
            });
        },
    });

    const demandLetterMutation = useMutation({
        mutationFn: () =>
            api.post<{ status: string; result: Record<string, unknown> }>(
                `/cases/${caseId}/preparations/${prepId}/generate/demand-letter`,
                {},
                { getToken },
            ),
        onSuccess: (data) => {
            const result = data.result;
            const content = result.demand_letter;
            setDemandLetterResult(
                typeof content === "string"
                    ? content
                    : JSON.stringify(content, null, 2),
            );
            queryClient.invalidateQueries({
                queryKey: ["cases", caseId, "prep-state", prepId],
            });
            toast.success("Demand letter generated");
        },
        onError: (err: Error) => {
            toast.error("Demand letter failed", {
                description: err.message,
            });
        },
    });

    if (!prepId) {
        return (
            <Card className="border-dashed">
                <CardContent className="py-12 text-center text-muted-foreground">
                    Select a preparation to use civil tools.
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            {/* Medical Chronology */}
            <div className="space-y-3">
                <ResultSection
                    title="Medical Chronology"
                    icon={"\uD83C\uDFE5"}
                    isEmpty={!medChronoResult}
                    emptyMessage="Generate a structured medical chronology from case documents. Best suited for personal injury and medical malpractice cases."
                >
                    {medChronoResult && (
                        <MarkdownContent content={medChronoResult} />
                    )}
                </ResultSection>
                <div className="flex items-center gap-3">
                    <Button
                        size="sm"
                        onClick={() => medChronoMutation.mutate()}
                        disabled={medChronoMutation.isPending}
                        variant={medChronoResult ? "outline" : "default"}
                    >
                        {medChronoMutation.isPending ? (
                            <span className="flex items-center gap-2">
                                <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                Generating...
                            </span>
                        ) : medChronoResult ? (
                            "Regenerate"
                        ) : (
                            "Generate Medical Chronology"
                        )}
                    </Button>
                    {medChronoMutation.isError && (
                        <p className="text-xs text-red-400">
                            Generation failed. Please try again.
                        </p>
                    )}
                </div>
            </div>

            {/* Demand Letter */}
            <div className="space-y-3">
                <ResultSection
                    title="Demand Letter"
                    icon={"\uD83D\uDCC4"}
                    isEmpty={!demandLetterResult}
                    emptyMessage="Generate a demand letter for civil litigation. Includes damages summary, liability analysis, and settlement demand."
                >
                    {demandLetterResult && (
                        <MarkdownContent content={demandLetterResult} />
                    )}
                </ResultSection>
                <div className="flex items-center gap-3">
                    <Button
                        size="sm"
                        onClick={() => demandLetterMutation.mutate()}
                        disabled={demandLetterMutation.isPending}
                        variant={demandLetterResult ? "outline" : "default"}
                    >
                        {demandLetterMutation.isPending ? (
                            <span className="flex items-center gap-2">
                                <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                Generating...
                            </span>
                        ) : demandLetterResult ? (
                            "Regenerate"
                        ) : (
                            "Generate Demand Letter"
                        )}
                    </Button>
                    {demandLetterMutation.isError && (
                        <p className="text-xs text-red-400">
                            Generation failed. Please try again.
                        </p>
                    )}
                </div>
            </div>

            <ModuleNotes caseId={caseId} prepId={prepId} moduleKey="civil_tools" />
        </div>
    );
}
