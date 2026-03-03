// ---- Research Tab — Full Implementation -----------------------------------
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

interface ResearchItem {
    id?: string;
    topic: string;
    summary: string;
    source: string;
    citations: string[];
    jurisdiction?: string;
    relevance_score?: number;
    created_at?: string;
}

interface LegalResearchResult {
    research_items: ResearchItem[];
    case_law: Array<{
        case_name: string;
        citation: string;
        holding: string;
        relevance: string;
        year?: string;
    }>;
    statutes: Array<{
        title: string;
        section: string;
        text: string;
        jurisdiction: string;
    }>;
}

export default function ResearchPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, isLoading: prepLoading } = usePrep();
    const queryClient = useQueryClient();
    const [searchQuery, setSearchQuery] = useState("");
    const [activeTab, setActiveTab] = useState<"research" | "caselaw" | "statutes">("research");

    const { data, isLoading, error } = useQuery({
        queryKey: ["research", caseId, activePrepId],
        queryFn: () =>
            api.get<LegalResearchResult>(
                `/cases/${caseId}/preparations/${activePrepId}/research`,
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    const runResearchMutation = useMutation({
        mutationFn: (query: string) =>
            api.post<{ status: string }>(
                `/cases/${caseId}/preparations/${activePrepId}/research/run`,
                { query, jurisdiction: "federal" },
                { getToken },
            ),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["research", caseId, activePrepId] });
        },
    });

    // ---- Demand Letter On-Demand Generation ---------------------------------

    const [demandLetterResult, setDemandLetterResult] = useState<string | null>(null);
    const [demandLetterExpanded, setDemandLetterExpanded] = useState(false);

    const demandLetterMutation = useMutation({
        mutationFn: () =>
            api.post<{ result?: string; content?: string }>(
                `/cases/${caseId}/ondemand/demand-letter`,
                { prep_id: activePrepId },
                { getToken },
            ),
        onSuccess: (data) => {
            const text = data.result ?? data.content ?? JSON.stringify(data, null, 2);
            setDemandLetterResult(text);
            setDemandLetterExpanded(true);
            toast.success("Demand letter generated");
        },
        onError: (err: Error) => {
            toast.error("Failed to generate demand letter", { description: err.message });
        },
    });

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">
                    Create a preparation first to view research.
                </p>
            </div>
        );
    }

    const research = data?.research_items || [];
    const caseLaw = data?.case_law || [];
    const statutes = data?.statutes || [];
    const filteredResearch = searchQuery
        ? research.filter(
              (r) =>
                  r.topic?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                  r.summary?.toLowerCase().includes(searchQuery.toLowerCase()),
          )
        : research;

    return (
        <div className="space-y-5">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">Legal Research</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Case law, statutes, and research analysis
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <input
                        type="text"
                        placeholder="Search research..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="text-sm bg-muted border border-border rounded-md px-3 py-1.5 w-64"
                    />
                    <Button
                        size="sm"
                        onClick={() => runResearchMutation.mutate(searchQuery || "general")}
                        disabled={runResearchMutation.isPending}
                    >
                        {runResearchMutation.isPending ? "Running..." : "Run Research"}
                    </Button>
                </div>
            </div>

            {/* Tab Navigation */}
            <div className="flex gap-1 border-b border-border">
                {[
                    { key: "research" as const, label: "Research", count: research.length },
                    { key: "caselaw" as const, label: "Case Law", count: caseLaw.length },
                    { key: "statutes" as const, label: "Statutes", count: statutes.length },
                ].map((tab) => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                            activeTab === tab.key
                                ? "border-primary text-primary"
                                : "border-transparent text-muted-foreground hover:text-foreground"
                        }`}
                    >
                        {tab.label}
                        {tab.count > 0 && (
                            <Badge variant="secondary" className="ml-2 text-[10px]">
                                {tab.count}
                            </Badge>
                        )}
                    </button>
                ))}
            </div>

            {isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-24 w-full rounded-lg" />
                    ))}
                </div>
            ) : error ? (
                <Card className="border-dashed">
                    <CardContent className="py-8 text-center text-muted-foreground">
                        Failed to load research data. Run analysis first.
                    </CardContent>
                </Card>
            ) : activeTab === "research" ? (
                filteredResearch.length === 0 ? (
                    <Card className="border-dashed">
                        <CardContent className="py-12 text-center text-muted-foreground">
                            <p className="text-lg mb-2">No research data yet</p>
                            <p className="text-sm">
                                Run the Legal Researcher analysis module to populate this tab,
                                or click &quot;Run Research&quot; to search for specific topics.
                            </p>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="space-y-3">
                        {filteredResearch.map((item, i) => (
                            <Card key={item.id || i} className="hover:bg-accent/30 transition-colors">
                                <CardContent className="py-4">
                                    <div className="flex items-start justify-between">
                                        <div className="flex-1">
                                            <p className="font-medium text-sm">
                                                {item.topic || `Research Item ${i + 1}`}
                                            </p>
                                            {item.summary && (
                                                <p className="text-sm text-muted-foreground mt-1 whitespace-pre-wrap">
                                                    {item.summary}
                                                </p>
                                            )}
                                        </div>
                                        {item.relevance_score !== undefined && (
                                            <Badge
                                                variant={
                                                    item.relevance_score >= 0.8
                                                        ? "default"
                                                        : "secondary"
                                                }
                                                className="ml-3 shrink-0"
                                            >
                                                {Math.round(item.relevance_score * 100)}%
                                            </Badge>
                                        )}
                                    </div>
                                    {item.source && (
                                        <p className="text-xs text-muted-foreground mt-2">
                                            Source: {item.source}
                                        </p>
                                    )}
                                    {item.citations && item.citations.length > 0 && (
                                        <div className="mt-2 flex flex-wrap gap-1">
                                            {item.citations.map((c, ci) => (
                                                <Badge key={ci} variant="outline" className="text-[10px]">
                                                    {c}
                                                </Badge>
                                            ))}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )
            ) : activeTab === "caselaw" ? (
                caseLaw.length === 0 ? (
                    <Card className="border-dashed">
                        <CardContent className="py-12 text-center text-muted-foreground">
                            No case law found. Run the Legal Researcher module.
                        </CardContent>
                    </Card>
                ) : (
                    <div className="space-y-3">
                        {caseLaw.map((cl, i) => (
                            <Card key={i}>
                                <CardContent className="py-4">
                                    <div className="flex items-start justify-between">
                                        <p className="font-medium text-sm">{cl.case_name}</p>
                                        {cl.year && (
                                            <Badge variant="outline" className="text-xs shrink-0 ml-2">
                                                {cl.year}
                                            </Badge>
                                        )}
                                    </div>
                                    <p className="text-xs text-muted-foreground mt-1">
                                        {cl.citation}
                                    </p>
                                    <p className="text-sm mt-2">{cl.holding}</p>
                                    <p className="text-xs text-indigo-400 mt-1">
                                        Relevance: {cl.relevance}
                                    </p>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )
            ) : (
                statutes.length === 0 ? (
                    <Card className="border-dashed">
                        <CardContent className="py-12 text-center text-muted-foreground">
                            No statutes found. Run the Legal Researcher module.
                        </CardContent>
                    </Card>
                ) : (
                    <div className="space-y-3">
                        {statutes.map((s, i) => (
                            <Card key={i}>
                                <CardContent className="py-4">
                                    <p className="font-medium text-sm">{s.title}</p>
                                    <p className="text-xs text-muted-foreground">
                                        {s.section} | {s.jurisdiction}
                                    </p>
                                    <p className="text-sm mt-2 whitespace-pre-wrap">{s.text}</p>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )
            )}

            {/* ---- Generate Demand Letter ---- */}
            <Card>
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0">
                            <CardTitle className="text-sm font-medium">
                                Generate Demand Letter
                            </CardTitle>
                            <p className="text-xs text-muted-foreground mt-0.5">
                                AI-generated demand letter based on case analysis and research.
                            </p>
                        </div>
                        <Button
                            size="sm"
                            variant={demandLetterResult ? "outline" : "default"}
                            disabled={demandLetterMutation.isPending}
                            onClick={() => demandLetterMutation.mutate()}
                            className="shrink-0"
                        >
                            {demandLetterMutation.isPending ? (
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
                            ) : demandLetterResult ? (
                                "Regenerate"
                            ) : (
                                "Generate Demand Letter"
                            )}
                        </Button>
                    </div>
                </CardHeader>
            </Card>

            {demandLetterResult && (
                <Card className="border-primary/20">
                    <CardHeader className="pb-0 pt-3 px-4">
                        <button
                            type="button"
                            className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors w-full text-left"
                            onClick={() => setDemandLetterExpanded((prev) => !prev)}
                        >
                            <span
                                className={`transition-transform ${
                                    demandLetterExpanded ? "rotate-90" : ""
                                }`}
                            >
                                {"\u25B6"}
                            </span>
                            {demandLetterExpanded ? "Collapse" : "Expand"} result
                            <Badge variant="outline" className="ml-auto text-[10px]">
                                AI Generated
                            </Badge>
                        </button>
                    </CardHeader>
                    {demandLetterExpanded && (
                        <CardContent className="pt-3 px-4 pb-4">
                            <div className="prose prose-sm dark:prose-invert max-w-none">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {demandLetterResult}
                                </ReactMarkdown>
                            </div>
                        </CardContent>
                    )}
                </Card>
            )}
        </div>
    );
}
