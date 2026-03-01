// ---- Strategy Chat Tab (SSE streaming) ----------------------------------
"use client";

import { useState, useRef, useEffect } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import type { ChatMessage } from "@/types/api";
import { usePrep } from "@/hooks/use-prep";
import { useRole } from "@/hooks/use-role";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

export default function ChatPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, isLoading: prepLoading } = usePrep();
    const { canEdit } = useRole();
    const queryClient = useQueryClient();

    const [input, setInput] = useState("");
    const [isStreaming, setIsStreaming] = useState(false);
    const [streamingContent, setStreamingContent] = useState("");
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Load chat history
    const { data, isLoading } = useQuery({
        queryKey: ["chat", caseId, activePrepId],
        queryFn: () =>
            api.get<ChatMessage[]>(
                `/cases/${caseId}/chat/history`,
                { params: { prep_id: activePrepId! }, getToken },
            ),
        enabled: !!activePrepId,
    });

    const messages = data ?? [];

    // Auto-scroll to bottom when messages change or streaming content updates
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, streamingContent]);

    const handleSend = async () => {
        const text = input.trim();
        if (!text || !activePrepId || isStreaming) return;

        setInput("");
        setIsStreaming(true);
        setStreamingContent("");

        // Optimistically add user message
        queryClient.setQueryData<ChatMessage[]>(
            ["chat", caseId, activePrepId],
            (prev) => [...(prev ?? []), { role: "user", content: text }],
        );

        try {
            const response = await api.stream(
                `/cases/${caseId}/chat/stream`,
                { message: text, prep_id: activePrepId },
                { getToken },
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const reader = response.body?.getReader();
            if (!reader) throw new Error("No response stream");

            const decoder = new TextDecoder();
            let accumulated = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split("\n");

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        const payload = line.slice(6).trim();
                        if (payload === "[DONE]") continue;
                        try {
                            const parsed = JSON.parse(payload);
                            if (parsed.content) {
                                accumulated += parsed.content;
                                setStreamingContent(accumulated);
                            }
                        } catch {
                            // Non-JSON SSE line, skip
                        }
                    }
                }
            }

            // Finalize: add assistant message to cache
            queryClient.setQueryData<ChatMessage[]>(
                ["chat", caseId, activePrepId],
                (prev) => [
                    ...(prev ?? []),
                    { role: "assistant", content: accumulated },
                ],
            );
        } catch (err) {
            toast.error("Chat failed", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        } finally {
            setIsStreaming(false);
            setStreamingContent("");
            inputRef.current?.focus();
        }
    };

    const handleClearHistory = async () => {
        try {
            await api.delete(`/cases/${caseId}/chat/history`, {
                params: { prep_id: activePrepId! },
                getToken,
            });
            queryClient.setQueryData(["chat", caseId, activePrepId], []);
            toast.success("Chat history cleared");
        } catch (err) {
            toast.error("Failed to clear", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">
                    Create a preparation first to use strategy chat.
                </p>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-[calc(100vh-12rem)]">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">
                        Strategy Chat
                    </h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        AI-powered case strategy discussion
                    </p>
                </div>
                {messages.length > 0 && canEdit && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleClearHistory}
                        disabled={isStreaming}
                    >
                        Clear History
                    </Button>
                )}
            </div>

            {/* Messages area */}
            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
                {isLoading ? (
                    <div className="space-y-3">
                        {Array.from({ length: 4 }).map((_, i) => (
                            <Skeleton key={i} className="h-16 w-full rounded-lg" />
                        ))}
                    </div>
                ) : messages.length === 0 && !isStreaming ? (
                    <Card className="border-dashed">
                        <CardContent className="py-12 text-center text-muted-foreground">
                            No messages yet. Start a conversation about your
                            case strategy.
                        </CardContent>
                    </Card>
                ) : (
                    <>
                        {messages.map((msg, i) => (
                            <div
                                key={i}
                                className={`flex ${
                                    msg.role === "user"
                                        ? "justify-end"
                                        : "justify-start"
                                }`}
                            >
                                <Card
                                    className={`max-w-[80%] ${
                                        msg.role === "user"
                                            ? "bg-primary text-primary-foreground"
                                            : "bg-muted"
                                    }`}
                                >
                                    <CardContent className="py-2.5 px-3.5">
                                        <p className="text-xs font-medium mb-1 opacity-70">
                                            {msg.role === "user"
                                                ? "You"
                                                : "Assistant"}
                                        </p>
                                        <p className="text-sm whitespace-pre-wrap">
                                            {msg.content}
                                        </p>
                                    </CardContent>
                                </Card>
                            </div>
                        ))}

                        {/* Streaming message */}
                        {isStreaming && streamingContent && (
                            <div className="flex justify-start">
                                <Card className="max-w-[80%] bg-muted">
                                    <CardContent className="py-2.5 px-3.5">
                                        <p className="text-xs font-medium mb-1 opacity-70">
                                            Assistant
                                        </p>
                                        <p className="text-sm whitespace-pre-wrap">
                                            {streamingContent}
                                            <span className="inline-block w-2 h-4 bg-foreground/50 animate-pulse ml-0.5" />
                                        </p>
                                    </CardContent>
                                </Card>
                            </div>
                        )}

                        {/* Streaming indicator before first content */}
                        {isStreaming && !streamingContent && (
                            <div className="flex justify-start">
                                <Card className="max-w-[80%] bg-muted">
                                    <CardContent className="py-2.5 px-3.5">
                                        <p className="text-xs font-medium mb-1 opacity-70">
                                            Assistant
                                        </p>
                                        <div className="flex items-center gap-1.5">
                                            <div className="w-2 h-2 rounded-full bg-foreground/40 animate-bounce [animation-delay:0ms]" />
                                            <div className="w-2 h-2 rounded-full bg-foreground/40 animate-bounce [animation-delay:150ms]" />
                                            <div className="w-2 h-2 rounded-full bg-foreground/40 animate-bounce [animation-delay:300ms]" />
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        )}
                    </>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            {canEdit && (
                <div className="flex items-center gap-2 pt-3 border-t border-border mt-3">
                    <Input
                        ref={inputRef}
                        placeholder="Ask about case strategy..."
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={isStreaming || !activePrepId}
                        className="flex-1"
                    />
                    <Button
                        onClick={handleSend}
                        disabled={!input.trim() || isStreaming || !activePrepId}
                        size="sm"
                    >
                        {isStreaming ? "Sending..." : "Send"}
                    </Button>
                </div>
            )}
        </div>
    );
}
