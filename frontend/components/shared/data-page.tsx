// ---- DataPage Shell Component -------------------------------------------
// Reusable pattern for Phase 2 tabs: fetch list → search → paginate → create/edit/delete.
"use client";

import { useState, useMemo, type ReactNode } from "react";
import { type UseQueryResult } from "@tanstack/react-query";
import { useDebounce } from "@/hooks/use-debounce";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";

const DEFAULT_PAGE_SIZE = 25;

interface DataPageProps<T> {
    /** Page title */
    title: string;
    /** Optional subtitle */
    subtitle?: string;
    /** TanStack Query result */
    query: UseQueryResult<T[], Error>;
    /** Search filter function */
    searchFilter?: (item: T, search: string) => boolean;
    /** Search placeholder text */
    searchPlaceholder?: string;
    /** Render each item */
    renderItem: (item: T, index: number) => ReactNode;
    /** Render empty state (default provided) */
    renderEmpty?: () => ReactNode;
    /** "New" button label (null to hide) */
    createLabel?: string | null;
    /** Called when "New" button clicked */
    onCreateClick?: () => void;
    /** Extra actions in the header */
    headerActions?: ReactNode;
    /** Content rendered after the list (dialogs, etc.) */
    children?: ReactNode;
    /** Items per page (0 = no pagination) */
    pageSize?: number;
}

export function DataPage<T>({
    title,
    subtitle,
    query,
    searchFilter,
    searchPlaceholder = "Search...",
    renderItem,
    renderEmpty,
    createLabel = "New",
    onCreateClick,
    headerActions,
    children,
    pageSize = DEFAULT_PAGE_SIZE,
}: DataPageProps<T>) {
    const [search, setSearch] = useState("");
    const [page, setPage] = useState(0);
    const { data, isLoading, error } = query;

    const items = useMemo(() => data ?? [], [data]);
    const debouncedSearch = useDebounce(search, 300);
    const filtered = useMemo(
        () =>
            debouncedSearch && searchFilter
                ? items.filter((item) => searchFilter(item, debouncedSearch.toLowerCase()))
                : items,
        [items, debouncedSearch, searchFilter],
    );

    // Pagination
    const totalPages = pageSize > 0 ? Math.ceil(filtered.length / pageSize) : 1;
    const paged = pageSize > 0 ? filtered.slice(page * pageSize, (page + 1) * pageSize) : filtered;

    // Reset page when search changes
    const handleSearch = (value: string) => {
        setSearch(value);
        setPage(0);
    };

    return (
        <div className="space-y-5">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">{title}</h2>
                    {subtitle && (
                        <p className="text-sm text-muted-foreground mt-0.5">{subtitle}</p>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    {headerActions}
                    {createLabel && onCreateClick && (
                        <Button onClick={onCreateClick} size="sm" className="gap-1.5">
                            <span>+</span> {createLabel}
                        </Button>
                    )}
                </div>
            </div>

            {/* Search */}
            {searchFilter && (
                <div className="flex items-center gap-3">
                    <Input
                        placeholder={searchPlaceholder}
                        value={search}
                        onChange={(e) => handleSearch(e.target.value)}
                        className="max-w-sm"
                    />
                    {filtered.length !== items.length && (
                        <span className="text-xs text-muted-foreground">
                            {filtered.length} of {items.length}
                        </span>
                    )}
                </div>
            )}

            {/* Content */}
            {isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-20 w-full rounded-lg" />
                    ))}
                </div>
            ) : error ? (
                <Card className="border-destructive/50">
                    <CardContent className="py-8 text-center">
                        <p className="text-sm text-destructive">
                            Failed to load: {error.message}
                        </p>
                    </CardContent>
                </Card>
            ) : filtered.length === 0 ? (
                renderEmpty ? (
                    renderEmpty()
                ) : (
                    <Card className="border-dashed">
                        <CardContent className="py-16 text-center">
                            <div className="mx-auto w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-4 text-xl">
                                {search ? "🔍" : "📂"}
                            </div>
                            <p className="text-base font-medium text-foreground">
                                {search ? "No results found" : `No ${title.toLowerCase()} yet`}
                            </p>
                            <p className="text-sm text-muted-foreground mt-1.5 max-w-sm mx-auto">
                                {search
                                    ? "Try adjusting your search terms or clearing the filter."
                                    : createLabel && onCreateClick
                                        ? "Get started by creating your first entry."
                                        : "Items will appear here once added."}
                            </p>
                            {!search && createLabel && onCreateClick && (
                                <Button onClick={onCreateClick} size="sm" className="mt-4 gap-1.5">
                                    <span>+</span> {createLabel}
                                </Button>
                            )}
                        </CardContent>
                    </Card>
                )
            ) : (
                <div className="space-y-2">{paged.map(renderItem)}</div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-between pt-2 border-t border-border">
                    <p className="text-xs text-muted-foreground">
                        Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, filtered.length)} of {filtered.length}
                    </p>
                    <div className="flex items-center gap-1">
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={page === 0}
                            onClick={() => setPage((p) => p - 1)}
                        >
                            ← Prev
                        </Button>
                        <span className="text-xs text-muted-foreground px-2">
                            {page + 1} / {totalPages}
                        </span>
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={page >= totalPages - 1}
                            onClick={() => setPage((p) => p + 1)}
                        >
                            Next →
                        </Button>
                    </div>
                </div>
            )}

            {/* Extra content (dialogs, etc.) */}
            {children}
        </div>
    );
}
