// ---- Ask Your Case (AI Case Q&A) ----------------------------------------
// Natural language questions against all case analysis data.
// Streams AI responses in real-time via Server-Sent Events.
"use client";

import { useCallback, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { usePrep } from "@/hooks/use-prep";
import { routes } from "@/lib/api-routes";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface QAEntry {
    question: string;
    answer: string;
    timestamp: string;
}

const SUGGESTED_QUESTIONS = [
    "What are the strongest pieces of evidence in this case?",
    "Summarize the key weaknesses the opposing side will exploit",
    "Which witnesses are most vulnerable to cross-examination?",
    "What are the critical timeline gaps?",
    "List the legal elements we still need to prove",
    "What inconsistencies exist in the evidence?",
];

export default function AskCasePage() {
    const { id: caseId } = useParams<{ id: string }>();
    const { activePrep: prep } = usePrep();
    const { getToken } = useAuth();
    const [question, setQuestion] = useState("");
    const [streaming, setStreaming] = useState(false);
    const [currentAnswer, setCurrentAnswer] = useState("");
    const [history, setHistory] = useState<QAEntry[]>([]);
    const [error, setError] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const answerRef = useRef<HTMLDivElement>(null);

    const askQuestion = useCallback(
        async (q: string) => {
            if (!prep?.id || !q.trim() || streaming) return;

            const trimmedQ = q.trim();
            setQuestion("");
            setStreaming(true);
            setCurrentAnswer("");
            setError("");

            try {
                const token = await getToken();
                const url = `${API_BASE}/api/v1${routes.caseQA.ask(caseId, prep.id)}`;

                // Read CSRF cookie
                const csrfMatch = document.cookie.match(/mc-csrf=([^;]+)/);
                const headers: Record<string, string> = {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                };
                if (csrfMatch) headers["X-CSRF-Token"] = csrfMatch[1];

                const res = await fetch(url, {
                    method: "POST",
                    headers,
                    credentials: "include",
                    body: JSON.stringify({ question: trimmedQ }),
                });

                if (!res.ok) {
                    const errBody = await res.json().catch(() => ({}));
                    throw new Error(errBody.detail || `Request failed (${res.status})`);
                }

                const reader = res.body?.getReader();
                if (!reader) throw new Error("No response stream");

                const decoder = new TextDecoder();
                let accumulated = "";
                let fullAnswer = "";

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    accumulated += decoder.decode(value, { stream: true });
                    const lines = accumulated.split("\n");
                    accumulated = lines.pop() || "";

                    for (const line of lines) {
                        if (!line.startsWith("data: ")) continue;
                        try {
                            const parsed = JSON.parse(line.slice(6));
                            if (parsed.type === "token") {
                                fullAnswer += parsed.content;
                                setCurrentAnswer(fullAnswer);
                            } else if (parsed.type === "done") {
                                fullAnswer = parsed.content;
                                setCurrentAnswer(fullAnswer);
                            } else if (parsed.type === "error") {
                                throw new Error(parsed.content);
                            }
                        } catch {
                            // Skip malformed lines
                        }
                    }

                    // Auto-scroll to bottom
                    answerRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
                }

                setHistory((prev) => [
                    { question: trimmedQ, answer: fullAnswer, timestamp: new Date().toISOString() },
                    ...prev,
                ]);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to get answer");
            } finally {
                setStreaming(false);
            }
        },
        [caseId, prep?.id, streaming, getToken]
    );

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        askQuestion(question);
    };

    if (!prep) {
        return (
            <div className="p-6">
                <p className="text-muted-foreground">Select a preparation to ask questions about your case.</p>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-[calc(100vh-10rem)]">
            {/* Header */}
            <div className="px-6 pt-4 pb-2">
                <h1 className="text-2xl font-bold">Ask Your Case</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Ask any question about your case — AI searches across all analysis, evidence, witnesses, and strategy.
                </p>
            </div>

            {/* Main content area */}
            <div className="flex-1 overflow-y-auto px-6 pb-4 space-y-4">
                {/* Suggested questions (show when no history and not streaming) */}
                {history.length === 0 && !streaming && !currentAnswer && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
                        {SUGGESTED_QUESTIONS.map((sq) => (
                            <button
                                key={sq}
                                onClick={() => askQuestion(sq)}
                                className="text-left p-4 rounded-lg border border-white/10 bg-white/[0.02] hover:bg-white/[0.05] hover:border-indigo-500/30 transition-all text-sm text-zinc-300"
                            >
                                {sq}
                            </button>
                        ))}
                    </div>
                )}

                {/* Current streaming answer */}
                {(streaming || currentAnswer) && (
                    <Card className="border-indigo-500/20 bg-indigo-500/[0.03]">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium text-indigo-400">
                                {streaming ? "Analyzing..." : "Answer"}
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div ref={answerRef} className="prose prose-invert prose-sm max-w-none">
                                {currentAnswer ? (
                                    <div className="whitespace-pre-wrap">{currentAnswer}</div>
                                ) : (
                                    <div className="space-y-2">
                                        <Skeleton className="h-4 w-full" />
                                        <Skeleton className="h-4 w-3/4" />
                                        <Skeleton className="h-4 w-5/6" />
                                    </div>
                                )}
                                {streaming && (
                                    <span className="inline-block w-2 h-4 bg-indigo-400 animate-pulse ml-0.5" />
                                )}
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Error */}
                {error && (
                    <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
                        <p className="text-sm text-red-400">{error}</p>
                    </div>
                )}

                {/* History */}
                {history.map((entry, i) => (
                    <Card key={i} className="border-white/5">
                        <CardContent className="pt-4">
                            <p className="text-sm font-medium text-zinc-300 mb-3">
                                Q: {entry.question}
                            </p>
                            <div className="prose prose-invert prose-sm max-w-none text-zinc-400">
                                <div className="whitespace-pre-wrap">{entry.answer}</div>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Input bar (fixed at bottom) */}
            <div className="px-6 py-4 border-t border-white/10 bg-background">
                <form onSubmit={handleSubmit} className="flex gap-3">
                    <textarea
                        ref={textareaRef}
                        value={question}
                        onChange={(e) => setQuestion(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                handleSubmit(e);
                            }
                        }}
                        placeholder="Ask anything about your case..."
                        rows={1}
                        className="flex-1 resize-none rounded-lg border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50"
                        disabled={streaming}
                    />
                    <Button
                        type="submit"
                        disabled={!question.trim() || streaming}
                        className="bg-indigo-600 hover:bg-indigo-500 px-6"
                    >
                        {streaming ? (
                            <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                        ) : (
                            "Ask"
                        )}
                    </Button>
                </form>
            </div>
        </div>
    );
}
