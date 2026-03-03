// ---- Worker Status WebSocket Hook ---------------------------------------
// Connects to the backend WebSocket for real-time worker updates.
// Includes auto-reconnect logic and rich analysis progress fields.

"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";

const WS_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
    .replace("http://", "ws://")
    .replace("https://", "wss://");

export interface AnalysisWorkerStatus {
    status: string;
    progress?: number;
    current_module?: string;
    module_description?: string;
    error?: string;
    elapsed_seconds?: number;
    completed_modules?: string[];
    total_modules?: number;
    tokens_used?: number;
}

export interface WorkerStatus {
    analysis: AnalysisWorkerStatus;
    ingestion: { status: string; progress?: number; error?: string };
    ocr: { status: string; progress?: number; error?: string };
}

const IDLE_STATUS: WorkerStatus = {
    analysis: { status: "idle" },
    ingestion: { status: "idle" },
    ocr: { status: "idle" },
};

const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY_MS = 2000;

export function useWorkerStatus(caseId: string | null) {
    const { getToken } = useAuth();
    const [status, setStatus] = useState<WorkerStatus>(IDLE_STATUS);
    const [connected, setConnected] = useState(false);
    const [reconnectAttempts, setReconnectAttempts] = useState(0);
    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const intentionalCloseRef = useRef(false);

    const clearReconnectTimer = useCallback(() => {
        if (reconnectTimerRef.current) {
            clearTimeout(reconnectTimerRef.current);
            reconnectTimerRef.current = null;
        }
    }, []);

    const connect = useCallback(async () => {
        if (!caseId) return;

        // Close existing connection if any
        if (wsRef.current) {
            intentionalCloseRef.current = true;
            wsRef.current.close();
            wsRef.current = null;
        }

        const token = await getToken();
        if (!token) return;

        intentionalCloseRef.current = false;
        const ws = new WebSocket(`${WS_BASE}/api/v1/ws/workers/${caseId}?token=${token}`);
        wsRef.current = ws;

        ws.onopen = () => {
            setConnected(true);
            setReconnectAttempts(0);
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data._done) {
                intentionalCloseRef.current = true;
                ws.close();
                return;
            }
            setStatus(data as WorkerStatus);
        };

        ws.onclose = () => {
            setConnected(false);
            wsRef.current = null;

            // Auto-reconnect if the close was not intentional and we haven't
            // exceeded the max attempts. This keeps the progress stream alive
            // even if the connection drops mid-analysis.
            if (!intentionalCloseRef.current) {
                setReconnectAttempts((prev) => {
                    const next = prev + 1;
                    if (next <= MAX_RECONNECT_ATTEMPTS) {
                        clearReconnectTimer();
                        reconnectTimerRef.current = setTimeout(() => {
                            connect();
                        }, RECONNECT_DELAY_MS);
                    }
                    return next;
                });
            }
        };

        ws.onerror = () => {
            // onclose will fire after onerror, which handles reconnect
            setConnected(false);
        };
    }, [caseId, getToken, clearReconnectTimer]);

    const reconnect = useCallback(() => {
        setReconnectAttempts(0);
        clearReconnectTimer();
        connect();
    }, [connect, clearReconnectTimer]);

    useEffect(() => {
        connect();
        return () => {
            intentionalCloseRef.current = true;
            clearReconnectTimer();
            wsRef.current?.close();
        };
    }, [connect, clearReconnectTimer]);

    return { status, connected, reconnect, reconnectAttempts };
}
