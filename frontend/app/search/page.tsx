// ---- Full-text Search Page -----------------------------------------------
// Cross-entity search with typeahead, keyboard nav, and within-case mode.
"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api-client";
import { useDebounce } from "@/hooks/use-debounce";
import { useCase } from "@/hooks/use-cases";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

// ---- Types --------------------------------------------------------------

interface CaseResult {
    id: string;
    name: string;
    client_name: string;
    status: string;
    match_type: "case";
}

interface ClientResult {
    id: string;
    name: string;
    email: string;
    phone: string;
    status: string;
    linked_cases: string[];
    match_type: "client";
}

interface TaskResult {
    id: string;
    title: string;
    case_id: string;
    case_name: string;
    status: string;
    priority: string;
    match_type: "task";
}

interface GlobalSearchResponse {
    cases: CaseResult[];
    clients: ClientResult[];
    tasks: TaskResult[];
}

interface CaseSearchResponse {
    tasks: TaskResult[];
    activity: ActivityResult[];
}

interface ActivityResult {
    id?: string;
    action: string;
    detail: string;
    timestamp?: string;
    user?: string;
}

type FlatResult =
    | (CaseResult & { _section: "cases"; _index: number })
    | (ClientResult & { _section: "clients"; _index: number })
    | (TaskResult & { _section: "tasks"; _index: number })
    | (ActivityResult & { _section: "activity"; _index: number });

// ---- Status helpers -----------------------------------------------------

const PHASE_COLORS: Record<string, string> = {
    active: "text-green-400 border-green-500/30 bg-green-500/10",
    closed: "text-amber-400 border-amber-500/30 bg-amber-500/10",
    archived: "text-zinc-400 border-zinc-500/30 bg-zinc-500/10",
};

const PRIORITY_COLORS: Record<string, string> = {
    high: "text-red-400 border-red-400/30",
    medium: "text-amber-400 border-amber-400/30",
    low: "text-green-400 border-green-400/30",
};

const CLIENT_STATUS_COLORS: Record<string, string> = {
    active: "text-green-400 border-green-500/30 bg-green-500/10",
    prospective: "text-blue-400 border-blue-500/30 bg-blue-500/10",
    former: "text-amber-400 border-amber-500/30 bg-amber-500/10",
    declined: "text-red-400 border-red-500/30 bg-red-500/10",
};

const TASK_STATUS_COLORS: Record<string, string> = {
    pending: "text-zinc-400 border-zinc-500/30 bg-zinc-500/10",
    in_progress: "text-blue-400 border-blue-500/30 bg-blue-500/10",
    completed: "text-green-400 border-green-500/30 bg-green-500/10",
};

const RECENT_SEARCHES_KEY = "mushroom-cloud-recent-searches";
const MAX_RECENT = 8;

function loadRecentSearches(): string[] {
    if (typeof window === "undefined") return [];
    try {
        const raw = localStorage.getItem(RECENT_SEARCHES_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch {
        return [];
    }
}

function saveRecentSearch(term: string) {
    if (typeof window === "undefined" || !term.trim()) return;
    try {
        const existing = loadRecentSearches();
        const updated = [term, ...existing.filter((s) => s !== term)].slice(0, MAX_RECENT);
        localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(updated));
    } catch {
        // Ignore storage errors
    }
}

// ---- Component ----------------------------------------------------------

export default function SearchPage() {
    const { getToken } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();
    const caseIdParam = searchParams.get("case_id") || "";

    // Input state
    const [query, setQuery] = useState("");
    const debouncedQuery = useDebounce(query, 300);
    const inputRef = useRef<HTMLInputElement>(null);
    const resultsRef = useRef<HTMLDivElement>(null);

    // Search mode: global vs within-case
    const [searchInCase, setSearchInCase] = useState(!!caseIdParam);

    // Keyboard navigation
    const [selectedIndex, setSelectedIndex] = useState(-1);

    // Recent searches
    const [recentSearches, setRecentSearches] = useState<string[]>([]);

    // Load recent searches on mount
    useEffect(() => {
        setRecentSearches(loadRecentSearches());
    }, []);

    // Auto-focus on mount
    useEffect(() => {
        inputRef.current?.focus();
    }, []);

    // Fetch case name when in case-scoped mode
    const { data: scopedCase } = useCase(caseIdParam || null);

    // ---- Global search query ----
    const {
        data: globalResults,
        isLoading: globalLoading,
        isFetching: globalFetching,
    } = useQuery({
        queryKey: ["search-global", debouncedQuery],
        queryFn: () =>
            api.get<GlobalSearchResponse>("/search", {
                params: { q: debouncedQuery },
                getToken,
            }),
        enabled: debouncedQuery.length >= 2 && !searchInCase,
        staleTime: 30_000,
    });

    // ---- Within-case search query ----
    const {
        data: caseResults,
        isLoading: caseLoading,
        isFetching: caseFetching,
    } = useQuery({
        queryKey: ["search-case", caseIdParam, debouncedQuery],
        queryFn: () =>
            api.get<CaseSearchResponse>(`/search/case/${caseIdParam}`, {
                params: { q: debouncedQuery },
                getToken,
            }),
        enabled: debouncedQuery.length >= 2 && searchInCase && !!caseIdParam,
        staleTime: 30_000,
    });

    const isLoading = searchInCase ? caseLoading : globalLoading;
    const isFetching = searchInCase ? caseFetching : globalFetching;

    // ---- Flatten results for keyboard navigation ----
    const flatResults: FlatResult[] = useMemo(() => {
        const items: FlatResult[] = [];
        let idx = 0;

        if (searchInCase && caseResults) {
            for (const t of caseResults.tasks) {
                items.push({ ...t, _section: "tasks", _index: idx++, match_type: "task" });
            }
            for (const a of caseResults.activity) {
                items.push({ ...a, _section: "activity", _index: idx++ });
            }
        } else if (!searchInCase && globalResults) {
            for (const c of globalResults.cases) {
                items.push({ ...c, _section: "cases", _index: idx++ });
            }
            for (const cl of globalResults.clients) {
                items.push({ ...cl, _section: "clients", _index: idx++ });
            }
            for (const t of globalResults.tasks) {
                items.push({ ...t, _section: "tasks", _index: idx++ });
            }
        }

        return items;
    }, [globalResults, caseResults, searchInCase]);

    // Reset selection when results change
    useEffect(() => {
        setSelectedIndex(-1);
    }, [flatResults]);

    // ---- Navigation helpers ----
    const navigateToResult = useCallback(
        (result: FlatResult) => {
            // Save to recent searches
            if (query.trim()) {
                saveRecentSearch(query.trim());
            }

            if (result._section === "cases") {
                router.push(`/cases/${(result as CaseResult).id}`);
            } else if (result._section === "clients") {
                router.push(`/crm`);
            } else if (result._section === "tasks") {
                const taskResult = result as TaskResult;
                if (taskResult.case_id) {
                    router.push(`/cases/${taskResult.case_id}`);
                } else {
                    router.push("/tasks");
                }
            } else if (result._section === "activity") {
                if (caseIdParam) {
                    router.push(`/cases/${caseIdParam}/activity`);
                }
            }
        },
        [router, query, caseIdParam],
    );

    // ---- Keyboard handler ----
    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            switch (e.key) {
                case "ArrowDown":
                    e.preventDefault();
                    setSelectedIndex((prev) =>
                        prev < flatResults.length - 1 ? prev + 1 : prev,
                    );
                    break;
                case "ArrowUp":
                    e.preventDefault();
                    setSelectedIndex((prev) => (prev > 0 ? prev - 1 : -1));
                    break;
                case "Enter":
                    e.preventDefault();
                    if (selectedIndex >= 0 && selectedIndex < flatResults.length) {
                        navigateToResult(flatResults[selectedIndex]);
                    }
                    break;
                case "Escape":
                    e.preventDefault();
                    if (query) {
                        setQuery("");
                        setSelectedIndex(-1);
                    } else {
                        inputRef.current?.blur();
                    }
                    break;
                default:
                    break;
            }
        },
        [flatResults, selectedIndex, navigateToResult, query],
    );

    // Scroll selected item into view
    useEffect(() => {
        if (selectedIndex >= 0 && resultsRef.current) {
            const el = resultsRef.current.querySelector(
                `[data-result-index="${selectedIndex}"]`,
            );
            el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
        }
    }, [selectedIndex]);

    // ---- Section counts ----
    const casesCount = globalResults?.cases?.length ?? 0;
    const clientsCount = globalResults?.clients?.length ?? 0;
    const globalTasksCount = globalResults?.tasks?.length ?? 0;
    const caseTasksCount = caseResults?.tasks?.length ?? 0;
    const activityCount = caseResults?.activity?.length ?? 0;

    const totalResults = searchInCase
        ? caseTasksCount + activityCount
        : casesCount + clientsCount + globalTasksCount;

    const hasQuery = debouncedQuery.length >= 2;
    const showEmpty = hasQuery && !isLoading && totalResults === 0;
    const showResults = hasQuery && totalResults > 0;

    // ---- Render ----
    return (
        <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Search</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Find cases, clients, and tasks across the platform
                </p>
            </div>

            {/* Search input */}
            <div className="relative" onKeyDown={handleKeyDown}>
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none">
                    <SearchIcon />
                </div>
                <input
                    ref={inputRef}
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={
                        searchInCase && scopedCase
                            ? `Search in "${scopedCase.name}"...`
                            : "Search cases, clients, tasks..."
                    }
                    className={cn(
                        "w-full h-12 pl-10 pr-20 rounded-lg border bg-background text-base",
                        "border-input shadow-xs transition-[color,box-shadow] outline-none",
                        "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
                        "placeholder:text-muted-foreground",
                    )}
                    autoComplete="off"
                    spellCheck={false}
                />
                <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                    {isFetching && (
                        <div className="size-4 border-2 border-muted-foreground/30 border-t-primary rounded-full animate-spin" />
                    )}
                    {query && (
                        <Button
                            variant="ghost"
                            size="icon-xs"
                            onClick={() => {
                                setQuery("");
                                setSelectedIndex(-1);
                                inputRef.current?.focus();
                            }}
                            aria-label="Clear search"
                        >
                            <XIcon />
                        </Button>
                    )}
                    <kbd className="hidden sm:inline-flex items-center rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground font-mono">
                        ESC
                    </kbd>
                </div>
            </div>

            {/* Case-scoped toggle */}
            {caseIdParam && (
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => setSearchInCase(false)}
                        className={cn(
                            "px-3 py-1.5 rounded-md text-sm transition-colors",
                            !searchInCase
                                ? "bg-primary text-primary-foreground"
                                : "bg-secondary text-secondary-foreground hover:bg-secondary/80",
                        )}
                    >
                        Search all
                    </button>
                    <button
                        onClick={() => setSearchInCase(true)}
                        className={cn(
                            "px-3 py-1.5 rounded-md text-sm transition-colors",
                            searchInCase
                                ? "bg-primary text-primary-foreground"
                                : "bg-secondary text-secondary-foreground hover:bg-secondary/80",
                        )}
                    >
                        Search in {scopedCase?.name ? `"${scopedCase.name}"` : "case"}
                    </button>
                </div>
            )}

            {/* Results */}
            <div ref={resultsRef} className="space-y-6">
                {/* Loading skeletons */}
                {isLoading && hasQuery && (
                    <div className="space-y-4">
                        <Skeleton className="h-5 w-24" />
                        {Array.from({ length: 4 }).map((_, i) => (
                            <Skeleton key={i} className="h-16 w-full rounded-lg" />
                        ))}
                    </div>
                )}

                {/* No results */}
                {showEmpty && (
                    <div className="text-center py-16 space-y-3">
                        <div className="text-4xl opacity-40">
                            <MagnifyingGlassIcon />
                        </div>
                        <p className="text-muted-foreground">
                            No results found for &quot;{debouncedQuery}&quot;
                        </p>
                        <p className="text-xs text-muted-foreground/70">
                            Try a different search term or broaden your query
                        </p>
                    </div>
                )}

                {/* Global results */}
                {showResults && !searchInCase && globalResults && (
                    <>
                        {/* Cases */}
                        {globalResults.cases.length > 0 && (
                            <ResultSection title="Cases" count={casesCount}>
                                {globalResults.cases.map((c) => {
                                    const flat = flatResults.find(
                                        (f) => f._section === "cases" && (f as CaseResult).id === c.id,
                                    );
                                    const idx = flat?._index ?? -1;
                                    return (
                                        <ResultCard
                                            key={c.id}
                                            selected={selectedIndex === idx}
                                            dataIndex={idx}
                                            onClick={() => navigateToResult(flat!)}
                                        >
                                            <div className="flex items-center justify-between gap-3">
                                                <div className="min-w-0 flex-1">
                                                    <p className="text-sm font-medium truncate">{c.name}</p>
                                                    {c.client_name && (
                                                        <p className="text-xs text-muted-foreground truncate mt-0.5">
                                                            Client: {c.client_name}
                                                        </p>
                                                    )}
                                                </div>
                                                <Badge
                                                    variant="outline"
                                                    className={cn(
                                                        "text-[10px] shrink-0",
                                                        PHASE_COLORS[c.status] ?? "",
                                                    )}
                                                >
                                                    {c.status || "active"}
                                                </Badge>
                                            </div>
                                        </ResultCard>
                                    );
                                })}
                            </ResultSection>
                        )}

                        {/* Clients */}
                        {globalResults.clients.length > 0 && (
                            <ResultSection title="Clients" count={clientsCount}>
                                {globalResults.clients.map((cl) => {
                                    const flat = flatResults.find(
                                        (f) => f._section === "clients" && (f as ClientResult).id === cl.id,
                                    );
                                    const idx = flat?._index ?? -1;
                                    return (
                                        <ResultCard
                                            key={cl.id}
                                            selected={selectedIndex === idx}
                                            dataIndex={idx}
                                            onClick={() => navigateToResult(flat!)}
                                        >
                                            <div className="flex items-center justify-between gap-3">
                                                <div className="min-w-0 flex-1">
                                                    <p className="text-sm font-medium truncate">{cl.name}</p>
                                                    {cl.email && (
                                                        <p className="text-xs text-muted-foreground truncate mt-0.5">
                                                            {cl.email}
                                                        </p>
                                                    )}
                                                </div>
                                                {cl.status && (
                                                    <Badge
                                                        variant="outline"
                                                        className={cn(
                                                            "text-[10px] shrink-0",
                                                            CLIENT_STATUS_COLORS[cl.status] ?? "",
                                                        )}
                                                    >
                                                        {cl.status}
                                                    </Badge>
                                                )}
                                            </div>
                                        </ResultCard>
                                    );
                                })}
                            </ResultSection>
                        )}

                        {/* Tasks */}
                        {globalResults.tasks.length > 0 && (
                            <ResultSection title="Tasks" count={globalTasksCount}>
                                {globalResults.tasks.map((t, i) => {
                                    const flat = flatResults.find(
                                        (f) =>
                                            f._section === "tasks" &&
                                            (f as TaskResult).id === t.id &&
                                            (f as TaskResult).case_id === t.case_id,
                                    );
                                    const idx = flat?._index ?? -1;
                                    return (
                                        <ResultCard
                                            key={`${t.case_id}-${t.id}-${i}`}
                                            selected={selectedIndex === idx}
                                            dataIndex={idx}
                                            onClick={() => navigateToResult(flat!)}
                                        >
                                            <div className="flex items-center justify-between gap-3">
                                                <div className="min-w-0 flex-1">
                                                    <p className="text-sm font-medium truncate">{t.title}</p>
                                                    <div className="flex items-center gap-2 mt-0.5">
                                                        {t.case_name && (
                                                            <span className="text-xs text-muted-foreground truncate">
                                                                {t.case_name}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-1.5 shrink-0">
                                                    {t.priority && (
                                                        <Badge
                                                            variant="outline"
                                                            className={cn(
                                                                "text-[10px]",
                                                                PRIORITY_COLORS[t.priority] ?? "",
                                                            )}
                                                        >
                                                            {t.priority}
                                                        </Badge>
                                                    )}
                                                    {t.status && (
                                                        <Badge
                                                            variant="outline"
                                                            className={cn(
                                                                "text-[10px]",
                                                                TASK_STATUS_COLORS[t.status] ?? "",
                                                            )}
                                                        >
                                                            {t.status.replace("_", " ")}
                                                        </Badge>
                                                    )}
                                                </div>
                                            </div>
                                        </ResultCard>
                                    );
                                })}
                            </ResultSection>
                        )}
                    </>
                )}

                {/* Within-case results */}
                {showResults && searchInCase && caseResults && (
                    <>
                        {caseResults.tasks.length > 0 && (
                            <ResultSection title="Tasks" count={caseTasksCount}>
                                {caseResults.tasks.map((t, i) => {
                                    const flat = flatResults.find(
                                        (f) =>
                                            f._section === "tasks" &&
                                            (f as TaskResult).id === t.id,
                                    );
                                    const idx = flat?._index ?? -1;
                                    return (
                                        <ResultCard
                                            key={`task-${t.id}-${i}`}
                                            selected={selectedIndex === idx}
                                            dataIndex={idx}
                                            onClick={() => navigateToResult(flat!)}
                                        >
                                            <div className="flex items-center justify-between gap-3">
                                                <div className="min-w-0 flex-1">
                                                    <p className="text-sm font-medium truncate">
                                                        {t.title}
                                                    </p>
                                                </div>
                                                {t.status && (
                                                    <Badge
                                                        variant="outline"
                                                        className={cn(
                                                            "text-[10px]",
                                                            TASK_STATUS_COLORS[t.status] ?? "",
                                                        )}
                                                    >
                                                        {t.status.replace("_", " ")}
                                                    </Badge>
                                                )}
                                            </div>
                                        </ResultCard>
                                    );
                                })}
                            </ResultSection>
                        )}

                        {caseResults.activity.length > 0 && (
                            <ResultSection title="Activity" count={activityCount}>
                                {caseResults.activity.map((a, i) => {
                                    const flat = flatResults.find(
                                        (f) => f._section === "activity" && f._index === casesCount + clientsCount + globalTasksCount + caseTasksCount + i,
                                    );
                                    // For activity, use a simpler index calc
                                    const idx = caseTasksCount + i;
                                    return (
                                        <ResultCard
                                            key={`activity-${i}`}
                                            selected={selectedIndex === idx}
                                            dataIndex={idx}
                                            onClick={() => {
                                                if (caseIdParam) {
                                                    router.push(`/cases/${caseIdParam}/activity`);
                                                }
                                            }}
                                        >
                                            <div className="min-w-0 flex-1">
                                                <p className="text-sm font-medium truncate">
                                                    {a.action}
                                                </p>
                                                {a.detail && (
                                                    <p className="text-xs text-muted-foreground truncate mt-0.5">
                                                        {a.detail}
                                                    </p>
                                                )}
                                                {a.timestamp && (
                                                    <p className="text-[10px] text-muted-foreground/70 mt-1">
                                                        {a.timestamp}
                                                    </p>
                                                )}
                                            </div>
                                        </ResultCard>
                                    );
                                })}
                            </ResultSection>
                        )}
                    </>
                )}

                {/* Empty state: recent searches / suggestions */}
                {!hasQuery && (
                    <div className="space-y-6 pt-4">
                        {/* Recent searches */}
                        {recentSearches.length > 0 && (
                            <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-sm font-medium text-muted-foreground">
                                        Recent searches
                                    </h3>
                                    <Button
                                        variant="ghost"
                                        size="xs"
                                        className="text-xs text-muted-foreground"
                                        onClick={() => {
                                            localStorage.removeItem(RECENT_SEARCHES_KEY);
                                            setRecentSearches([]);
                                        }}
                                    >
                                        Clear
                                    </Button>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    {recentSearches.map((term) => (
                                        <button
                                            key={term}
                                            className={cn(
                                                "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm",
                                                "bg-secondary text-secondary-foreground hover:bg-secondary/80",
                                                "transition-colors cursor-pointer",
                                            )}
                                            onClick={() => {
                                                setQuery(term);
                                                inputRef.current?.focus();
                                            }}
                                        >
                                            <ClockIcon />
                                            {term}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Suggestions */}
                        <div className="space-y-3">
                            <h3 className="text-sm font-medium text-muted-foreground">
                                Suggested searches
                            </h3>
                            <div className="flex flex-wrap gap-2">
                                {["motion", "hearing", "discovery", "deposition", "trial", "settlement"].map(
                                    (term) => (
                                        <button
                                            key={term}
                                            className={cn(
                                                "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm",
                                                "border border-border text-muted-foreground",
                                                "hover:bg-accent hover:text-accent-foreground",
                                                "transition-colors cursor-pointer",
                                            )}
                                            onClick={() => {
                                                setQuery(term);
                                                inputRef.current?.focus();
                                            }}
                                        >
                                            {term}
                                        </button>
                                    ),
                                )}
                            </div>
                        </div>

                        {/* Keyboard hints */}
                        <div className="pt-6 border-t border-border">
                            <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-muted-foreground/70">
                                <span>
                                    <kbd className="inline-flex items-center rounded border border-border px-1 py-0.5 font-mono text-[10px] mr-1">
                                        ↑↓
                                    </kbd>
                                    Navigate
                                </span>
                                <span>
                                    <kbd className="inline-flex items-center rounded border border-border px-1 py-0.5 font-mono text-[10px] mr-1">
                                        Enter
                                    </kbd>
                                    Open
                                </span>
                                <span>
                                    <kbd className="inline-flex items-center rounded border border-border px-1 py-0.5 font-mono text-[10px] mr-1">
                                        Esc
                                    </kbd>
                                    Clear
                                </span>
                            </div>
                        </div>
                    </div>
                )}

                {/* Minimum character hint */}
                {query.length > 0 && query.length < 2 && (
                    <p className="text-sm text-muted-foreground text-center py-8">
                        Type at least 2 characters to search
                    </p>
                )}

                {/* Result count footer */}
                {showResults && (
                    <p className="text-xs text-muted-foreground/70 text-center pt-2">
                        {totalResults} result{totalResults !== 1 ? "s" : ""} for &quot;{debouncedQuery}&quot;
                    </p>
                )}
            </div>
        </div>
    );
}

// ---- Sub-components -----------------------------------------------------

function ResultSection({
    title,
    count,
    children,
}: {
    title: string;
    count: number;
    children: React.ReactNode;
}) {
    return (
        <div className="space-y-2">
            <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                    {title}
                </h2>
                <Badge variant="secondary" className="text-[10px]">
                    {count}
                </Badge>
            </div>
            <div className="space-y-1.5">{children}</div>
        </div>
    );
}

function ResultCard({
    children,
    selected,
    dataIndex,
    onClick,
}: {
    children: React.ReactNode;
    selected: boolean;
    dataIndex: number;
    onClick: () => void;
}) {
    return (
        <Card
            data-result-index={dataIndex}
            className={cn(
                "cursor-pointer transition-colors",
                selected
                    ? "border-primary/50 bg-primary/5"
                    : "hover:border-primary/30",
            )}
            onClick={onClick}
        >
            <CardContent className="py-3 px-4">{children}</CardContent>
        </Card>
    );
}

// ---- Inline SVG Icons (avoid extra dependency) --------------------------

function SearchIcon() {
    return (
        <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
        </svg>
    );
}

function XIcon() {
    return (
        <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <path d="M18 6 6 18" />
            <path d="m6 6 12 12" />
        </svg>
    );
}

function ClockIcon() {
    return (
        <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-muted-foreground/70"
        >
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
        </svg>
    );
}

function MagnifyingGlassIcon() {
    return (
        <svg
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="mx-auto"
        >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
        </svg>
    );
}
