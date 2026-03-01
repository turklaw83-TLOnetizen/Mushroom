// ---- useNotifications Hook -----------------------------------------------
// Real-time notification integration via WebSocket status updates.
// Converts worker status changes into toast notifications.
"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { toast } from "sonner";

interface NotificationEvent {
    type: "analysis" | "ingestion" | "ocr";
    status: "complete" | "error" | "running";
    message: string;
    timestamp: number;
}

interface UseNotificationsOptions {
    /** Case ID to listen for */
    caseId: string;
    /** Auth token for WebSocket */
    token: string | null;
    /** Whether notifications are enabled */
    enabled?: boolean;
}

/**
 * Listens for WebSocket worker status updates and converts them
 * into toast notifications when workers complete or error.
 *
 * Uses the existing /ws/workers/{caseId} endpoint.
 */
export function useNotifications(options: UseNotificationsOptions) {
    const { caseId, token, enabled = true } = options;
    const [events, setEvents] = useState<NotificationEvent[]>([]);
    const wsRef = useRef<WebSocket | null>(null);
    const prevStatusRef = useRef<Record<string, string>>({});

    const connect = useCallback(() => {
        if (!caseId || !token || !enabled) return;

        const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const wsUrl = API_BASE.replace(/^http/, "ws");
        const ws = new WebSocket(`${wsUrl}/api/v1/ws/workers/${caseId}?token=${token}`);
        wsRef.current = ws;

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data._done) return;

                // Check each worker for status transitions
                for (const [worker, status] of Object.entries(data)) {
                    const s = (status as Record<string, string>)?.status;
                    const prev = prevStatusRef.current[worker];

                    if (prev && prev !== s) {
                        // Status changed — notify
                        if (s === "complete") {
                            const msg = `${worker.charAt(0).toUpperCase() + worker.slice(1)} completed`;
                            toast.success(msg);
                            setEvents((e) => [...e, {
                                type: worker as NotificationEvent["type"],
                                status: "complete",
                                message: msg,
                                timestamp: Date.now(),
                            }]);
                        } else if (s === "error") {
                            const msg = `${worker.charAt(0).toUpperCase() + worker.slice(1)} failed`;
                            toast.error(msg);
                            setEvents((e) => [...e, {
                                type: worker as NotificationEvent["type"],
                                status: "error",
                                message: msg,
                                timestamp: Date.now(),
                            }]);
                        } else if (s === "running" && prev !== "running") {
                            toast.info(`${worker.charAt(0).toUpperCase() + worker.slice(1)} started...`);
                        }
                    }

                    prevStatusRef.current[worker] = s;
                }
            } catch {
                // Ignore parse errors
            }
        };

        ws.onerror = () => {
            // Silent — useWorkerStatus handles reconnection
        };

        ws.onclose = () => {
            wsRef.current = null;
        };
    }, [caseId, token, enabled]);

    useEffect(() => {
        connect();
        return () => {
            wsRef.current?.close();
            wsRef.current = null;
        };
    }, [connect]);

    return { events };
}
