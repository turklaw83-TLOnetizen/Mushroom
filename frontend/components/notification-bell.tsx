// ---- Notification Bell --------------------------------------------------
// Shows notification count badge + dropdown with severity-sorted alerts.
// Includes "Mark all read" button to clear notifications.
"use client";

import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
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
    const { data, error } = useQuery({
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

    // Mark all read mutation
    const markAllRead = useMutationWithToast<void>({
        mutationFn: () =>
            api.post("/notifications/mark-read", {}, { getToken }),
        successMessage: "All notifications cleared",
        errorMessage: "Failed to clear notifications",
        invalidateKeys: [["notifications"]],
    });

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
                aria-haspopup="true"
                aria-expanded={open}
            >
                <span className={`text-lg ${error ? "text-destructive" : ""}`} aria-hidden="true">&#x1F514;</span>
                {error ? (
                    <span className="absolute -top-0.5 -right-0.5 h-4 min-w-4 px-1 rounded-full bg-destructive text-white text-[10px] font-bold flex items-center justify-center" title="Failed to load notifications">
                        !
                    </span>
                ) : count > 0 ? (
                    <span className="absolute -top-0.5 -right-0.5 h-4 min-w-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">
                        {count > 99 ? "99+" : count}
                    </span>
                ) : null}
            </Button>

            {open && (
                <div
                    className="absolute right-0 top-full mt-2 w-80 max-h-96 overflow-auto bg-popover border rounded-lg shadow-xl z-50 animate-in fade-in slide-in-from-top-2 duration-200"
                    role="menu"
                    aria-label="Notifications"
                    onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }}
                >
                    <div className="p-3 border-b flex items-center justify-between">
                        <div>
                            <p className="text-sm font-semibold">Notifications</p>
                            <p className="text-xs text-muted-foreground">{count} alert{count !== 1 ? "s" : ""}</p>
                        </div>
                        {count > 0 && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="text-xs h-7 px-2 text-muted-foreground hover:text-foreground"
                                onClick={() => markAllRead.mutate()}
                                disabled={markAllRead.isPending}
                            >
                                {markAllRead.isPending ? "Clearing..." : "Mark all read"}
                            </Button>
                        )}
                    </div>

                    {items.length === 0 && (
                        <p className="text-sm text-muted-foreground text-center py-6">All clear &#x1F389;</p>
                    )}

                    {items.map((n, i) => (
                        <button
                            key={`${n.type}-${n.case_id}-${i}`}
                            role="menuitem"
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
