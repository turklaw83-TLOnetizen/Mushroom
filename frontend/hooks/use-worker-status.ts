// ---- Worker Status WebSocket Hook ---------------------------------------
// Connects to the backend WebSocket for real-time worker updates.

"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";

const WS_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
    .replace("http://", "ws://")
    .replace("https://", "wss://");

export interface WorkerStatus {
    analysis: { status: string; progress?: number; current_module?: string; error?: string };
    ingestion: { status: string; progress?: number; error?: string };
    ocr: { status: string; progress?: number; error?: string };
}

const IDLE_STATUS: WorkerStatus = {
    analysis: { status: "idle" },
    ingestion: { status: "idle" },
    ocr: { status: "idle" },
};

export function useWorkerStatus(caseId: string | null) {
    const { getToken } = useAuth();
    const [status, setStatus] = useState<WorkerStatus>(IDLE_STATUS);
    const [connected, setConnected] = useState(false);
    const wsRef = useRef<WebSocket | null>(null);

    const connect = useCallback(async () => {
        if (!caseId) return;
        const token = await getToken();
        if (!token) return;

        const ws = new WebSocket(`${WS_BASE}/api/v1/ws/workers/${caseId}?token=${token}`);
        wsRef.current = ws;

        ws.onopen = () => setConnected(true);
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data._done) {
                    ws.close();
                    return;
                }
                setStatus(data as WorkerStatus);
            } catch {
                // Skip malformed JSON messages
            }
        };
        ws.onclose = () => {
            setConnected(false);
            wsRef.current = null;
        };
        ws.onerror = () => {
            setConnected(false);
        };
    }, [caseId, getToken]);

    useEffect(() => {
        connect();
        return () => {
            wsRef.current?.close();
        };
    }, [connect]);

    return { status, connected, reconnect: connect };
}
