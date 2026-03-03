"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { useDebounce } from "@/hooks/use-debounce";
import type { CaseItem } from "@/hooks/use-cases";

// ---- Types for backend search response ----------------------------------

interface SearchCaseResult {
    id: string;
    name: string;
    client_name: string;
    status: string;
    match_type: "case";
}

interface SearchClientResult {
    id: string;
    name: string;
    email: string;
    phone: string;
    status: string;
    linked_cases: string[];
    match_type: "client";
}

interface SearchTaskResult {
    id: string;
    title: string;
    case_id: string;
    case_name: string;
    status: string;
    priority: string;
    match_type: "task";
}

interface GlobalSearchResponse {
    cases: SearchCaseResult[];
    clients: SearchClientResult[];
    tasks: SearchTaskResult[];
}

// ---- Static navigation commands -----------------------------------------

const COMMANDS = [
    { id: "dashboard", label: "Dashboard", icon: "layout", path: "/" },
    { id: "search", label: "Global Search", icon: "search", path: "/search" },
    { id: "calendar", label: "Calendar", icon: "calendar", path: "/calendar" },
    { id: "tasks", label: "Task Board", icon: "clipboard", path: "/tasks" },
    { id: "crm", label: "Clients (CRM)", icon: "users", path: "/crm" },
    { id: "email", label: "Email Queue", icon: "mail", path: "/email" },
    { id: "conflicts", label: "Conflict Checker", icon: "scale", path: "/conflicts" },
    { id: "analytics", label: "Analytics", icon: "chart", path: "/analytics" },
    { id: "portal", label: "Client Portal", icon: "globe", path: "/portal" },
    { id: "notifications", label: "Notifications", icon: "bell", path: "/notifications" },
    { id: "journal", label: "Journal", icon: "book", path: "/journal" },
    { id: "backup", label: "Backup Manager", icon: "save", path: "/settings/backup" },
    { id: "profile", label: "Profile", icon: "user", path: "/profile" },
    { id: "settings", label: "Settings", icon: "settings", path: "/settings" },
    { id: "admin", label: "Admin Dashboard", icon: "shield", path: "/admin" },
];

// ---- Quick actions (triggered by "/" prefix) -----------------------------

const QUICK_ACTIONS = [
    { id: "qa-new-case", label: "/new case", description: "Create a new case", icon: "plus", path: "/cases/new" },
    { id: "qa-upload", label: "/upload", description: "Upload documents", icon: "upload", path: "/upload" },
    { id: "qa-export", label: "/export", description: "Export reports", icon: "download", path: "/export" },
];

// ---- Unified result item type -------------------------------------------

type ResultSection = "cases" | "clients" | "actions" | "commands";

interface ResultItem {
    id: string;
    label: string;
    icon: string;
    path: string;
    section: ResultSection;
    description?: string;
    badge?: string;
    badgeVariant?: "default" | "success" | "warning" | "muted";
}

// ---- Section config for headers -----------------------------------------

const SECTION_META: Record<ResultSection, { label: string; emptyLabel?: string }> = {
    cases: { label: "Cases", emptyLabel: "Recent Cases" },
    clients: { label: "Clients" },
    actions: { label: "Quick Actions" },
    commands: { label: "Commands" },
};

// ---- SVG Icons (inline to avoid extra deps) -----------------------------

function IconSearch({ className = "" }: { className?: string }) {
    return (
        <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
        </svg>
    );
}

function IconFolder({ className = "" }: { className?: string }) {
    return (
        <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
        </svg>
    );
}

function IconUser({ className = "" }: { className?: string }) {
    return (
        <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
        </svg>
    );
}

function IconCommand({ className = "" }: { className?: string }) {
    return (
        <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 6v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3" />
        </svg>
    );
}

function IconZap({ className = "" }: { className?: string }) {
    return (
        <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
        </svg>
    );
}

function IconLoader({ className = "" }: { className?: string }) {
    return (
        <svg className={`animate-spin ${className}`} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
        </svg>
    );
}

function SectionIcon({ section }: { section: ResultSection }) {
    switch (section) {
        case "cases": return <IconFolder className="text-blue-400" />;
        case "clients": return <IconUser className="text-emerald-400" />;
        case "actions": return <IconZap className="text-amber-400" />;
        case "commands": return <IconCommand className="text-white/40" />;
    }
}

// ---- Badge color mappings -----------------------------------------------

const BADGE_COLORS: Record<string, string> = {
    default: "bg-white/10 text-white/50",
    success: "bg-emerald-500/15 text-emerald-400",
    warning: "bg-amber-500/15 text-amber-400",
    muted: "bg-white/5 text-white/30",
};

// ---- Component ----------------------------------------------------------

export function CommandPalette() {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    const [selected, setSelected] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);
    const listRef = useRef<HTMLDivElement>(null);
    const router = useRouter();
    const { getToken } = useAuth();

    // Debounce the query for API calls (300ms)
    const debouncedQuery = useDebounce(query, 300);

    // ---- Fetch pre-loaded cases for instant local filtering -------------

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

    // ---- Backend global search (debounced) for clients + tasks ----------

    const shouldSearch = open && debouncedQuery.trim().length >= 2 && !debouncedQuery.trim().startsWith("/");

    const {
        data: searchResults,
        isFetching: isSearching,
    } = useQuery({
        queryKey: ["command-palette-search", debouncedQuery],
        queryFn: () =>
            api.get<GlobalSearchResponse>("/search", {
                params: { q: debouncedQuery.trim() },
                getToken,
            }),
        enabled: shouldSearch,
        staleTime: 15_000,
        // Keep previous data while new search loads for smoother UX
        placeholderData: (prev) => prev,
    });

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

        // --- Cases: local filtering for instant results ---
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
                    label: c.name,
                    icon: "folder",
                    path: `/cases/${c.id}`,
                    section: "cases",
                    description: c.client_name || undefined,
                    badge: c.phase || c.status || undefined,
                    badgeVariant: c.phase === "active" || c.status === "active" ? "success" : "muted",
                });
            }
        } else {
            // No query: show recent cases (up to 5)
            const recent = allCases.slice(0, 5);
            for (const c of recent) {
                items.push({
                    id: `case-${c.id}`,
                    label: c.name,
                    icon: "folder",
                    path: `/cases/${c.id}`,
                    section: "cases",
                    description: c.client_name || undefined,
                    badge: c.phase || c.status || undefined,
                    badgeVariant: c.phase === "active" || c.status === "active" ? "success" : "muted",
                });
            }
        }

        // --- Clients: from backend search response ---
        if (searchResults?.clients && q.length >= 2) {
            const existingCaseIds = new Set(items.map((i) => i.id));
            for (const cl of searchResults.clients.slice(0, 5)) {
                const id = `client-${cl.id}`;
                if (existingCaseIds.has(id)) continue;
                items.push({
                    id,
                    label: cl.name,
                    icon: "user",
                    path: "/crm",
                    section: "clients",
                    description: cl.email || cl.phone || undefined,
                    badge: cl.status || undefined,
                    badgeVariant: cl.status === "active" ? "success"
                        : cl.status === "prospective" ? "warning"
                        : "muted",
                });
            }
        }

        // --- Static commands: filtered by query ---
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
    }, [query, allCases, searchResults]);

    // ---- Section ordering -----------------------------------------------

    const sectionOrder: ResultSection[] = ["cases", "clients", "actions", "commands"];

    const groupedResults = useMemo(() => {
        const groups: { section: ResultSection; items: ResultItem[] }[] = [];
        for (const section of sectionOrder) {
            const sectionItems = results.filter((r) => r.section === section);
            if (sectionItems.length > 0) {
                groups.push({ section, items: sectionItems });
            }
        }
        return groups;
    }, [results]);

    // Flat index mapping for keyboard navigation
    const flatItems = useMemo(() => {
        return groupedResults.flatMap((g) => g.items);
    }, [groupedResults]);

    // ---- Keyboard shortcuts (open/close) --------------------------------

    useEffect(() => {
        function onKeyDown(e: KeyboardEvent) {
            if ((e.metaKey || e.ctrlKey) && e.key === "k") {
                e.preventDefault();
                setOpen((prev) => !prev);
                setQuery("");
                setSelected(0);
            }
            if (e.key === "Escape" && open) {
                e.preventDefault();
                setOpen(false);
            }
        }
        document.addEventListener("keydown", onKeyDown);
        return () => document.removeEventListener("keydown", onKeyDown);
    }, [open]);

    useEffect(() => {
        if (open) {
            // Small delay to ensure DOM is ready
            requestAnimationFrame(() => inputRef.current?.focus());
        }
    }, [open]);

    // Reset selection when results change
    useEffect(() => {
        setSelected(0);
    }, [flatItems.length]);

    // Scroll selected item into view
    useEffect(() => {
        if (!listRef.current) return;
        const item = listRef.current.querySelector(`[data-index="${selected}"]`);
        if (item) {
            item.scrollIntoView({ block: "nearest" });
        }
    }, [selected]);

    // ---- Navigate to selected item --------------------------------------

    const navigateTo = useCallback(
        (item: ResultItem) => {
            router.push(item.path);
            setOpen(false);
        },
        [router]
    );

    // ---- Keyboard navigation within the list ----------------------------

    const onInputKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key === "ArrowDown") {
                e.preventDefault();
                setSelected((s) => Math.min(s + 1, flatItems.length - 1));
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setSelected((s) => Math.max(s - 1, 0));
            } else if (e.key === "Enter" && flatItems[selected]) {
                e.preventDefault();
                navigateTo(flatItems[selected]);
            } else if (e.key === "Escape") {
                e.preventDefault();
                if (query) {
                    setQuery("");
                    setSelected(0);
                } else {
                    setOpen(false);
                }
            }
        },
        [flatItems, selected, navigateTo, query]
    );

    if (!open) return null;

    // ---- Compute flat index for each item across grouped sections -------

    let flatIndex = 0;

    const hasQuery = query.trim().length > 0;
    const isWaitingForSearch = hasQuery && query.trim().length >= 2 && !query.trim().startsWith("/") && isSearching;

    return (
        <div
            className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]"
            onClick={() => setOpen(false)}
        >
            {/* Backdrop */}
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

            {/* Palette container */}
            <div
                className="relative w-full max-w-xl rounded-xl border border-white/10 bg-gray-900 shadow-2xl overflow-hidden"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Search input row */}
                <div className="flex items-center gap-3 border-b border-white/10 px-4 py-3">
                    {isWaitingForSearch ? (
                        <IconLoader className="text-indigo-400 shrink-0" />
                    ) : (
                        <IconSearch className="text-white/40 shrink-0" />
                    )}
                    <input
                        ref={inputRef}
                        type="text"
                        value={query}
                        onChange={(e) => { setQuery(e.target.value); setSelected(0); }}
                        onKeyDown={onInputKeyDown}
                        placeholder='Search commands, cases, clients... or type "/" for actions'
                        className="flex-1 bg-transparent text-white placeholder-white/40 outline-none text-sm"
                        autoComplete="off"
                        spellCheck={false}
                    />
                    <kbd className="rounded bg-white/10 px-2 py-0.5 text-xs text-white/40 font-mono shrink-0">
                        ESC
                    </kbd>
                </div>

                {/* Results list */}
                <div ref={listRef} className="max-h-[60vh] overflow-y-auto py-1">
                    {flatItems.length === 0 && hasQuery ? (
                        <div className="px-4 py-10 text-center text-white/40 text-sm">
                            <IconSearch className="mx-auto mb-2 text-white/20" />
                            No results found for &ldquo;{query.trim()}&rdquo;
                        </div>
                    ) : (
                        groupedResults.map(({ section, items: sectionItems }) => (
                            <div key={section}>
                                {/* Section header */}
                                <div className="px-4 pt-3 pb-1.5 flex items-center gap-2">
                                    <span className="text-[10px] font-semibold uppercase tracking-widest text-white/30">
                                        {hasQuery
                                            ? SECTION_META[section].label
                                            : (SECTION_META[section].emptyLabel || SECTION_META[section].label)}
                                    </span>
                                    {hasQuery && (
                                        <span className="text-[10px] text-white/20">
                                            {sectionItems.length}
                                        </span>
                                    )}
                                </div>

                                {/* Section items */}
                                {sectionItems.map((item) => {
                                    const idx = flatIndex++;
                                    const isSelected = idx === selected;

                                    return (
                                        <button
                                            key={item.id}
                                            data-index={idx}
                                            className={`
                                                w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm
                                                transition-colors duration-75
                                                ${isSelected
                                                    ? "bg-indigo-500/20 text-white"
                                                    : "text-white/70 hover:bg-white/5"
                                                }
                                            `}
                                            onClick={() => navigateTo(item)}
                                            onMouseEnter={() => setSelected(idx)}
                                        >
                                            {/* Section-aware icon */}
                                            <span className="shrink-0">
                                                <SectionIcon section={item.section} />
                                            </span>

                                            {/* Label + description */}
                                            <div className="flex-1 min-w-0">
                                                <span className={`truncate block ${item.section === "actions" ? "font-mono" : ""}`}>
                                                    {item.label}
                                                </span>
                                                {item.description && (
                                                    <span className="text-xs text-white/30 truncate block">
                                                        {item.description}
                                                    </span>
                                                )}
                                            </div>

                                            {/* Badge (status/phase) */}
                                            {item.badge && (
                                                <span className={`
                                                    shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium
                                                    ${BADGE_COLORS[item.badgeVariant || "default"]}
                                                `}>
                                                    {item.badge}
                                                </span>
                                            )}

                                            {/* Path hint for commands */}
                                            {item.section === "commands" && !item.badge && (
                                                <span className="ml-auto text-xs text-white/20 shrink-0 font-mono">
                                                    {item.path}
                                                </span>
                                            )}

                                            {/* Arrow indicator for selected item */}
                                            {isSelected && (
                                                <span className="text-white/40 text-xs shrink-0">&crarr;</span>
                                            )}
                                        </button>
                                    );
                                })}
                            </div>
                        ))
                    )}
                </div>

                {/* Footer */}
                <div className="border-t border-white/10 px-4 py-2 flex items-center gap-4 text-xs text-white/30">
                    <span className="flex items-center gap-1">
                        <kbd className="rounded bg-white/10 px-1 py-0.5 text-[10px] font-mono">&uarr;&darr;</kbd>
                        navigate
                    </span>
                    <span className="flex items-center gap-1">
                        <kbd className="rounded bg-white/10 px-1 py-0.5 text-[10px] font-mono">&crarr;</kbd>
                        select
                    </span>
                    <span className="flex items-center gap-1">
                        <kbd className="rounded bg-white/10 px-1 py-0.5 text-[10px] font-mono">esc</kbd>
                        close
                    </span>
                    <span className="ml-auto text-white/20">
                        {isWaitingForSearch ? "Searching..." : 'type / for quick actions'}
                    </span>
                </div>
            </div>
        </div>
    );
}
