// ---- Mock Exam WebSocket Hook --------------------------------------------
// Bidirectional WebSocket for interactive mock examination sessions.

"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";

const WS_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
    .replace("http://", "ws://")
    .replace("https://", "wss://");

export interface MockExamMessage {
    id: string;
    role: "system" | "attorney" | "witness" | "objection";
    content: string;
    timestamp: string;
    metadata?: Record<string, unknown>;
}

export interface CoachingNote {
    message_id: string;
    type: "technique_tip" | "objection_warning" | "impeachment_opportunity" | "door_opened";
    content: string;
    severity: "info" | "warning" | "critical";
}

export interface Ruling {
    ruling: "sustained" | "overruled";
    explanation: string;
}

export function useMockExam(
    caseId: string,
    prepId: string,
    sessionId: string | null,
) {
    const { getToken } = useAuth();
    const [messages, setMessages] = useState<MockExamMessage[]>([]);
    const [coachingNotes, setCoachingNotes] = useState<CoachingNote[]>([]);
    const [isWitnessTyping, setIsWitnessTyping] = useState(false);
    const [streamingText, setStreamingText] = useState("");
    const [connected, setConnected] = useState(false);
    const [lastRuling, setLastRuling] = useState<Ruling | null>(null);
    const wsRef = useRef<WebSocket | null>(null);

    const connect = useCallback(async () => {
        if (!sessionId || !caseId || !prepId) return;
        const token = await getToken();
        if (!token) return;

        const url = `${WS_BASE}/api/v1/ws/mock-exam/${caseId}/${prepId}/${sessionId}?token=${token}`;
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => setConnected(true);

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            switch (data.type) {
                case "session_loaded":
                    // Hydrate from persisted messages
                    setMessages(data.messages || []);
                    setCoachingNotes(data.coaching_notes || []);
                    break;

                case "witness_start":
                    setIsWitnessTyping(true);
                    setStreamingText("");
                    setLastRuling(null);
                    break;

                case "witness_token":
                    setStreamingText((prev) => prev + data.token);
                    break;

                case "witness_done":
                    setIsWitnessTyping(false);
                    setStreamingText("");
                    if (data.message) {
                        setMessages((prev) => [...prev, data.message]);
                    }
                    break;

                case "objection":
                    if (data.message) {
                        setMessages((prev) => [...prev, data.message]);
                    }
                    break;

                case "ruling":
                    setLastRuling({
                        ruling: data.ruling,
                        explanation: data.explanation || "",
                    });
                    break;

                case "coaching":
                    if (data.coaching) {
                        setCoachingNotes((prev) => [...prev, data.coaching]);
                    }
                    break;

                case "error":
                    setIsWitnessTyping(false);
                    setStreamingText("");
                    break;
            }
        };

        ws.onclose = () => {
            setConnected(false);
            wsRef.current = null;
        };

        ws.onerror = () => {
            setConnected(false);
        };
    }, [caseId, prepId, sessionId, getToken]);

    useEffect(() => {
        connect();
        return () => {
            wsRef.current?.close();
        };
    }, [connect]);

    const sendQuestion = useCallback(
        (content: string) => {
            if (wsRef.current?.readyState === WebSocket.OPEN && content.trim()) {
                // Optimistically add attorney message
                const msg: MockExamMessage = {
                    id: `msg_${Date.now().toString(36)}`,
                    role: "attorney",
                    content: content.trim(),
                    timestamp: new Date().toISOString(),
                };
                setMessages((prev) => [...prev, msg]);
                setLastRuling(null);
                wsRef.current.send(JSON.stringify({ content: content.trim() }));
            }
        },
        [],
    );

    return {
        messages,
        coachingNotes,
        isWitnessTyping,
        streamingText,
        connected,
        lastRuling,
        sendQuestion,
        reconnect: connect,
    };
}
