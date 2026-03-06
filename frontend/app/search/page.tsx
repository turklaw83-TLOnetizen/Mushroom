// ---- Global Search Page --------------------------------------------------
// Cross-entity search across cases, clients, and tasks.
// Supports optional in-case filtering via case dropdown.
"use client";

import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

interface CaseResult {
    id: string;
    name: string;
    case_type: string;
    phase: string;
    client_name?: string;
}

interface ClientResult {
    id: string;
    name: string;
    email: string;
    phone?: string;
    company?: string;
}

interface TaskResult {
    id: string;
    title: string;
    status: string;
    priority: string;
    case_id?: string;
    case_name?: string;
}

interface SearchResponse {
    cases: CaseResult[];
    clients: ClientResult[];
    tasks: TaskResult[];
}

interface CaseListItem {
    id: string;
    name: string;
}

const priorityColor: Record<string, string> = {
    high: "text-red-400 border-red-400/30",
    medium: "text-amber-400 border-amber-400/30",
    low: "text-green-400 border-green-400/30",
};

const statusColor: Record<string, string> = {
    pending: "text-amber-400 border-amber-400/30",
    in_progress: "text-blue-400 border-blue-400/30",
    completed: "text-green-400 border-green-400/30",
};

export default function SearchPage() {
    return (
        <Suspense fallback={<div className="p-6 md:p-8 max-w-5xl mx-auto"><Skeleton className="h-12 w-full max-w-2xl" /></div>}>
            <SearchPageInner />
        </Suspense>
    );
}

function SearchPageInner() {
    const { getToken } = useAuth();
    const searchParams = useSearchParams();
    const router = useRouter();

    const queryParam = searchParams.get("q") ?? "";
    const [input, setInput] = useState(queryParam);
    const [debouncedQuery, setDebouncedQuery] = useState(queryParam);
    const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);

    // Fetch case list for filter dropdown
    const { data: casesList } = useQuery({
        queryKey: ["cases-list"],
        queryFn: () => api.get<CaseListItem[]>("/cases", { getToken }),
    });

    // Debounce input by 300ms and sync to URL
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedQuery(input);
            const url = input ? `/search?q=${encodeURIComponent(input)}` : "/search";
            router.replace(url, { scroll: false });
        }, 300);
        return () => clearTimeout(timer);
    }, [input, router]);

    // Sync from URL on navigation (e.g. back button)
    useEffect(() => {
        setInput(queryParam);
        setDebouncedQuery(queryParam);
    }, [queryParam]);

    // Switch between global search and in-case search based on filter
    const searchPath = selectedCaseId
        ? `/search/case/${selectedCaseId}`
        : "/search";

    const { data, isLoading } = useQuery({
        queryKey: ["global-search", debouncedQuery, selectedCaseId],
        queryFn: () =>
            api.get<SearchResponse>(searchPath, {
                params: { q: debouncedQuery },
                getToken,
            }),
        enabled: !!debouncedQuery,
    });

    // Derive selected case name for badge
    const selectedCaseName = selectedCaseId
        ? casesList?.find((c) => c.id === selectedCaseId)?.name ?? selectedCaseId
        : null;

    const cases = data?.cases ?? [];
    const clients = data?.clients ?? [];
    const tasks = data?.tasks ?? [];
    const hasResults = cases.length > 0 || clients.length > 0 || tasks.length > 0;
    const hasQuery = !!debouncedQuery;

    return (
        <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Search</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Search across cases, clients, and tasks
                </p>
            </div>

            <div className="flex items-center gap-3 max-w-2xl">
                <Input
                    placeholder="Type to search cases, clients, tasks..."
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    className="flex-1 text-base h-12"
                    autoFocus
                />
                <Select
                    value={selectedCaseId ?? "all"}
                    onValueChange={(v) => setSelectedCaseId(v === "all" ? null : v)}
                >
                    <SelectTrigger className="h-12 min-w-[180px]">
                        <SelectValue placeholder="All Cases" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Cases</SelectItem>
                        {casesList?.map((c) => (
                            <SelectItem key={c.id} value={c.id}>
                                {c.name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {selectedCaseName && (
                <Badge variant="secondary" className="text-xs">
                    Searching in: {selectedCaseName}
                </Badge>
            )}

            {/* Loading state */}
            {isLoading && hasQuery && (
                <div className="space-y-6">
                    {Array.from({ length: 3 }).map((_, i) => (
                        <div key={i} className="space-y-3">
                            <Skeleton className="h-6 w-24" />
                            <Skeleton className="h-16 w-full rounded-lg" />
                            <Skeleton className="h-16 w-full rounded-lg" />
                        </div>
                    ))}
                </div>
            )}

            {/* Empty state: no query entered */}
            {!hasQuery && !isLoading && (
                <Card className="border-dashed">
                    <CardContent className="py-16 text-center text-muted-foreground">
                        Start typing to search across your entire workspace.
                    </CardContent>
                </Card>
            )}

            {/* No results state */}
            {hasQuery && !isLoading && !hasResults && (
                <Card className="border-dashed">
                    <CardContent className="py-16 text-center text-muted-foreground">
                        No results found for &ldquo;{debouncedQuery}&rdquo;
                    </CardContent>
                </Card>
            )}

            {/* Results */}
            {hasQuery && !isLoading && hasResults && (
                <div className="space-y-8">
                    {/* Cases */}
                    {cases.length > 0 && (
                        <section>
                            <div className="flex items-center gap-2 mb-3">
                                <h2 className="text-lg font-semibold">Cases</h2>
                                <Badge variant="secondary" className="text-xs">
                                    {cases.length}
                                </Badge>
                            </div>
                            <div className="space-y-2">
                                {cases.map((c) => (
                                    <Link key={c.id} href={`/cases/${c.id}`}>
                                        <Card className="hover:bg-accent/30 transition-colors cursor-pointer">
                                            <CardContent className="py-3 flex items-center justify-between">
                                                <div>
                                                    <p className="text-sm font-medium">{c.name}</p>
                                                    {c.client_name && (
                                                        <p className="text-xs text-muted-foreground mt-0.5">
                                                            Client: {c.client_name}
                                                        </p>
                                                    )}
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    {c.case_type && (
                                                        <Badge variant="outline" className="text-[10px]">
                                                            {c.case_type}
                                                        </Badge>
                                                    )}
                                                    {c.phase && (
                                                        <Badge variant="secondary" className="text-[10px]">
                                                            {c.phase}
                                                        </Badge>
                                                    )}
                                                </div>
                                            </CardContent>
                                        </Card>
                                    </Link>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* Clients */}
                    {clients.length > 0 && (
                        <section>
                            <div className="flex items-center gap-2 mb-3">
                                <h2 className="text-lg font-semibold">Clients</h2>
                                <Badge variant="secondary" className="text-xs">
                                    {clients.length}
                                </Badge>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {clients.map((client) => (
                                    <Card key={client.id} className="hover:border-primary/30 transition-colors">
                                        <CardContent className="py-3">
                                            <p className="text-sm font-medium">{client.name}</p>
                                            {client.email && (
                                                <p className="text-xs text-muted-foreground mt-0.5">
                                                    {client.email}
                                                </p>
                                            )}
                                            {client.phone && (
                                                <p className="text-xs text-muted-foreground">
                                                    {client.phone}
                                                </p>
                                            )}
                                            {client.company && (
                                                <Badge variant="outline" className="text-[10px] mt-1">
                                                    {client.company}
                                                </Badge>
                                            )}
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* Tasks */}
                    {tasks.length > 0 && (
                        <section>
                            <div className="flex items-center gap-2 mb-3">
                                <h2 className="text-lg font-semibold">Tasks</h2>
                                <Badge variant="secondary" className="text-xs">
                                    {tasks.length}
                                </Badge>
                            </div>
                            <div className="space-y-2">
                                {tasks.map((task) => (
                                    <Card key={task.id} className="hover:bg-accent/30 transition-colors">
                                        <CardContent className="py-3">
                                            <div className="flex items-center justify-between">
                                                <p className="text-sm font-medium">{task.title}</p>
                                                <div className="flex items-center gap-2">
                                                    {task.priority && (
                                                        <Badge
                                                            variant="outline"
                                                            className={`text-[10px] ${priorityColor[task.priority] || ""}`}
                                                        >
                                                            {task.priority}
                                                        </Badge>
                                                    )}
                                                    {task.status && (
                                                        <Badge
                                                            variant="outline"
                                                            className={`text-[10px] ${statusColor[task.status] || ""}`}
                                                        >
                                                            {task.status.replace("_", " ")}
                                                        </Badge>
                                                    )}
                                                </div>
                                            </div>
                                            {task.case_name && (
                                                <p className="text-xs text-muted-foreground mt-0.5">
                                                    Case: {task.case_name}
                                                </p>
                                            )}
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        </section>
                    )}
                </div>
            )}
        </div>
    );
}
