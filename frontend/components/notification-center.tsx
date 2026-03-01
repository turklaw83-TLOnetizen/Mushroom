"use client";

import { useState, useRef, useEffect } from "react";
import { useNotifications, type Notification } from "@/hooks/use-notifications";
import Link from "next/link";

const SEVERITY_STYLES: Record<string, { icon: string; bg: string }> = {
    info: { icon: "info-circle", bg: "bg-blue-500/10 text-blue-400" },
    warning: { icon: "alert-triangle", bg: "bg-amber-500/10 text-amber-400" },
    success: { icon: "check-circle", bg: "bg-emerald-500/10 text-emerald-400" },
    error: { icon: "x-circle", bg: "bg-red-500/10 text-red-400" },
};

const SEVERITY_ICONS: Record<string, string> = {
    info: "\u2139\uFE0F",
    warning: "\u26A0\uFE0F",
    success: "\u2705",
    error: "\u274C",
};

function timeAgo(dateStr: string): string {
    try {
        const s = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
        if (s < 60) return "just now";
        if (s < 3600) return `${Math.floor(s / 60)}m ago`;
        if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
        return `${Math.floor(s / 86400)}d ago`;
    } catch {
        return "";
    }
}

function NotificationItem({
    notification,
    onRead,
    onDismiss,
}: {
    notification: Notification;
    onRead: (id: string) => void;
    onDismiss: (id: string) => void;
}) {
    const severity = SEVERITY_STYLES[notification.severity] || SEVERITY_STYLES.info;

    const content = (
        <div
            className={`flex items-start gap-3 px-4 py-3 border-b border-white/5 transition-colors hover:bg-white/[0.03] ${
                notification.read ? "opacity-50" : ""
            }`}
            onClick={() => !notification.read && onRead(notification.id)}
        >
            <span className={`text-lg mt-0.5 shrink-0 w-6 h-6 flex items-center justify-center rounded-full ${severity.bg}`}>
                {SEVERITY_ICONS[notification.severity] || SEVERITY_ICONS.info}
            </span>
            <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium text-white truncate">
                        {notification.title}
                    </p>
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            onDismiss(notification.id);
                        }}
                        className="text-white/20 hover:text-white/60 text-xs flex-shrink-0"
                    >
                        x
                    </button>
                </div>
                <p className="text-xs text-white/50 mt-0.5 line-clamp-2">
                    {notification.message}
                </p>
                <p className="text-xs text-white/30 mt-1">
                    {timeAgo(notification.created_at)}
                </p>
            </div>
            {!notification.read && (
                <div className="w-2 h-2 rounded-full bg-indigo-400 mt-2 shrink-0" />
            )}
        </div>
    );

    if (notification.link) {
        return <Link href={notification.link}>{content}</Link>;
    }
    return content;
}

export function NotificationCenter() {
    const [open, setOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);
    const {
        notifications,
        unreadCount,
        isLoading,
        markRead,
        markAllRead,
        dismiss,
    } = useNotifications();

    // Close on outside click
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setOpen(false);
            }
        }
        if (open) {
            document.addEventListener("mousedown", handleClickOutside);
            return () => document.removeEventListener("mousedown", handleClickOutside);
        }
    }, [open]);

    return (
        <div className="relative" ref={dropdownRef}>
            <button
                onClick={() => setOpen(!open)}
                className="relative rounded-lg p-2 text-white/60 hover:bg-white/10 hover:text-white transition-colors"
                aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
            >
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                >
                    <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
                    <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
                </svg>
                {unreadCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white animate-pulse">
                        {unreadCount > 9 ? "9+" : unreadCount}
                    </span>
                )}
            </button>

            {open && (
                <div className="absolute right-0 top-full mt-2 w-96 rounded-xl border border-white/10 bg-gray-900 shadow-2xl z-50 overflow-hidden">
                    {/* Header */}
                    <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                        <h3 className="font-semibold text-white text-sm">
                            Notifications
                            {unreadCount > 0 && (
                                <span className="ml-2 text-xs text-white/40">
                                    ({unreadCount} unread)
                                </span>
                            )}
                        </h3>
                        {unreadCount > 0 && (
                            <button
                                onClick={markAllRead}
                                className="text-xs text-indigo-400 hover:text-indigo-300"
                            >
                                Mark all read
                            </button>
                        )}
                    </div>

                    {/* Content */}
                    <div className="max-h-96 overflow-y-auto">
                        {isLoading ? (
                            <div className="px-4 py-8 text-center">
                                <div className="animate-spin h-5 w-5 border-2 border-white/20 border-t-white/60 rounded-full mx-auto" />
                                <p className="text-xs text-white/40 mt-2">Loading...</p>
                            </div>
                        ) : notifications.length === 0 ? (
                            <div className="px-4 py-12 text-center">
                                <svg
                                    className="mx-auto h-8 w-8 text-white/20 mb-2"
                                    xmlns="http://www.w3.org/2000/svg"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="1.5"
                                >
                                    <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
                                    <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
                                </svg>
                                <p className="text-sm text-white/40">No notifications</p>
                                <p className="text-xs text-white/25 mt-1">
                                    You&apos;re all caught up
                                </p>
                            </div>
                        ) : (
                            notifications.map((n) => (
                                <NotificationItem
                                    key={n.id}
                                    notification={n}
                                    onRead={markRead}
                                    onDismiss={dismiss}
                                />
                            ))
                        )}
                    </div>

                    {/* Footer */}
                    {notifications.length > 0 && (
                        <div className="border-t border-white/10 px-4 py-2">
                            <Link
                                href="/notifications"
                                className="text-xs text-indigo-400 hover:text-indigo-300"
                                onClick={() => setOpen(false)}
                            >
                                View all notifications
                            </Link>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
