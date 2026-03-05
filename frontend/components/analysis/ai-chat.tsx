// ---- AI Chat Panel -------------------------------------------------------
// Streaming chat component for contextual AI assistance.
// Uses SSE streaming via the useAiChat hook.
"use client";

import { useState, useRef, useEffect } from "react";
import { useAiChat } from "@/hooks/use-ai-chat";
import { MarkdownContent } from "./markdown-content";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface AiChatProps {
    caseId: string;
    prepId: string | null;
    contextModule?: string;
}

export function AiChat({ caseId, prepId, contextModule = "general" }: AiChatProps) {
    const {
        messages,
        isStreaming,
        streamingContent,
        sendMessage,
        stopStreaming,
        clearHistory,
        isLoadingHistory,
    } = useAiChat(caseId, prepId, contextModule);

    const [input, setInput] = useState("");
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, streamingContent]);

    // Auto-focus input
    useEffect(() => {
        inputRef.current?.focus();
    }, []);

    const handleSubmit = (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!input.trim() || isStreaming) return;
        sendMessage(input);
        setInput("");
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    };

    if (!prepId) {
        return (
            <Card className="border-dashed">
                <CardContent className="py-8 text-center">
                    <p className="text-sm text-muted-foreground">
                        Create a preparation first to use AI Chat.
                    </p>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="flex flex-col h-[600px]">
            <CardHeader className="pb-2 flex flex-row items-center justify-between shrink-0">
                <CardTitle className="text-base flex items-center gap-2">
                    <span aria-hidden="true">💬</span> AI Assistant
                    <span className="text-xs text-muted-foreground font-normal">
                        ({contextModule})
                    </span>
                </CardTitle>
                <div className="flex items-center gap-2">
                    {messages.length > 0 && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={clearHistory}
                            className="text-xs h-7"
                        >
                            Clear
                        </Button>
                    )}
                </div>
            </CardHeader>

            {/* Messages Area */}
            <CardContent className="flex-1 overflow-y-auto space-y-3 px-4">
                {isLoadingHistory ? (
                    <div className="space-y-3">
                        <Skeleton className="h-12 w-3/4" />
                        <Skeleton className="h-16 w-5/6 ml-auto" />
                        <Skeleton className="h-12 w-2/3" />
                    </div>
                ) : messages.length === 0 && !isStreaming ? (
                    <div className="flex items-center justify-center h-full">
                        <div className="text-center space-y-2">
                            <p className="text-sm text-muted-foreground">
                                Ask questions about your case analysis.
                            </p>
                            <div className="flex flex-wrap gap-2 justify-center mt-3">
                                {suggestedPrompts(contextModule).map((prompt, i) => (
                                    <button
                                        key={i}
                                        className="text-xs px-3 py-1.5 rounded-full border border-border hover:bg-accent transition-colors text-muted-foreground"
                                        onClick={() => {
                                            setInput(prompt);
                                            inputRef.current?.focus();
                                        }}
                                    >
                                        {prompt}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                ) : (
                    <>
                        {messages.map((msg, i) => (
                            <div
                                key={i}
                                className={cn(
                                    "flex",
                                    msg.role === "user" ? "justify-end" : "justify-start",
                                )}
                            >
                                <div
                                    className={cn(
                                        "max-w-[85%] rounded-lg px-3 py-2 text-sm",
                                        msg.role === "user"
                                            ? "bg-[oklch(0.55_0.23_264_/_15%)] text-foreground"
                                            : "bg-accent/50",
                                    )}
                                >
                                    {msg.role === "assistant" ? (
                                        <MarkdownContent content={msg.content} />
                                    ) : (
                                        <p className="whitespace-pre-wrap">{msg.content}</p>
                                    )}
                                </div>
                            </div>
                        ))}

                        {/* Streaming indicator */}
                        {isStreaming && streamingContent && (
                            <div className="flex justify-start">
                                <div className="max-w-[85%] rounded-lg px-3 py-2 text-sm bg-accent/50">
                                    <MarkdownContent content={streamingContent} />
                                    <span className="inline-block w-1.5 h-4 bg-foreground/60 animate-pulse ml-0.5" />
                                </div>
                            </div>
                        )}

                        {isStreaming && !streamingContent && (
                            <div className="flex justify-start">
                                <div className="max-w-[85%] rounded-lg px-3 py-2 text-sm bg-accent/50">
                                    <span className="flex items-center gap-1.5 text-muted-foreground">
                                        <span className="flex gap-1">
                                            <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce [animation-delay:0ms]" />
                                            <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce [animation-delay:150ms]" />
                                            <span className="w-1.5 h-1.5 rounded-full bg-current animate-bounce [animation-delay:300ms]" />
                                        </span>
                                        Thinking...
                                    </span>
                                </div>
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </>
                )}
            </CardContent>

            {/* Input Area */}
            <div className="border-t p-3 shrink-0">
                <form onSubmit={handleSubmit} className="flex gap-2">
                    <textarea
                        ref={inputRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask about your case..."
                        rows={1}
                        className="flex-1 resize-none rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={isStreaming}
                    />
                    {isStreaming ? (
                        <Button
                            type="button"
                            size="sm"
                            variant="destructive"
                            onClick={stopStreaming}
                            className="shrink-0"
                        >
                            Stop
                        </Button>
                    ) : (
                        <Button
                            type="submit"
                            size="sm"
                            disabled={!input.trim()}
                            className="shrink-0"
                        >
                            Send
                        </Button>
                    )}
                </form>
            </div>
        </Card>
    );
}

// ---- Suggested Prompts per Module ----------------------------------------

function suggestedPrompts(module: string): string[] {
    switch (module) {
        case "evidence":
        case "consistency":
            return [
                "What are the strongest evidence items?",
                "Are there any major contradictions?",
                "Which evidence might be inadmissible?",
            ];
        case "witnesses":
        case "cross-exam":
        case "direct-exam":
            return [
                "Summarize key witness credibility",
                "What are the biggest risks with our witnesses?",
                "Suggest cross-examination strategy",
            ];
        case "strategy":
            return [
                "What is the strongest defense theory?",
                "How should we respond to prosecution?",
                "What are the key motions to file?",
            ];
        case "investigation":
            return [
                "What tasks are highest priority?",
                "What evidence should we look for?",
                "Are there any gaps in our investigation?",
            ];
        case "research":
            return [
                "What are the key legal precedents?",
                "What statutes are most relevant?",
                "How does case law support our position?",
            ];
        default:
            return [
                "Summarize this case",
                "What are the key issues?",
                "What should I focus on next?",
            ];
    }
}
