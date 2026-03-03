// ---- Notification Bell --------------------------------------------------
// Shows notification count badge + dropdown with severity-sorted alerts.
"use client";

import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Notification {
    type: string;
    title: string;
    detail: string;
    case_id: string;
    case_name: string;
    severity: "critical" | "high" | "medium" | "low";
    timestamp: string;
}

function severityColor(s: string) {
    switch (s) {
        case "critical": return "text-red-400 bg-red-500/10";
        case "high": return "text-amber-400 bg-amber-500/10";
        case "medium": return "text-blue-400 bg-blue-500/10";
        default: return "text-zinc-400 bg-zinc-500/10";
    }
}

function severityDot(s: string) {
    switch (s) {
        case "critical": return "bg-red-500";
        case "high": return "bg-amber-500";
        case "medium": return "bg-blue-500";
        default: return "bg-zinc-500";
    }
}

export function NotificationBell() {
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);
    const { getToken } = useAuth();
    const router = useRouter();

    const { data } = useQuery({
        queryKey: ["notifications"],
        queryFn: () =>
            api.get<{ items: Notification[]; total: number }>("/notifications", { getToken }),
        refetchInterval: 60000,
        staleTime: 55000,
        retry: false,
        refetchOnWindowFocus: false,
    });

    const items = data?.items ?? [];
    const count = items.length;

    // Click outside to close
    useEffect(() => {
        function handle(e: MouseEvent) {
            if (ref.current && !ref.current.contains(e.target as Node)) {
                setOpen(false);
            }
        }
        if (open) document.addEventListener("mousedown", handle);
        return () => document.removeEventListener("mousedown", handle);
    }, [open]);

    return (
        <div ref={ref} className="relative">
            <Button
                variant="ghost"
                size="icon"
                className="relative"
                onClick={() => setOpen(!open)}
                aria-label="Notifications"
            >
                <span className="text-lg">🔔</span>
                {count > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 h-4 min-w-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">
                        {count > 99 ? "99+" : count}
                    </span>
                )}
            </Button>

            {open && (
                <div className="absolute right-0 top-full mt-2 w-80 max-h-96 overflow-auto bg-popover border rounded-lg shadow-xl z-50">
                    <div className="p-3 border-b">
                        <p className="text-sm font-semibold">Notifications</p>
                        <p className="text-xs text-muted-foreground">{count} alert{count !== 1 ? "s" : ""}</p>
                    </div>

                    {items.length === 0 && (
                        <p className="text-sm text-muted-foreground text-center py-6">All clear 🎉</p>
                    )}

                    {items.map((n, i) => (
                        <button
                            key={`${n.type}-${n.case_id}-${i}`}
                            className="w-full text-left px-3 py-2.5 hover:bg-accent/50 transition-colors border-b last:border-0"
                            onClick={() => {
                                if (n.case_id) {
                                    router.push(`/cases/${n.case_id}`);
                                    setOpen(false);
                                }
                            }}
                        >
                            <div className="flex items-start gap-2">
                                <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${severityDot(n.severity)}`} />
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium truncate">{n.title}</p>
                                    <p className="text-xs text-muted-foreground truncate">{n.detail}</p>
                                    {n.case_name && (
                                        <Badge variant="outline" className={`mt-1 text-[10px] ${severityColor(n.severity)}`}>
                                            {n.case_name}
                                        </Badge>
                                    )}
                                </div>
                            </div>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
