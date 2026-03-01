"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import type { CaseItem } from "@/hooks/use-cases";

// ---- Static commands ----------------------------------------------------

const COMMANDS = [
    { id: "dashboard", label: "Dashboard", icon: "\u26A1", path: "/" },
    { id: "search", label: "Global Search", icon: "\uD83D\uDD0E", path: "/search" },
    { id: "calendar", label: "Calendar", icon: "\uD83D\uDCC5", path: "/calendar" },
    { id: "tasks", label: "Task Board", icon: "\uD83D\uDCCB", path: "/tasks" },
    { id: "crm", label: "Clients (CRM)", icon: "\uD83D\uDC65", path: "/crm" },
    { id: "email", label: "Email Queue", icon: "\uD83D\uDCE7", path: "/email" },
    { id: "conflicts", label: "Conflict Checker", icon: "\u2696\uFE0F", path: "/conflicts" },
    { id: "analytics", label: "Analytics", icon: "\uD83D\uDCCA", path: "/analytics" },
    { id: "portal", label: "Client Portal", icon: "\uD83C\uDF10", path: "/portal" },
    { id: "notifications", label: "Notifications", icon: "\uD83D\uDD14", path: "/notifications" },
    { id: "journal", label: "Journal", icon: "\uD83D\uDCD3", path: "/journal" },
    { id: "backup", label: "Backup Manager", icon: "\uD83D\uDCBE", path: "/settings/backup" },
    { id: "profile", label: "Profile", icon: "\uD83D\uDC64", path: "/profile" },
    { id: "settings", label: "Settings", icon: "\u2699\uFE0F", path: "/settings" },
    { id: "admin", label: "Admin Dashboard", icon: "\uD83D\uDEE1\uFE0F", path: "/admin" },
];

// ---- Quick actions (triggered by "/" prefix) -----------------------------

const QUICK_ACTIONS = [
    { id: "qa-new-case", label: "/new case", description: "Create a new case", icon: "\u2795", path: "/cases/new" },
    { id: "qa-upload", label: "/upload", description: "Upload documents", icon: "\uD83D\uDCC2", path: "/upload" },
    { id: "qa-export", label: "/export", description: "Export reports", icon: "\uD83D\uDCE4", path: "/export" },
];

// ---- Unified result item type -------------------------------------------

interface ResultItem {
    id: string;
    label: string;
    icon: string;
    path: string;
    section: "cases" | "actions" | "commands";
    description?: string;
}

export function CommandPalette() {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    const [selected, setSelected] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);
    const listRef = useRef<HTMLDivElement>(null);
    const router = useRouter();
    const { getToken } = useAuth();

    // ---- Fetch cases for search -----------------------------------------

    const { data: casesData } = useQuery({
        queryKey: ["cases", "command-palette"],
        queryFn: () =>
            api.get<{ items: CaseItem[]; total: number }>("/cases", {
                params: { per_page: 100 },
                getToken,
            }),
        enabled: open,
        staleTime: 30_000,
    });

    const allCases = casesData?.items ?? [];

    // ---- Build unified results list -------------------------------------

    const results: ResultItem[] = useMemo(() => {
        const q = query.trim().toLowerCase();
        const items: ResultItem[] = [];

        // Quick actions mode: show actions when query starts with "/"
        if (q.startsWith("/")) {
            const actionQuery = q.slice(1);
            const matchedActions = QUICK_ACTIONS.filter(
                (a) =>
                    a.label.toLowerCase().includes(q) ||
                    a.description.toLowerCase().includes(actionQuery)
            );
            for (const a of matchedActions) {
                items.push({
                    id: a.id,
                    label: a.label,
                    icon: a.icon,
                    path: a.path,
                    section: "actions",
                    description: a.description,
                });
            }
            return items;
        }

        // Case results (shown first, up to 5)
        if (q.length > 0) {
            const matchedCases = allCases
                .filter(
                    (c) =>
                        c.name.toLowerCase().includes(q) ||
                        (c.client_name && c.client_name.toLowerCase().includes(q)) ||
                        c.id.toLowerCase().includes(q)
                )
                .slice(0, 5);
            for (const c of matchedCases) {
                items.push({
                    id: `case-${c.id}`,
                    label: `Go to case: ${c.name}`,
                    icon: "\uD83D\uDCC1",
                    path: `/cases/${c.id}`,
                    section: "cases",
                    description: c.client_name || undefined,
                });
            }
        } else {
            // No query: show recent cases (up to 5)
            const recent = allCases.slice(0, 5);
            for (const c of recent) {
                items.push({
                    id: `case-${c.id}`,
                    label: c.name,
                    icon: "\uD83D\uDCC1",
                    path: `/cases/${c.id}`,
                    section: "cases",
                    description: c.client_name || undefined,
                });
            }
        }

        // Static commands (filtered by query)
        const matchedCommands = q.length > 0
            ? COMMANDS.filter(
                (cmd) =>
                    cmd.label.toLowerCase().includes(q) ||
                    cmd.id.includes(q)
            )
            : COMMANDS;

        for (const cmd of matchedCommands) {
            items.push({
                id: cmd.id,
                label: cmd.label,
                icon: cmd.icon,
                path: cmd.path,
                section: "commands",
            });
        }

        return items;
    }, [query, allCases]);

    // ---- Keyboard shortcuts (open/close) --------------------------------

    useEffect(() => {
        function onKeyDown(e: KeyboardEvent) {
            if ((e.metaKey || e.ctrlKey) && e.key === "k") {
                e.preventDefault();
                setOpen((prev) => !prev);
                setQuery("");
                setSelected(0);
            }
            if (e.key === "Escape") setOpen(false);
        }
        document.addEventListener("keydown", onKeyDown);
        return () => document.removeEventListener("keydown", onKeyDown);
    }, []);

    useEffect(() => {
        if (open) inputRef.current?.focus();
    }, [open]);

    // Reset selection when results change
    useEffect(() => {
        setSelected(0);
    }, [results.length]);

    // Scroll selected item into view
    useEffect(() => {
        if (!listRef.current) return;
        const item = listRef.current.querySelector(`[data-index="${selected}"]`);
        if (item) {
            item.scrollIntoView({ block: "nearest" });
        }
    }, [selected]);

    // ---- Keyboard navigation within the list ----------------------------

    const onInputKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key === "ArrowDown") {
                e.preventDefault();
                setSelected((s) => Math.min(s + 1, results.length - 1));
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setSelected((s) => Math.max(s - 1, 0));
            } else if (e.key === "Enter" && results[selected]) {
                router.push(results[selected].path);
                setOpen(false);
            }
        },
        [results, selected, router]
    );

    if (!open) return null;

    // ---- Render sections with headers -----------------------------------

    const hasCases = results.some((r) => r.section === "cases");
    const hasActions = results.some((r) => r.section === "actions");
    const hasCommands = results.some((r) => r.section === "commands");

    let currentIndex = 0;

    return (
        <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[20vh]" onClick={() => setOpen(false)}>
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
            <div className="relative w-full max-w-lg rounded-xl border border-white/10 bg-gray-900 shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center gap-3 border-b border-white/10 px-4 py-3">
                    <span className="text-white/40 text-lg">{"\uD83D\uDD0D"}</span>
                    <input
                        ref={inputRef}
                        type="text"
                        value={query}
                        onChange={(e) => { setQuery(e.target.value); setSelected(0); }}
                        onKeyDown={onInputKeyDown}
                        placeholder='Search commands, cases, or type "/" for actions...'
                        className="flex-1 bg-transparent text-white placeholder-white/40 outline-none text-sm"
                    />
                    <kbd className="rounded bg-white/10 px-2 py-0.5 text-xs text-white/40 font-mono">ESC</kbd>
                </div>
                <div ref={listRef} className="max-h-80 overflow-y-auto py-2">
                    {results.length === 0 ? (
                        <div className="px-4 py-8 text-center text-white/40 text-sm">No results found</div>
                    ) : (
                        <>
                            {/* Cases section */}
                            {hasCases && (
                                <>
                                    <div className="px-4 pt-2 pb-1">
                                        <span className="text-[10px] font-semibold uppercase tracking-widest text-white/30">
                                            {query.trim().length > 0 ? "Cases" : "Recent Cases"}
                                        </span>
                                    </div>
                                    {results
                                        .filter((r) => r.section === "cases")
                                        .map((item) => {
                                            const idx = currentIndex++;
                                            return (
                                                <button
                                                    key={item.id}
                                                    data-index={idx}
                                                    className={`w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors ${idx === selected ? "bg-indigo-500/20 text-white" : "text-white/70 hover:bg-white/5"}`}
                                                    onClick={() => { router.push(item.path); setOpen(false); }}
                                                    onMouseEnter={() => setSelected(idx)}
                                                >
                                                    <span className="text-base">{item.icon}</span>
                                                    <div className="flex-1 min-w-0">
                                                        <span className="truncate block">{item.label}</span>
                                                        {item.description && (
                                                            <span className="text-xs text-white/30 truncate block">{item.description}</span>
                                                        )}
                                                    </div>
                                                    <span className="ml-auto text-xs text-white/30 shrink-0">{item.path}</span>
                                                </button>
                                            );
                                        })}
                                </>
                            )}

                            {/* Quick actions section */}
                            {hasActions && (
                                <>
                                    <div className="px-4 pt-2 pb-1">
                                        <span className="text-[10px] font-semibold uppercase tracking-widest text-white/30">
                                            Quick Actions
                                        </span>
                                    </div>
                                    {results
                                        .filter((r) => r.section === "actions")
                                        .map((item) => {
                                            const idx = currentIndex++;
                                            return (
                                                <button
                                                    key={item.id}
                                                    data-index={idx}
                                                    className={`w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors ${idx === selected ? "bg-indigo-500/20 text-white" : "text-white/70 hover:bg-white/5"}`}
                                                    onClick={() => { router.push(item.path); setOpen(false); }}
                                                    onMouseEnter={() => setSelected(idx)}
                                                >
                                                    <span className="text-base">{item.icon}</span>
                                                    <div className="flex-1 min-w-0">
                                                        <span className="truncate block font-mono">{item.label}</span>
                                                        {item.description && (
                                                            <span className="text-xs text-white/30 truncate block">{item.description}</span>
                                                        )}
                                                    </div>
                                                </button>
                                            );
                                        })}
                                </>
                            )}

                            {/* Commands section */}
                            {hasCommands && (
                                <>
                                    {(hasCases || hasActions) && (
                                        <div className="px-4 pt-3 pb-1">
                                            <span className="text-[10px] font-semibold uppercase tracking-widest text-white/30">
                                                Commands
                                            </span>
                                        </div>
                                    )}
                                    {results
                                        .filter((r) => r.section === "commands")
                                        .map((item) => {
                                            const idx = currentIndex++;
                                            return (
                                                <button
                                                    key={item.id}
                                                    data-index={idx}
                                                    className={`w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors ${idx === selected ? "bg-indigo-500/20 text-white" : "text-white/70 hover:bg-white/5"}`}
                                                    onClick={() => { router.push(item.path); setOpen(false); }}
                                                    onMouseEnter={() => setSelected(idx)}
                                                >
                                                    <span className="text-base">{item.icon}</span>
                                                    <span>{item.label}</span>
                                                    <span className="ml-auto text-xs text-white/30">{item.path}</span>
                                                </button>
                                            );
                                        })}
                                </>
                            )}
                        </>
                    )}
                </div>
                <div className="border-t border-white/10 px-4 py-2 flex items-center gap-4 text-xs text-white/30">
                    <span>{"\u2191\u2193"} navigate</span>
                    <span>{"\u21B5"} select</span>
                    <span>esc close</span>
                    <span className="ml-auto">type / for quick actions</span>
                </div>
            </div>
        </div>
    );
}
