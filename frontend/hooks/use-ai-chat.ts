// ---- AI Chat Hook (SSE Streaming) ----------------------------------------
// Connects to the streaming chat endpoint via fetch + ReadableStream.
// Returns messages, streaming state, and control functions.
"use client";

import { useState, useCallback, useRef } from "react";
import { useAuth } from "@clerk/nextjs";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ChatMessage {
    role: "user" | "assistant";
    content: string;
    timestamp?: string;
}

interface SSEEvent {
    type: "token" | "done" | "error";
    content: string;
}

export function useAiChat(caseId: string, prepId: string | null, contextModule: string = "general") {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [isStreaming, setIsStreaming] = useState(false);
    const [streamingContent, setStreamingContent] = useState("");
    const abortRef = useRef<AbortController | null>(null);

    // Load chat history on mount
    const historyQuery = useQuery({
        queryKey: ["chat-history", caseId, prepId],
        queryFn: async () => {
            const data = await api.get<{ messages: ChatMessage[] }>(
                `/cases/${caseId}/preparations/${prepId}/chat/history`,
                { getToken },
            );
            return data.messages ?? [];
        },
        enabled: !!prepId,
    });

    // Sync history into local state on first load
    const hasLoadedHistory = useRef(false);
    if (historyQuery.data && !hasLoadedHistory.current && messages.length === 0) {
        hasLoadedHistory.current = true;
        setMessages(historyQuery.data);
    }

    // Send a message and stream the response
    const sendMessage = useCallback(async (text: string) => {
        if (!prepId || isStreaming || !text.trim()) return;

        const userMsg: ChatMessage = {
            role: "user",
            content: text.trim(),
            timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, userMsg]);
        setIsStreaming(true);
        setStreamingContent("");

        const controller = new AbortController();
        abortRef.current = controller;

        try {
            const token = await getToken();
            const url = `${API_BASE}/api/v1/cases/${caseId}/preparations/${prepId}/chat`;

            const response = await fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
                body: JSON.stringify({
                    message: text.trim(),
                    context_module: contextModule,
                    history: messages.slice(-20).map((m) => ({
                        role: m.role,
                        content: m.content,
                    })),
                }),
                signal: controller.signal,
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const reader = response.body?.getReader();
            if (!reader) throw new Error("No response body");

            const decoder = new TextDecoder();
            let buffer = "";
            let fullContent = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Parse SSE events from buffer
                const lines = buffer.split("\n");
                buffer = lines.pop() || ""; // Keep incomplete line

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const event: SSEEvent = JSON.parse(line.slice(6));
                            if (event.type === "token") {
                                fullContent += event.content;
                                setStreamingContent(fullContent);
                            } else if (event.type === "done") {
                                fullContent = event.content;
                                setStreamingContent("");
                                setMessages((prev) => [
                                    ...prev,
                                    {
                                        role: "assistant",
                                        content: fullContent,
                                        timestamp: new Date().toISOString(),
                                    },
                                ]);
                            } else if (event.type === "error") {
                                setStreamingContent("");
                                setMessages((prev) => [
                                    ...prev,
                                    {
                                        role: "assistant",
                                        content: `Error: ${event.content}`,
                                        timestamp: new Date().toISOString(),
                                    },
                                ]);
                            }
                        } catch {
                            // Skip malformed JSON
                        }
                    }
                }
            }

            // If we got tokens but no "done" event, finalize
            if (fullContent && streamingContent) {
                setStreamingContent("");
                setMessages((prev) => {
                    const last = prev[prev.length - 1];
                    if (last?.role !== "assistant") {
                        return [...prev, { role: "assistant", content: fullContent }];
                    }
                    return prev;
                });
            }
        } catch (err) {
            if ((err as Error).name !== "AbortError") {
                setMessages((prev) => [
                    ...prev,
                    {
                        role: "assistant",
                        content: "Sorry, an error occurred. Please try again.",
                        timestamp: new Date().toISOString(),
                    },
                ]);
            }
        } finally {
            setIsStreaming(false);
            setStreamingContent("");
            abortRef.current = null;
        }
    }, [prepId, isStreaming, caseId, contextModule, getToken, messages, streamingContent]);

    // Stop streaming
    const stopStreaming = useCallback(() => {
        abortRef.current?.abort();
    }, []);

    // Clear history
    const clearHistory = useCallback(async () => {
        if (!prepId) return;
        try {
            await api.delete(`/cases/${caseId}/preparations/${prepId}/chat/history`, { getToken });
            setMessages([]);
            hasLoadedHistory.current = false;
            queryClient.invalidateQueries({ queryKey: ["chat-history", caseId, prepId] });
        } catch {
            // Silently fail
        }
    }, [caseId, prepId, getToken, queryClient]);

    return {
        messages,
        isStreaming,
        streamingContent,
        sendMessage,
        stopStreaming,
        clearHistory,
        isLoadingHistory: historyQuery.isLoading,
    };
}
