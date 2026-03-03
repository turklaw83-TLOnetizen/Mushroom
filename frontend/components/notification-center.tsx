"use client";

import { useState, useEffect } from "react";

interface Notification {
    id: string;
    type: "info" | "warning" | "success" | "error";
    title: string;
    message: string;
    timestamp: Date;
    read: boolean;
}

const ICONS: Record<string, string> = { info: "ℹ️", warning: "⚠️", success: "✅", error: "❌" };

export function NotificationCenter() {
    const [open, setOpen] = useState(false);
    const [notifications, setNotifications] = useState<Notification[]>([
        { id: "1", type: "warning", title: "SOL Deadline Approaching", message: "Smith v. Johnson — statute of limitations expires in 14 days", timestamp: new Date(), read: false },
        { id: "2", type: "info", title: "New Document Uploaded", message: "Medical records uploaded to Case #2024-0042", timestamp: new Date(Date.now() - 3600000), read: false },
        { id: "3", type: "success", title: "Analysis Complete", message: "AI analysis finished for Davis v. Metro Transit", timestamp: new Date(Date.now() - 7200000), read: true },
    ]);

    const unreadCount = notifications.filter((n) => !n.read).length;
    const markAllRead = () => setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    const dismiss = (id: string) => setNotifications((prev) => prev.filter((n) => n.id !== id));
    const timeAgo = (date: Date): string => {
        const s = Math.floor((Date.now() - date.getTime()) / 1000);
        if (s < 60) return "just now";
        if (s < 3600) return `${Math.floor(s / 60)}m ago`;
        if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
        return `${Math.floor(s / 86400)}d ago`;
    };

    useEffect(() => {
        // Only connect WebSocket if explicitly configured
        const wsUrl = process.env.NEXT_PUBLIC_WS_URL;
        if (!wsUrl) return;

        let ws: WebSocket | null = null;
        let retryTimeout: NodeJS.Timeout;

        function connect() {
            try {
                ws = new WebSocket(wsUrl!);
                ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.type === "notification") {
                            setNotifications((prev) => [{ id: Date.now().toString(), type: data.severity || "info", title: data.title, message: data.message, timestamp: new Date(), read: false }, ...prev]);
                        }
                    } catch {}
                };
                ws.onclose = () => {
                    // Backoff retry — don't spam reconnect
                    retryTimeout = setTimeout(connect, 30000);
                };
                ws.onerror = () => ws?.close();
            } catch {}
        }

        connect();
        return () => { ws?.close(); clearTimeout(retryTimeout); };
    }, []);

    return (
        <div className="relative">
            <button onClick={() => setOpen(!open)} className="relative rounded-lg p-2 text-white/60 hover:bg-white/10 hover:text-white transition-colors">
                🔔
                {unreadCount > 0 && <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">{unreadCount}</span>}
            </button>
            {open && (
                <div className="absolute right-0 top-full mt-2 w-80 rounded-xl border border-white/10 bg-gray-900 shadow-2xl z-50 overflow-hidden">
                    <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                        <h3 className="font-semibold text-white text-sm">Notifications</h3>
                        {unreadCount > 0 && <button onClick={markAllRead} className="text-xs text-indigo-400 hover:text-indigo-300">Mark all read</button>}
                    </div>
                    <div className="max-h-80 overflow-y-auto">
                        {notifications.length === 0 ? (
                            <div className="px-4 py-8 text-center text-white/40 text-sm">No notifications</div>
                        ) : notifications.map((n) => (
                            <div key={n.id} className={`flex items-start gap-3 px-4 py-3 border-b border-white/5 ${n.read ? "opacity-60" : "bg-white/[0.02]"}`}>
                                <span className="text-base mt-0.5">{ICONS[n.type]}</span>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center justify-between gap-2">
                                        <p className="text-sm font-medium text-white truncate">{n.title}</p>
                                        <button onClick={() => dismiss(n.id)} className="text-white/20 hover:text-white/60 text-xs flex-shrink-0">✕</button>
                                    </div>
                                    <p className="text-xs text-white/50 mt-0.5 line-clamp-2">{n.message}</p>
                                    <p className="text-xs text-white/30 mt-1">{timeAgo(n.timestamp)}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
