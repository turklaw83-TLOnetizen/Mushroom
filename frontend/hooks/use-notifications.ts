// ---- useNotifications Hook -----------------------------------------------
// Full notification center hook — fetches from REST API + real-time via WS.
"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { toast } from "sonner";

export interface Notification {
    id: string;
    type: string;
    title: string;
    message: string;
    severity: "info" | "warning" | "success" | "error";
    read: boolean;
    created_at: string;
    case_id?: string;
    link?: string;
}

interface UseNotificationsOptions {
    enabled?: boolean;
    pollInterval?: number;
}

export function useNotifications(options: UseNotificationsOptions = {}) {
    const { enabled = true, pollInterval = 30000 } = options;
    const { getToken } = useAuth();
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [unreadCount, setUnreadCount] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const wsRef = useRef<WebSocket | null>(null);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // Fetch notifications from REST API
    const fetchNotifications = useCallback(async () => {
        try {
            const data = await api.get<{ notifications: Notification[]; unread_count: number }>(
                "/notifications",
                { getToken },
            );
            setNotifications(data.notifications || []);
            setUnreadCount(data.unread_count || 0);
        } catch {
            // Fallback: use empty list on error
        } finally {
            setIsLoading(false);
        }
    }, [getToken]);

    // Mark single as read
    const markRead = useCallback(async (id: string) => {
        try {
            await api.patch(`/notifications/${id}/read`, {}, { getToken });
            setNotifications((prev) =>
                prev.map((n) => (n.id === id ? { ...n, read: true } : n)),
            );
            setUnreadCount((c) => Math.max(0, c - 1));
        } catch {
            // silent
        }
    }, [getToken]);

    // Mark all as read
    const markAllRead = useCallback(async () => {
        try {
            await api.post("/notifications/mark-all-read", {}, { getToken });
            setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
            setUnreadCount(0);
        } catch {
            // silent
        }
    }, [getToken]);

    // Dismiss
    const dismiss = useCallback(async (id: string) => {
        try {
            await api.delete(`/notifications/${id}`, { getToken });
            setNotifications((prev) => prev.filter((n) => n.id !== id));
            setUnreadCount((c) => Math.max(0, c - 1));
        } catch {
            // silent
        }
    }, [getToken]);

    // WebSocket for real-time push
    useEffect(() => {
        if (!enabled) return;

        const connectWs = async () => {
            try {
                const token = await getToken();
                if (!token) return;

                const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
                const wsUrl = API_BASE.replace(/^http/, "ws");
                const ws = new WebSocket(`${wsUrl}/ws/notifications?token=${token}`);
                wsRef.current = ws;

                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.type === "notification") {
                            const newNotif: Notification = {
                                id: data.id || Date.now().toString(),
                                type: data.notification_type || "system",
                                title: data.title || "New Notification",
                                message: data.message || "",
                                severity: data.severity || "info",
                                read: false,
                                created_at: new Date().toISOString(),
                                case_id: data.case_id,
                                link: data.link,
                            };
                            setNotifications((prev) => [newNotif, ...prev]);
                            setUnreadCount((c) => c + 1);

                            // Toast for real-time notifications
                            if (data.severity === "error") {
                                toast.error(data.title || data.message);
                            } else if (data.severity === "warning") {
                                toast.warning(data.title || data.message);
                            } else if (data.severity === "success") {
                                toast.success(data.title || data.message);
                            } else {
                                toast.info(data.title || data.message);
                            }
                        }
                    } catch {
                        // ignore parse errors
                    }
                };

                ws.onclose = () => {
                    wsRef.current = null;
                };
            } catch {
                // silent
            }
        };

        connectWs();

        return () => {
            wsRef.current?.close();
            wsRef.current = null;
        };
    }, [enabled, getToken]);

    // Initial fetch + polling
    useEffect(() => {
        if (!enabled) return;
        fetchNotifications();
        pollRef.current = setInterval(fetchNotifications, pollInterval);
        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
        };
    }, [enabled, fetchNotifications, pollInterval]);

    return {
        notifications,
        unreadCount,
        isLoading,
        markRead,
        markAllRead,
        dismiss,
        refresh: fetchNotifications,
    };
}
