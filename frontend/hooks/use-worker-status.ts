// ---- Worker Status WebSocket Hook ---------------------------------------
// Connects to the backend WebSocket for real-time worker updates.
// Auto-reconnects on close with exponential backoff.

"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";

// Extract just the origin (no path) to avoid double-prefix when
// NEXT_PUBLIC_API_URL includes a path like "https://example.com/api".
const WS_ORIGIN = (() => {
    try {
        return new URL(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").origin;
    } catch {
        return "http://localhost:8000";
    }
})();
const WS_BASE = WS_ORIGIN.replace("http://", "ws://").replace("https://", "wss://");

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
    const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const backoffRef = useRef(1000); // Start at 1s, max 10s
    const unmountedRef = useRef(false);

    const connect = useCallback(async () => {
        if (!caseId || unmountedRef.current) return;

        // Close any existing connection
        if (wsRef.current) {
            wsRef.current.onclose = null; // Prevent reconnect loop
            wsRef.current.close();
            wsRef.current = null;
        }

        const token = await getToken();
        if (!token || unmountedRef.current) return;

        const ws = new WebSocket(`${WS_BASE}/api/v1/ws/workers/${caseId}?token=${token}`);
        wsRef.current = ws;

        ws.onopen = () => {
            setConnected(true);
            backoffRef.current = 1000; // Reset backoff on successful connect
        };
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data._done) {
                    // Server lifetime expired — reconnect
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
            // Auto-reconnect with backoff (unless component unmounted)
            if (!unmountedRef.current) {
                reconnectTimer.current = setTimeout(() => {
                    connect();
                }, backoffRef.current);
                backoffRef.current = Math.min(backoffRef.current * 1.5, 10000);
            }
        };
        ws.onerror = () => {
            // onclose will fire after onerror, triggering reconnect
            setConnected(false);
        };
    }, [caseId, getToken]);

    useEffect(() => {
        unmountedRef.current = false;
        connect();
        return () => {
            unmountedRef.current = true;
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
            if (wsRef.current) {
                wsRef.current.onclose = null; // Prevent reconnect on cleanup
                wsRef.current.close();
            }
        };
    }, [connect]);

    return { status, connected, reconnect: connect };
}
