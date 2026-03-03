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
import { Badge } from "@/components/ui/badge";

// ---- Co-Counsel Personas ------------------------------------------------

type Persona = {
    id: string;
    label: string;
    description: string;
};

const PERSONAS: Persona[] = [
    { id: "general", label: "General Assistant", description: "Balanced, all-purpose" },
    { id: "strategist", label: "The Strategist", description: "Trial strategy & case theory" },
    { id: "bulldog", label: "The Bulldog", description: "Aggressive cross-exam & weaknesses" },
    { id: "scholar", label: "The Scholar", description: "Academic legal research" },
    { id: "judge", label: "The Judge", description: "Evaluates from the bench" },
];

// ---- File item shape from /cases/:id/files ------------------------------

interface FileItem {
    filename: string;
    size: number;
    tags: string[];
    uploaded_at?: string;
    ocr_status?: string;
}

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

    // Co-Counsel persona selection
    const [selectedPersona, setSelectedPersona] = useState<string>("general");

    // Document Focus Mode
    const [focusDocIds, setFocusDocIds] = useState<string[]>([]);
    const [docPanelOpen, setDocPanelOpen] = useState(false);

    // Fetch file list for document focus
    const { data: files } = useQuery({
        queryKey: ["cases", caseId, "files"],
        queryFn: () => api.get<FileItem[]>(`/cases/${caseId}/files`, { getToken }),
        enabled: !!caseId,
    });

    const toggleDocFocus = (filename: string) => {
        setFocusDocIds((prev) =>
            prev.includes(filename)
                ? prev.filter((f) => f !== filename)
                : [...prev, filename],
        );
    };

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
                {
                    message: text,
                    prep_id: activePrepId,
                    persona: selectedPersona,
                    ...(focusDocIds.length > 0 && { document_ids: focusDocIds }),
                },
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

            {/* Controls area */}
            {canEdit && (
                <div className="pt-3 border-t border-border mt-3 space-y-3">
                    {/* Document Focus Mode */}
                    <div>
                        <button
                            type="button"
                            onClick={() => setDocPanelOpen((v) => !v)}
                            className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                        >
                            <span className="inline-block transition-transform duration-200" style={{ transform: docPanelOpen ? "rotate(90deg)" : "rotate(0deg)" }}>
                                &#9654;
                            </span>
                            Focus Documents
                            {!docPanelOpen && focusDocIds.length > 0 && (
                                <Badge variant="secondary" className="ml-1">
                                    {focusDocIds.length} doc{focusDocIds.length !== 1 ? "s" : ""} focused
                                </Badge>
                            )}
                        </button>

                        {docPanelOpen && (
                            <Card className="mt-2">
                                <CardContent className="py-2 px-3 max-h-40 overflow-y-auto">
                                    {!files || files.length === 0 ? (
                                        <p className="text-xs text-muted-foreground py-1">
                                            No files uploaded to this case.
                                        </p>
                                    ) : (
                                        <div className="space-y-1">
                                            {files.map((file) => (
                                                <label
                                                    key={file.filename}
                                                    className="flex items-center gap-2 text-sm cursor-pointer hover:bg-muted/50 rounded px-1 py-0.5"
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={focusDocIds.includes(file.filename)}
                                                        onChange={() => toggleDocFocus(file.filename)}
                                                        className="accent-primary h-3.5 w-3.5 rounded"
                                                    />
                                                    <span className="truncate flex-1">{file.filename}</span>
                                                </label>
                                            ))}
                                        </div>
                                    )}
                                    {focusDocIds.length > 0 && (
                                        <button
                                            type="button"
                                            onClick={() => setFocusDocIds([])}
                                            className="text-xs text-muted-foreground hover:text-foreground mt-1"
                                        >
                                            Clear selection
                                        </button>
                                    )}
                                </CardContent>
                            </Card>
                        )}
                    </div>

                    {/* Co-Counsel Persona Selector */}
                    <div className="flex flex-wrap gap-1.5">
                        {PERSONAS.map((p) => (
                            <Button
                                key={p.id}
                                variant={selectedPersona === p.id ? "default" : "outline"}
                                size="sm"
                                onClick={() => setSelectedPersona(p.id)}
                                title={p.description}
                                className="text-xs h-7 px-2.5"
                            >
                                {p.label}
                            </Button>
                        ))}
                    </div>

                    {/* Input row */}
                    <div className="flex items-center gap-2">
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
                </div>
            )}
        </div>
    );
}
