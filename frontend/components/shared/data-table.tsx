// ---- DataTable Component -------------------------------------------------
// Sortable, filterable, paginated table for entity lists. Replaces manual
// table rendering across 20+ pages. Uses shadcn/ui primitives (Card, Input,
// Button, Skeleton) and the existing useDebounce hook.
//
// Features:
//   - Column-level sorting (click header to toggle asc/desc)
//   - Debounced text search via caller-provided searchFilter function
//   - Filter tabs (e.g., "All | Active | Archived")
//   - Pagination with configurable page size
//   - Loading skeleton and error states
//   - Optional row click handler and per-row action buttons
//   - Mobile-responsive column hiding (hideOnMobile)
//
// Usage:
//   <DataTable<Witness>
//       columns={[
//           { key: "name", header: "Name", render: (w) => w.name, sortValue: (w) => w.name },
//           { key: "type", header: "Type", render: (w) => <Badge>{w.type}</Badge>, sortValue: (w) => w.type },
//       ]}
//       data={witnesses}
//       isLoading={isLoading}
//       error={error}
//       searchFilter={(w, q) => w.name.toLowerCase().includes(q)}
//       searchPlaceholder="Search witnesses..."
//       rowKey={(w) => w.id}
//       onRowClick={(w) => router.push(`/witnesses/${w.id}`)}
//       rowActions={(w) => (
//           <Button size="icon" variant="ghost" onClick={() => remove.mutate(w.id)}>
//               <Trash2 className="h-4 w-4" />
//           </Button>
//       )}
//       pageSize={25}
//       defaultSortKey="name"
//   />
"use client";

import { useState, useMemo, type ReactNode } from "react";
import { useDebounce } from "@/hooks/use-debounce";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

// ---- Types ---------------------------------------------------------------

export interface Column<T> {
    /** Unique key for this column */
    key: string;
    /** Column header label */
    header: string;
    /** Extract the display value from a row. Return string or ReactNode. */
    render: (item: T) => ReactNode;
    /** Extract a sortable value (string or number). Omit to disable sort for this column. */
    sortValue?: (item: T) => string | number;
    /** Column width class (Tailwind). Defaults to auto. */
    className?: string;
    /** Hide on mobile */
    hideOnMobile?: boolean;
}

interface DataTableProps<T> {
    /** Column definitions */
    columns: Column<T>[];
    /** Data items to display */
    data: T[];
    /** Loading state */
    isLoading?: boolean;
    /** Error state */
    error?: Error | null;
    /** Search filter function -- if provided, shows search input */
    searchFilter?: (item: T, query: string) => boolean;
    /** Search placeholder */
    searchPlaceholder?: string;
    /** Get unique key for each row */
    rowKey: (item: T) => string;
    /** Called when a row is clicked (optional) */
    onRowClick?: (item: T) => void;
    /** Render actions for each row (e.g., edit/delete buttons) */
    rowActions?: (item: T) => ReactNode;
    /** Empty state message */
    emptyMessage?: string;
    /** Empty state with search active */
    emptySearchMessage?: string;
    /** Show table border */
    bordered?: boolean;
    /** Items per page (0 = no pagination) */
    pageSize?: number;
    /** Default sort column key */
    defaultSortKey?: string;
    /** Default sort direction */
    defaultSortDir?: "asc" | "desc";
    /** Filter tabs above the table */
    filterTabs?: { label: string; value: string }[];
    /** Current active filter tab */
    activeFilter?: string;
    /** Called when filter tab changes */
    onFilterChange?: (value: string) => void;
    /** Content rendered above the table (e.g., stats cards) */
    header?: ReactNode;
}

// ---- Component -----------------------------------------------------------

export function DataTable<T>({
    columns,
    data,
    isLoading = false,
    error = null,
    searchFilter,
    searchPlaceholder = "Search...",
    rowKey,
    onRowClick,
    rowActions,
    emptyMessage = "No items yet",
    emptySearchMessage = "No results match your search",
    bordered = true,
    pageSize = 0,
    defaultSortKey,
    defaultSortDir = "asc",
    filterTabs,
    activeFilter,
    onFilterChange,
    header,
}: DataTableProps<T>) {
    const [search, setSearch] = useState("");
    const [sortKey, setSortKey] = useState<string | null>(defaultSortKey ?? null);
    const [sortDir, setSortDir] = useState<"asc" | "desc">(defaultSortDir);
    const [page, setPage] = useState(0);

    const debouncedSearch = useDebounce(search, 250);

    // ---- Filter ----
    const filtered = useMemo(() => {
        if (!debouncedSearch || !searchFilter) return data;
        return data.filter((item) => searchFilter(item, debouncedSearch.toLowerCase()));
    }, [data, debouncedSearch, searchFilter]);

    // ---- Sort ----
    const sorted = useMemo(() => {
        if (!sortKey) return filtered;
        const col = columns.find((c) => c.key === sortKey);
        if (!col?.sortValue) return filtered;
        return [...filtered].sort((a, b) => {
            const av = col.sortValue!(a);
            const bv = col.sortValue!(b);
            const cmp = typeof av === "number" && typeof bv === "number"
                ? av - bv
                : String(av).localeCompare(String(bv));
            return sortDir === "asc" ? cmp : -cmp;
        });
    }, [filtered, sortKey, sortDir, columns]);

    // ---- Paginate ----
    const totalPages = pageSize > 0 ? Math.ceil(sorted.length / pageSize) : 1;
    const paged = pageSize > 0 ? sorted.slice(page * pageSize, (page + 1) * pageSize) : sorted;

    // Sort handler
    const handleSort = (key: string) => {
        const col = columns.find((c) => c.key === key);
        if (!col?.sortValue) return;
        if (sortKey === key) {
            setSortDir((d) => (d === "asc" ? "desc" : "asc"));
        } else {
            setSortKey(key);
            setSortDir("asc");
        }
        setPage(0);
    };

    // Sort indicator
    const sortIndicator = (key: string) => {
        if (sortKey !== key) return null;
        return <span className="ml-1 text-muted-foreground">{sortDir === "asc" ? "\u2191" : "\u2193"}</span>;
    };

    // ---- Loading State ----
    if (isLoading) {
        return (
            <div className="space-y-2">
                {header}
                {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 w-full rounded-lg" />
                ))}
            </div>
        );
    }

    // ---- Error State ----
    if (error) {
        return (
            <div className="space-y-4">
                {header}
                <Card className="border-destructive/50">
                    <CardContent className="py-8 text-center">
                        <p className="text-sm text-destructive">
                            Failed to load: {error.message}
                        </p>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="space-y-3">
            {header}

            {/* Search + Filter Row */}
            {(searchFilter || filterTabs) && (
                <div className="flex items-center gap-3 flex-wrap">
                    {searchFilter && (
                        <Input
                            placeholder={searchPlaceholder}
                            value={search}
                            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
                            className="max-w-sm"
                        />
                    )}
                    {filterTabs && (
                        <div className="flex gap-1">
                            {filterTabs.map((tab) => (
                                <Button
                                    key={tab.value}
                                    variant={activeFilter === tab.value ? "default" : "outline"}
                                    size="sm"
                                    className="h-8 text-xs"
                                    onClick={() => onFilterChange?.(tab.value)}
                                >
                                    {tab.label}
                                </Button>
                            ))}
                        </div>
                    )}
                    {debouncedSearch && filtered.length !== data.length && (
                        <span className="text-xs text-muted-foreground">
                            {filtered.length} of {data.length}
                        </span>
                    )}
                </div>
            )}

            {/* Empty State */}
            {sorted.length === 0 ? (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        {debouncedSearch ? emptySearchMessage : emptyMessage}
                    </CardContent>
                </Card>
            ) : (
                /* Table */
                <div className={bordered ? "rounded-lg border border-border overflow-hidden" : ""}>
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-border bg-muted/30">
                                {columns.map((col) => (
                                    <th
                                        key={col.key}
                                        className={`px-3 py-2.5 text-left font-medium text-muted-foreground ${
                                            col.sortValue ? "cursor-pointer hover:text-foreground select-none" : ""
                                        } ${col.hideOnMobile ? "hidden md:table-cell" : ""} ${col.className ?? ""}`}
                                        onClick={() => handleSort(col.key)}
                                    >
                                        {col.header}
                                        {sortIndicator(col.key)}
                                    </th>
                                ))}
                                {rowActions && (
                                    <th className="px-3 py-2.5 text-right font-medium text-muted-foreground w-[1%] whitespace-nowrap">
                                        Actions
                                    </th>
                                )}
                            </tr>
                        </thead>
                        <tbody>
                            {paged.map((item) => (
                                <tr
                                    key={rowKey(item)}
                                    className={`border-b border-border last:border-0 transition-colors ${
                                        onRowClick ? "cursor-pointer hover:bg-accent/30" : "hover:bg-accent/10"
                                    }`}
                                    onClick={() => onRowClick?.(item)}
                                >
                                    {columns.map((col) => (
                                        <td
                                            key={col.key}
                                            className={`px-3 py-2.5 ${col.hideOnMobile ? "hidden md:table-cell" : ""} ${col.className ?? ""}`}
                                        >
                                            {col.render(item)}
                                        </td>
                                    ))}
                                    {rowActions && (
                                        <td className="px-3 py-2.5 text-right whitespace-nowrap">
                                            <div
                                                className="flex items-center justify-end gap-1"
                                                onClick={(e) => e.stopPropagation()}
                                            >
                                                {rowActions(item)}
                                            </div>
                                        </td>
                                    )}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-between pt-1">
                    <p className="text-xs text-muted-foreground">
                        {page * pageSize + 1}&ndash;{Math.min((page + 1) * pageSize, sorted.length)} of {sorted.length}
                    </p>
                    <div className="flex items-center gap-1">
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={page === 0}
                            onClick={() => setPage((p) => p - 1)}
                        >
                            Prev
                        </Button>
                        <span className="text-xs text-muted-foreground px-2">
                            {page + 1}/{totalPages}
                        </span>
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={page >= totalPages - 1}
                            onClick={() => setPage((p) => p + 1)}
                        >
                            Next
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
