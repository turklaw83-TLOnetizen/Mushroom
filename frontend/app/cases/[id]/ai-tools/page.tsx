// ---- AI Tools Tab (Phase 16) ----------------------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface ModelComparisonResult {
    model: string;
    response: string;
    latency_ms: number;
    tokens_used: number;
    cost_estimate: number;
}

interface SummarizationResult {
    summary: string;
    key_facts: string[];
    word_count: number;
}

interface SemanticSearchResult {
    content: string;
    score: number;
    source: string;
    page?: number;
}

export default function AIToolsPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const [activeTab, setActiveTab] = useState<"compare" | "summarize" | "search" | "predict">("compare");
    const [prompt, setPrompt] = useState("");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedModels, setSelectedModels] = useState<string[]>([
        "claude-sonnet",
        "grok-2",
    ]);

    const AVAILABLE_MODELS = [
        { id: "claude-sonnet", label: "Claude Sonnet", provider: "Anthropic" },
        { id: "claude-haiku", label: "Claude Haiku", provider: "Anthropic" },
        { id: "grok-2", label: "Grok 2", provider: "xAI" },
        { id: "gpt-4o", label: "GPT-4o", provider: "OpenAI" },
        { id: "gpt-4o-mini", label: "GPT-4o Mini", provider: "OpenAI" },
    ];

    // Model comparison mutation
    const compareMutation = useMutation({
        mutationFn: (data: { prompt: string; models: string[] }) =>
            api.post<{ results: ModelComparisonResult[] }>(
                `/ai-features/compare`,
                { ...data, case_id: caseId },
                { getToken },
            ),
    });

    // Summarization mutation
    const summarizeMutation = useMutation({
        mutationFn: () =>
            api.post<SummarizationResult>(
                `/ai-features/summarize/${caseId}`,
                {},
                { getToken },
            ),
    });

    // Semantic search mutation
    const searchMutation = useMutation({
        mutationFn: (query: string) =>
            api.post<{ results: SemanticSearchResult[] }>(
                `/ai-features/search/${caseId}`,
                { query, top_k: 10 },
                { getToken },
            ),
    });

    const toggleModel = (id: string) => {
        setSelectedModels((prev) =>
            prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id],
        );
    };

    return (
        <div className="space-y-5">
            <div>
                <h2 className="text-xl font-bold tracking-tight">AI Tools</h2>
                <p className="text-sm text-muted-foreground mt-0.5">
                    Multi-model comparison, semantic search, and AI-powered analysis
                </p>
            </div>

            {/* Tab Nav */}
            <div className="flex gap-1 border-b border-border">
                {[
                    { key: "compare" as const, label: "Model Compare" },
                    { key: "summarize" as const, label: "Summarize" },
                    { key: "search" as const, label: "Semantic Search" },
                    { key: "predict" as const, label: "Predict" },
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
                    </button>
                ))}
            </div>

            {activeTab === "compare" && (
                <div className="space-y-4">
                    {/* Model Selection */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Select Models</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="flex flex-wrap gap-2">
                                {AVAILABLE_MODELS.map((m) => (
                                    <button
                                        key={m.id}
                                        onClick={() => toggleModel(m.id)}
                                        className={`px-3 py-1.5 rounded-md text-sm border transition-colors ${
                                            selectedModels.includes(m.id)
                                                ? "bg-primary/10 border-primary text-primary"
                                                : "bg-muted border-border text-muted-foreground hover:text-foreground"
                                        }`}
                                    >
                                        {m.label}
                                        <span className="text-[10px] ml-1 opacity-60">{m.provider}</span>
                                    </button>
                                ))}
                            </div>
                        </CardContent>
                    </Card>

                    {/* Prompt Input */}
                    <Card>
                        <CardContent className="pt-4">
                            <textarea
                                placeholder="Enter your prompt to compare across models..."
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                                className="w-full h-32 text-sm bg-muted border border-border rounded-md px-3 py-2 resize-none"
                            />
                            <div className="flex justify-end mt-2">
                                <Button
                                    onClick={() =>
                                        compareMutation.mutate({
                                            prompt,
                                            models: selectedModels,
                                        })
                                    }
                                    disabled={!prompt || selectedModels.length === 0 || compareMutation.isPending}
                                >
                                    {compareMutation.isPending ? "Comparing..." : "Compare Models"}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Results */}
                    {compareMutation.data?.results && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {compareMutation.data.results.map((result, i) => (
                                <Card key={i}>
                                    <CardHeader>
                                        <div className="flex items-center justify-between">
                                            <CardTitle className="text-base">{result.model}</CardTitle>
                                            <div className="flex items-center gap-2">
                                                <Badge variant="outline" className="text-[10px]">
                                                    {result.latency_ms}ms
                                                </Badge>
                                                <Badge variant="secondary" className="text-[10px]">
                                                    {result.tokens_used} tokens
                                                </Badge>
                                                <Badge variant="outline" className="text-[10px]">
                                                    ${result.cost_estimate.toFixed(4)}
                                                </Badge>
                                            </div>
                                        </div>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="text-sm whitespace-pre-wrap max-h-80 overflow-y-auto">
                                            {result.response}
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {activeTab === "summarize" && (
                <div className="space-y-4">
                    <Card>
                        <CardContent className="py-8 text-center">
                            <p className="text-muted-foreground mb-4">
                                Generate an AI summary of all case documents.
                            </p>
                            <Button
                                onClick={() => summarizeMutation.mutate()}
                                disabled={summarizeMutation.isPending}
                            >
                                {summarizeMutation.isPending ? "Summarizing..." : "Summarize Case"}
                            </Button>
                        </CardContent>
                    </Card>

                    {summarizeMutation.data && (
                        <>
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-base">Summary</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <p className="text-sm whitespace-pre-wrap">
                                        {summarizeMutation.data.summary}
                                    </p>
                                    <p className="text-xs text-muted-foreground mt-2">
                                        {summarizeMutation.data.word_count} words
                                    </p>
                                </CardContent>
                            </Card>

                            {summarizeMutation.data.key_facts.length > 0 && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="text-base">Key Facts</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <ul className="space-y-2">
                                            {summarizeMutation.data.key_facts.map((f, i) => (
                                                <li key={i} className="text-sm flex gap-2">
                                                    <span className="text-indigo-400 font-bold shrink-0">
                                                        {i + 1}.
                                                    </span>
                                                    {f}
                                                </li>
                                            ))}
                                        </ul>
                                    </CardContent>
                                </Card>
                            )}
                        </>
                    )}
                </div>
            )}

            {activeTab === "search" && (
                <div className="space-y-4">
                    <Card>
                        <CardContent className="pt-4">
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    placeholder="Search across all case documents..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    onKeyDown={(e) =>
                                        e.key === "Enter" && searchQuery && searchMutation.mutate(searchQuery)
                                    }
                                    className="flex-1 text-sm bg-muted border border-border rounded-md px-3 py-1.5"
                                />
                                <Button
                                    onClick={() => searchMutation.mutate(searchQuery)}
                                    disabled={!searchQuery || searchMutation.isPending}
                                >
                                    {searchMutation.isPending ? "Searching..." : "Search"}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    {searchMutation.data?.results && (
                        <div className="space-y-2">
                            {searchMutation.data.results.map((result, i) => (
                                <Card key={i} className="hover:bg-accent/30 transition-colors">
                                    <CardContent className="py-3">
                                        <div className="flex items-start justify-between">
                                            <div className="flex-1">
                                                <p className="text-sm">{result.content}</p>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <span className="text-xs text-muted-foreground">
                                                        {result.source}
                                                    </span>
                                                    {result.page !== undefined && (
                                                        <span className="text-xs text-muted-foreground">
                                                            p.{result.page}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                            <Badge
                                                variant={result.score >= 0.8 ? "default" : "secondary"}
                                                className="ml-3 shrink-0"
                                            >
                                                {Math.round(result.score * 100)}%
                                            </Badge>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {activeTab === "predict" && (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        <p className="mb-2">Case outcome prediction is available in the Strategy tab.</p>
                        <p className="text-sm">
                            Navigate to Strategy &gt; Case Prediction for win/lose/settle probabilities.
                        </p>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
