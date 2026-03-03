// ---- Strategy Tab — Full Implementation -----------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { usePrep } from "@/hooks/use-prep";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

interface StrategyData {
    strategy_notes: string;
    devils_advocate_notes: string;
    voir_dire: {
        ideal_juror_profile?: string;
        questions?: Array<{ question: string; purpose: string }>;
        red_flags?: string[];
        demographic_considerations?: string;
    };
    mock_jury_feedback: Array<{
        juror_profile: string;
        verdict: string;
        reasoning: string;
        credibility_concerns: string[];
        emotional_impact: string;
    }>;
    prediction?: {
        win_probability: number;
        settle_probability: number;
        lose_probability: number;
        confidence: number;
        key_factors: string[];
    };
}

/** Shape returned by on-demand generation endpoints. */
interface OnDemandResult {
    result?: string;
    content?: string;
    [key: string]: unknown;
}

/** Extract readable text from an on-demand result object. */
function extractResultText(data: OnDemandResult): string {
    return data.result ?? data.content ?? JSON.stringify(data, null, 2);
}

/** Configuration for each on-demand AI tool button. */
interface OnDemandTool {
    key: string;
    label: string;
    endpoint: string;
    description: string;
}

const ON_DEMAND_TOOLS: OnDemandTool[] = [
    {
        key: "client-report",
        label: "Generate Client Report",
        endpoint: "client-report",
        description: "Produce a plain-language case summary suitable for client review.",
    },
    {
        key: "opponent-playbook",
        label: "Generate Opponent Playbook",
        endpoint: "opponent-playbook",
        description: "Anticipate the opposing counsel's likely arguments and tactics.",
    },
    {
        key: "case-theory",
        label: "Validate Case Theory",
        endpoint: "case-theory",
        description: "Stress-test the current case theory for logical consistency.",
    },
    {
        key: "jury-instructions",
        label: "Generate Jury Instructions",
        endpoint: "jury-instructions",
        description: "Draft proposed jury instructions tailored to the charges and facts.",
    },
    {
        key: "statements",
        label: "Generate Statements",
        endpoint: "statements",
        description: "Draft opening and closing statement outlines for trial.",
    },
];

export default function StrategyPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, isLoading: prepLoading } = usePrep();
    const queryClient = useQueryClient();
    const [activeSection, setActiveSection] = useState<
        "strategy" | "devils" | "voirdire" | "mockjury" | "prediction"
    >("strategy");

    const { data, isLoading } = useQuery({
        queryKey: ["strategy", caseId, activePrepId],
        queryFn: () =>
            api.get<StrategyData>(
                `/cases/${caseId}/preparations/${activePrepId}/strategy`,
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    const predictMutation = useMutation({
        mutationFn: () =>
            api.post(
                `/cases/${caseId}/preparations/${activePrepId}/predict`,
                {},
                { getToken },
            ),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["strategy", caseId, activePrepId] });
        },
    });

    // ---- On-Demand AI Tools state -------------------------------------------

    /** Stores generated markdown results keyed by tool key (e.g. "client-report"). */
    const [onDemandResults, setOnDemandResults] = useState<Record<string, string>>({});

    /** Tracks which tool sections are expanded. */
    const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});

    /** Tracks which tool is currently generating. */
    const [generatingTool, setGeneratingTool] = useState<string | null>(null);

    const onDemandMutation = useMutation({
        mutationFn: (tool: OnDemandTool) =>
            api.post<OnDemandResult>(
                `/cases/${caseId}/ondemand/${tool.endpoint}`,
                { prep_id: activePrepId },
                { getToken },
            ),
        onSuccess: (data, tool) => {
            const text = extractResultText(data);
            setOnDemandResults((prev) => ({ ...prev, [tool.key]: text }));
            setExpandedTools((prev) => ({ ...prev, [tool.key]: true }));
            toast.success(`${tool.label.replace("Generate ", "").replace("Validate ", "")} generated`);
            setGeneratingTool(null);
        },
        onError: (err: Error, tool) => {
            toast.error(`Failed: ${tool.label}`, { description: err.message });
            setGeneratingTool(null);
        },
    });

    const handleGenerate = (tool: OnDemandTool) => {
        setGeneratingTool(tool.key);
        onDemandMutation.mutate(tool);
    };

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">
                    Create a preparation first to manage strategy.
                </p>
            </div>
        );
    }

    if (isLoading) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-10 w-64" />
                <Skeleton className="h-40 rounded-lg" />
                <Skeleton className="h-40 rounded-lg" />
            </div>
        );
    }

    const sections = [
        { key: "strategy" as const, label: "Strategy Notes" },
        { key: "devils" as const, label: "Devil's Advocate" },
        { key: "voirdire" as const, label: "Voir Dire" },
        { key: "mockjury" as const, label: `Mock Jury (${data?.mock_jury_feedback?.length || 0})` },
        { key: "prediction" as const, label: "Case Prediction" },
    ];

    return (
        <div className="space-y-5">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">Strategy Center</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Strategy recommendations, jury analysis, and predictions
                    </p>
                </div>
            </div>

            {/* Section Navigation */}
            <div className="flex gap-1 border-b border-border overflow-x-auto">
                {sections.map((s) => (
                    <button
                        key={s.key}
                        onClick={() => setActiveSection(s.key)}
                        className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                            activeSection === s.key
                                ? "border-primary text-primary"
                                : "border-transparent text-muted-foreground hover:text-foreground"
                        }`}
                    >
                        {s.label}
                    </button>
                ))}
            </div>

            {activeSection === "strategy" && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Strategy Notes</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {data?.strategy_notes ? (
                            <div className="prose prose-sm dark:prose-invert max-w-none">
                                <div className="text-sm whitespace-pre-wrap">{data.strategy_notes}</div>
                            </div>
                        ) : (
                            <p className="text-sm text-muted-foreground italic">
                                No strategy notes yet. Run the Strategist analysis module to generate recommendations.
                            </p>
                        )}
                    </CardContent>
                </Card>
            )}

            {activeSection === "devils" && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Devil&apos;s Advocate Analysis</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {data?.devils_advocate_notes ? (
                            <div className="text-sm whitespace-pre-wrap">
                                {data.devils_advocate_notes}
                            </div>
                        ) : (
                            <p className="text-sm text-muted-foreground italic">
                                No devil&apos;s advocate analysis yet. Run the analysis to see counterarguments.
                            </p>
                        )}
                    </CardContent>
                </Card>
            )}

            {activeSection === "voirdire" && (
                <div className="space-y-4">
                    {data?.voir_dire && Object.keys(data.voir_dire).length > 0 ? (
                        <>
                            {data.voir_dire.ideal_juror_profile && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="text-base">Ideal Juror Profile</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <p className="text-sm whitespace-pre-wrap">
                                            {data.voir_dire.ideal_juror_profile}
                                        </p>
                                    </CardContent>
                                </Card>
                            )}
                            {data.voir_dire.questions && data.voir_dire.questions.length > 0 && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="text-base">
                                            Voir Dire Questions ({data.voir_dire.questions.length})
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-3">
                                            {data.voir_dire.questions.map((q, i) => (
                                                <div key={i} className="p-3 bg-muted rounded-lg">
                                                    <p className="text-sm font-medium">
                                                        {i + 1}. {q.question}
                                                    </p>
                                                    <p className="text-xs text-muted-foreground mt-1">
                                                        Purpose: {q.purpose}
                                                    </p>
                                                </div>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            )}
                            {data.voir_dire.red_flags && data.voir_dire.red_flags.length > 0 && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="text-base">Red Flags</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <ul className="space-y-1">
                                            {data.voir_dire.red_flags.map((f, i) => (
                                                <li key={i} className="text-sm flex items-start gap-2">
                                                    <span className="text-red-400">!</span> {f}
                                                </li>
                                            ))}
                                        </ul>
                                    </CardContent>
                                </Card>
                            )}
                        </>
                    ) : (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No voir dire data. Run the Voir Dire Agent analysis module.
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}

            {activeSection === "mockjury" && (
                <div className="space-y-4">
                    {data?.mock_jury_feedback && data.mock_jury_feedback.length > 0 ? (
                        data.mock_jury_feedback.map((fb, i) => (
                            <Card key={i}>
                                <CardHeader>
                                    <div className="flex items-center justify-between">
                                        <CardTitle className="text-base">
                                            Juror {i + 1}: {fb.juror_profile}
                                        </CardTitle>
                                        <Badge
                                            variant={
                                                fb.verdict?.toLowerCase().includes("guilty") ||
                                                fb.verdict?.toLowerCase().includes("plaintiff")
                                                    ? "destructive"
                                                    : "default"
                                            }
                                        >
                                            {fb.verdict}
                                        </Badge>
                                    </div>
                                </CardHeader>
                                <CardContent className="space-y-2">
                                    <div>
                                        <p className="text-xs font-medium text-muted-foreground">
                                            Reasoning
                                        </p>
                                        <p className="text-sm">{fb.reasoning}</p>
                                    </div>
                                    {fb.credibility_concerns?.length > 0 && (
                                        <div>
                                            <p className="text-xs font-medium text-muted-foreground">
                                                Credibility Concerns
                                            </p>
                                            <div className="flex flex-wrap gap-1 mt-1">
                                                {fb.credibility_concerns.map((c, ci) => (
                                                    <Badge key={ci} variant="outline" className="text-[10px]">
                                                        {c}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {fb.emotional_impact && (
                                        <div>
                                            <p className="text-xs font-medium text-muted-foreground">
                                                Emotional Impact
                                            </p>
                                            <p className="text-sm">{fb.emotional_impact}</p>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        ))
                    ) : (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No mock jury feedback. Run the Mock Jury analysis module.
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}

            {activeSection === "prediction" && (
                <div className="space-y-4">
                    {data?.prediction ? (
                        <>
                            <div className="grid grid-cols-3 gap-4">
                                <Card>
                                    <CardContent className="py-6 text-center">
                                        <p className="text-3xl font-bold text-emerald-400">
                                            {Math.round(data.prediction.win_probability * 100)}%
                                        </p>
                                        <p className="text-sm text-muted-foreground mt-1">Win</p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="py-6 text-center">
                                        <p className="text-3xl font-bold text-amber-400">
                                            {Math.round(data.prediction.settle_probability * 100)}%
                                        </p>
                                        <p className="text-sm text-muted-foreground mt-1">Settle</p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="py-6 text-center">
                                        <p className="text-3xl font-bold text-red-400">
                                            {Math.round(data.prediction.lose_probability * 100)}%
                                        </p>
                                        <p className="text-sm text-muted-foreground mt-1">Lose</p>
                                    </CardContent>
                                </Card>
                            </div>
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-base">Key Factors</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <ul className="space-y-2">
                                        {data.prediction.key_factors.map((f, i) => (
                                            <li key={i} className="text-sm flex items-start gap-2">
                                                <span className="text-indigo-400 font-bold">{i + 1}.</span> {f}
                                            </li>
                                        ))}
                                    </ul>
                                    <p className="text-xs text-muted-foreground mt-4">
                                        Confidence: {Math.round(data.prediction.confidence * 100)}%
                                    </p>
                                </CardContent>
                            </Card>
                        </>
                    ) : (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                <p className="mb-4">No prediction data yet.</p>
                                <Button
                                    onClick={() => predictMutation.mutate()}
                                    disabled={predictMutation.isPending}
                                >
                                    {predictMutation.isPending ? "Generating..." : "Generate Prediction"}
                                </Button>
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}

            {/* ---- On-Demand AI Tools ----------------------------------------- */}
            <div className="border-t border-border pt-6 mt-6 space-y-4">
                <div>
                    <h3 className="text-lg font-semibold tracking-tight">On-Demand AI Tools</h3>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Generate additional strategic documents and analyses on demand.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {ON_DEMAND_TOOLS.map((tool) => {
                        const isGenerating = generatingTool === tool.key;
                        const result = onDemandResults[tool.key];
                        const isExpanded = expandedTools[tool.key] ?? false;

                        return (
                            <div key={tool.key} className="space-y-2">
                                <Card>
                                    <CardHeader className="pb-3">
                                        <div className="flex items-center justify-between gap-2">
                                            <div className="min-w-0">
                                                <CardTitle className="text-sm font-medium">
                                                    {tool.label}
                                                </CardTitle>
                                                <p className="text-xs text-muted-foreground mt-0.5">
                                                    {tool.description}
                                                </p>
                                            </div>
                                            <Button
                                                size="sm"
                                                variant={result ? "outline" : "default"}
                                                disabled={isGenerating}
                                                onClick={() => handleGenerate(tool)}
                                                className="shrink-0"
                                            >
                                                {isGenerating ? (
                                                    <>
                                                        <svg
                                                            className="animate-spin h-3 w-3 mr-1.5"
                                                            xmlns="http://www.w3.org/2000/svg"
                                                            fill="none"
                                                            viewBox="0 0 24 24"
                                                        >
                                                            <circle
                                                                className="opacity-25"
                                                                cx="12"
                                                                cy="12"
                                                                r="10"
                                                                stroke="currentColor"
                                                                strokeWidth="4"
                                                            />
                                                            <path
                                                                className="opacity-75"
                                                                fill="currentColor"
                                                                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                                                            />
                                                        </svg>
                                                        Generating...
                                                    </>
                                                ) : result ? (
                                                    "Regenerate"
                                                ) : (
                                                    "Generate"
                                                )}
                                            </Button>
                                        </div>
                                    </CardHeader>
                                </Card>

                                {/* Collapsible result card */}
                                {result && (
                                    <Card className="border-primary/20">
                                        <CardHeader className="pb-0 pt-3 px-4">
                                            <button
                                                type="button"
                                                className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors w-full text-left"
                                                onClick={() =>
                                                    setExpandedTools((prev) => ({
                                                        ...prev,
                                                        [tool.key]: !prev[tool.key],
                                                    }))
                                                }
                                            >
                                                <span
                                                    className={`transition-transform ${
                                                        isExpanded ? "rotate-90" : ""
                                                    }`}
                                                >
                                                    {"\u25B6"}
                                                </span>
                                                {isExpanded ? "Collapse" : "Expand"} result
                                                <Badge variant="outline" className="ml-auto text-[10px]">
                                                    AI Generated
                                                </Badge>
                                            </button>
                                        </CardHeader>
                                        {isExpanded && (
                                            <CardContent className="pt-3 px-4 pb-4">
                                                <div className="prose prose-sm dark:prose-invert max-w-none">
                                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                        {result}
                                                    </ReactMarkdown>
                                                </div>
                                            </CardContent>
                                        )}
                                    </Card>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
