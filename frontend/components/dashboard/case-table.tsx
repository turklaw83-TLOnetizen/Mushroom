// ---- Case Table ---------------------------------------------------------
// Sortable columns, pin toggle, bulk actions, readiness badges, deadlines.
"use client";

import { useState, useCallback, useMemo } from "react";
import type { CaseItem } from "@/hooks/use-cases";
import { useAuth } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";

const phaseColors: Record<string, string> = {
    active: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    closed: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    archived: "bg-amber-500/15 text-amber-400 border-amber-500/30",
};

const AVAILABLE_PHASES = ["active", "closed", "archived"];

function formatDate(iso: string): string {
    if (!iso) return "\u2014";
    try {
        return new Date(iso).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    } catch {
        return iso;
    }
}

// ---- Readiness badge ----------------------------------------------------

const readinessColors = {
    green: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    amber: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    red: "bg-red-500/15 text-red-400 border-red-500/30",
} as const;

function readinessColor(score: number): string {
    if (score >= 80) return readinessColors.green;
    if (score >= 50) return readinessColors.amber;
    return readinessColors.red;
}

function ReadinessBadge({ score, grade }: { score?: number; grade?: string }) {
    if (score == null) return <span className="text-muted-foreground">{"\u2014"}</span>;
    const label = grade ? `${score} (${grade})` : `${score}`;
    return (
        <Badge variant="outline" className={readinessColor(score)}>
            {label}
        </Badge>
    );
}

// ---- Deadline display ---------------------------------------------------

function formatRelativeDeadline(iso?: string): { text: string; urgency: "overdue" | "soon" | "normal" } | null {
    if (!iso) return null;
    try {
        const deadline = new Date(iso);
        if (isNaN(deadline.getTime())) return null;
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const target = new Date(deadline.getFullYear(), deadline.getMonth(), deadline.getDate());
        const diffMs = target.getTime() - today.getTime();
        const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

        if (diffDays < 0) {
            const absDays = Math.abs(diffDays);
            return {
                text: absDays === 1 ? "1 day overdue" : `${absDays} days overdue`,
                urgency: "overdue",
            };
        }
        if (diffDays === 0) return { text: "today", urgency: "soon" };
        if (diffDays === 1) return { text: "tomorrow", urgency: "soon" };
        if (diffDays <= 7) return { text: `in ${diffDays} days`, urgency: "soon" };
        if (diffDays <= 30) return { text: `in ${diffDays} days`, urgency: "normal" };
        return { text: formatDate(iso), urgency: "normal" };
    } catch {
        return null;
    }
}

const deadlineColors: Record<string, string> = {
    overdue: "text-red-400",
    soon: "text-amber-400",
    normal: "text-muted-foreground",
};

function DeadlineCell({ deadline, event }: { deadline?: string; event?: string }) {
    const source = deadline || event;
    const result = formatRelativeDeadline(source);
    if (!result) return <span className="text-muted-foreground">{"\u2014"}</span>;
    return <span className={`text-sm font-medium ${deadlineColors[result.urgency]}`}>{result.text}</span>;
}

// ---- Sorting ------------------------------------------------------------

type SortKey = "name" | "client_name" | "case_category" | "phase" | "readiness_score" | "next_deadline" | "last_updated" | "pinned";
type SortDir = "asc" | "desc";

function SortableHeader({
    label,
    sortKey,
    currentSort,
    currentDir,
    onSort,
    className,
}: {
    label: string;
    sortKey: SortKey;
    currentSort: SortKey;
    currentDir: SortDir;
    onSort: (key: SortKey) => void;
    className?: string;
}) {
    const isActive = currentSort === sortKey;
    const arrow = isActive ? (currentDir === "asc" ? " \u25B2" : " \u25BC") : "";
    return (
        <TableHead
            className={`font-semibold cursor-pointer select-none hover:text-foreground transition-colors ${className || ""}`}
            onClick={() => onSort(sortKey)}
        >
            {label}{arrow}
        </TableHead>
    );
}

function sortCases(cases: CaseItem[], sortKey: SortKey, sortDir: SortDir): CaseItem[] {
    const sorted = [...cases].sort((a, b) => {
        let aVal: string | number | boolean;
        let bVal: string | number | boolean;

        switch (sortKey) {
            case "name":
                aVal = a.name.toLowerCase();
                bVal = b.name.toLowerCase();
                break;
            case "client_name":
                aVal = (a.client_name || "").toLowerCase();
                bVal = (b.client_name || "").toLowerCase();
                break;
            case "case_category":
                aVal = (a.case_category || a.case_type || "").toLowerCase();
                bVal = (b.case_category || b.case_type || "").toLowerCase();
                break;
            case "phase":
                aVal = a.phase;
                bVal = b.phase;
                break;
            case "readiness_score":
                aVal = a.readiness_score ?? -1;
                bVal = b.readiness_score ?? -1;
                break;
            case "next_deadline":
                aVal = a.next_deadline || a.next_event || "9999";
                bVal = b.next_deadline || b.next_event || "9999";
                break;
            case "last_updated":
                aVal = a.last_updated || "";
                bVal = b.last_updated || "";
                break;
            case "pinned":
                aVal = a.pinned ? 1 : 0;
                bVal = b.pinned ? 1 : 0;
                break;
            default:
                return 0;
        }

        if (aVal < bVal) return sortDir === "asc" ? -1 : 1;
        if (aVal > bVal) return sortDir === "asc" ? 1 : -1;
        return 0;
    });

    // Always put pinned cases first regardless of sort
    const pinned = sorted.filter((c) => c.pinned);
    const unpinned = sorted.filter((c) => !c.pinned);
    return [...pinned, ...unpinned];
}

// ---- Floating Action Bar ------------------------------------------------

function BulkActionBar({
    selectedCount,
    onExport,
    onDelete,
    onChangePhase,
    onClear,
    isExporting,
    isDeleting,
    isChangingPhase,
}: {
    selectedCount: number;
    onExport: () => void;
    onDelete: () => void;
    onChangePhase: (phase: string) => void;
    onClear: () => void;
    isExporting: boolean;
    isDeleting: boolean;
    isChangingPhase: boolean;
}) {
    const [phaseDropdownOpen, setPhaseDropdownOpen] = useState(false);

    return (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 bg-card border border-border rounded-xl shadow-2xl px-5 py-3 flex items-center gap-4 animate-in slide-in-from-bottom-4 duration-200">
            <span className="text-sm font-medium whitespace-nowrap">
                {selectedCount} selected
            </span>
            <div className="h-5 w-px bg-border" />
            <Button
                size="sm"
                variant="outline"
                onClick={onExport}
                disabled={isExporting}
            >
                {isExporting ? "Exporting..." : "Export All"}
            </Button>
            <div className="relative">
                <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setPhaseDropdownOpen((v) => !v)}
                    disabled={isChangingPhase}
                >
                    {isChangingPhase ? "Updating..." : "Change Phase"}
                </Button>
                {phaseDropdownOpen && (
                    <div className="absolute bottom-full mb-1 left-0 bg-popover border border-border rounded-lg shadow-lg py-1 min-w-[120px]">
                        {AVAILABLE_PHASES.map((phase) => (
                            <button
                                key={phase}
                                className="w-full text-left px-3 py-1.5 text-sm hover:bg-accent capitalize"
                                onClick={() => {
                                    setPhaseDropdownOpen(false);
                                    onChangePhase(phase);
                                }}
                            >
                                {phase}
                            </button>
                        ))}
                    </div>
                )}
            </div>
            <Button
                size="sm"
                variant="destructive"
                onClick={onDelete}
                disabled={isDeleting}
            >
                {isDeleting ? "Deleting..." : "Delete Selected"}
            </Button>
            <div className="h-5 w-px bg-border" />
            <Button
                size="sm"
                variant="ghost"
                className="text-xs"
                onClick={onClear}
            >
                Clear
            </Button>
        </div>
    );
}

// ---- Table component ----------------------------------------------------

export function CaseTable({
    cases,
    onRowClick,
    onDelete,
}: {
    cases: CaseItem[];
    onRowClick: (c: CaseItem) => void;
    onDelete?: (c: CaseItem) => void;
}) {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
    const [sortKey, setSortKey] = useState<SortKey>("last_updated");
    const [sortDir, setSortDir] = useState<SortDir>("desc");

    const handleSort = useCallback((key: SortKey) => {
        setSortKey((prev) => {
            if (prev === key) {
                setSortDir((d) => (d === "asc" ? "desc" : "asc"));
                return key;
            }
            setSortDir(key === "last_updated" || key === "readiness_score" ? "desc" : "asc");
            return key;
        });
    }, []);

    const sortedCases = useMemo(() => sortCases(cases, sortKey, sortDir), [cases, sortKey, sortDir]);

    const allSelected = cases.length > 0 && selectedIds.size === cases.length;
    const someSelected = selectedIds.size > 0 && selectedIds.size < cases.length;

    const toggleAll = useCallback(() => {
        if (allSelected) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(cases.map((c) => c.id)));
        }
    }, [allSelected, cases]);

    const toggleOne = useCallback((id: string) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    }, []);

    const clearSelection = useCallback(() => setSelectedIds(new Set()), []);

    const togglePin = useCallback(async (c: CaseItem, e: React.MouseEvent) => {
        e.stopPropagation();
        try {
            await api.patch(`/cases/${c.id}`, { pinned: !c.pinned }, { getToken });
            queryClient.invalidateQueries({ queryKey: ["cases"] });
            toast.success(c.pinned ? "Unpinned" : "Pinned", { description: c.name });
        } catch {
            toast.error("Failed to update pin status");
        }
    }, [getToken, queryClient]);

    const selectedCaseIds = Array.from(selectedIds);

    // Bulk export mutation
    const bulkExport = useMutationWithToast({
        mutationFn: () =>
            api.post("/batch/cases/export", {
                case_ids: selectedCaseIds,
                format: "csv",
            }, { getToken }),
        successMessage: `Export started for ${selectedIds.size} case(s)`,
        errorMessage: "Bulk export failed",
    });

    // Bulk status/phase update mutation
    const bulkChangePhase = useMutationWithToast({
        mutationFn: (newStatus: string) =>
            api.post("/batch/cases/status", {
                case_ids: selectedCaseIds,
                new_status: newStatus,
            }, { getToken }),
        successMessage: "Phase updated for selected cases",
        errorMessage: "Bulk phase update failed",
        invalidateKeys: [["cases"]],
        onSuccess: () => clearSelection(),
    });

    // Bulk archive
    const bulkDelete = useMutationWithToast({
        mutationFn: () =>
            api.post("/batch/cases/archive", {
                case_ids: selectedCaseIds,
                new_status: "archived",
                reason: "Bulk delete from dashboard",
            }, { getToken }),
        successMessage: `${selectedIds.size} case(s) archived`,
        errorMessage: "Bulk delete failed",
        invalidateKeys: [["cases"]],
        onSuccess: () => {
            clearSelection();
            setDeleteConfirmOpen(false);
        },
    });

    if (cases.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-16">
                <p className="text-lg font-medium text-muted-foreground">No cases found</p>
                <p className="text-sm text-muted-foreground mt-1">
                    Create your first case to get started.
                </p>
            </div>
        );
    }

    return (
        <>
            <div className="rounded-lg border border-border overflow-hidden">
                <Table>
                    <TableHeader>
                        <TableRow className="bg-muted/50 hover:bg-muted/50">
                            <TableHead className="w-10">
                                <input
                                    type="checkbox"
                                    checked={allSelected}
                                    ref={(el) => {
                                        if (el) el.indeterminate = someSelected;
                                    }}
                                    onChange={toggleAll}
                                    className="rounded border-border accent-primary cursor-pointer"
                                    aria-label="Select all cases"
                                />
                            </TableHead>
                            <TableHead className="w-8" />
                            <SortableHeader label="Case Name" sortKey="name" currentSort={sortKey} currentDir={sortDir} onSort={handleSort} />
                            <SortableHeader label="Client" sortKey="client_name" currentSort={sortKey} currentDir={sortDir} onSort={handleSort} className="hidden md:table-cell" />
                            <SortableHeader label="Category" sortKey="case_category" currentSort={sortKey} currentDir={sortDir} onSort={handleSort} className="hidden lg:table-cell" />
                            <SortableHeader label="Phase" sortKey="phase" currentSort={sortKey} currentDir={sortDir} onSort={handleSort} />
                            <SortableHeader label="Readiness" sortKey="readiness_score" currentSort={sortKey} currentDir={sortDir} onSort={handleSort} className="hidden md:table-cell" />
                            <SortableHeader label="Next Deadline" sortKey="next_deadline" currentSort={sortKey} currentDir={sortDir} onSort={handleSort} className="hidden lg:table-cell" />
                            <SortableHeader label="Updated" sortKey="last_updated" currentSort={sortKey} currentDir={sortDir} onSort={handleSort} className="text-right hidden sm:table-cell" />
                            {onDelete && <TableHead className="w-10" />}
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {sortedCases.map((c) => {
                            const isSelected = selectedIds.has(c.id);
                            return (
                                <TableRow
                                    key={c.id}
                                    onClick={() => onRowClick(c)}
                                    className={`cursor-pointer transition-colors group ${
                                        isSelected
                                            ? "bg-primary/5 hover:bg-primary/10"
                                            : "hover:bg-accent/50"
                                    }`}
                                >
                                    <TableCell>
                                        <input
                                            type="checkbox"
                                            checked={isSelected}
                                            onChange={(e) => {
                                                e.stopPropagation();
                                                toggleOne(c.id);
                                            }}
                                            onClick={(e) => e.stopPropagation()}
                                            className="rounded border-border accent-primary cursor-pointer"
                                            aria-label={`Select ${c.name}`}
                                        />
                                    </TableCell>
                                    <TableCell className="px-0">
                                        <button
                                            onClick={(e) => togglePin(c, e)}
                                            className={`text-base transition-colors ${c.pinned ? "text-amber-400" : "text-muted-foreground/30 hover:text-muted-foreground"}`}
                                            title={c.pinned ? "Unpin case" : "Pin case"}
                                        >
                                            {c.pinned ? "\u2605" : "\u2606"}
                                        </button>
                                    </TableCell>
                                    <TableCell className="font-medium">{c.name}</TableCell>
                                    <TableCell className="text-muted-foreground hidden md:table-cell">
                                        {c.client_name || "\u2014"}
                                    </TableCell>
                                    <TableCell className="text-muted-foreground hidden lg:table-cell">
                                        {c.case_category || c.case_type || "\u2014"}
                                    </TableCell>
                                    <TableCell>
                                        <Badge
                                            variant="outline"
                                            className={phaseColors[c.phase] || phaseColors.active}
                                        >
                                            {c.phase}
                                            {c.sub_phase && ` / ${c.sub_phase}`}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="hidden md:table-cell">
                                        <ReadinessBadge score={c.readiness_score} grade={c.readiness_grade} />
                                    </TableCell>
                                    <TableCell className="hidden lg:table-cell">
                                        <DeadlineCell deadline={c.next_deadline} event={c.next_event} />
                                    </TableCell>
                                    <TableCell className="text-right text-muted-foreground text-sm hidden sm:table-cell">
                                        {formatDate(c.last_updated)}
                                    </TableCell>
                                    {onDelete && (
                                        <TableCell>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    onDelete(c);
                                                }}
                                            >
                                                {"\u2715"}
                                            </Button>
                                        </TableCell>
                                    )}
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </div>

            {/* Floating Bulk Action Bar */}
            {selectedIds.size > 0 && (
                <BulkActionBar
                    selectedCount={selectedIds.size}
                    onExport={() => bulkExport.mutate({})}
                    onDelete={() => setDeleteConfirmOpen(true)}
                    onChangePhase={(phase) => bulkChangePhase.mutate(phase)}
                    onClear={clearSelection}
                    isExporting={bulkExport.isPending}
                    isDeleting={bulkDelete.isPending}
                    isChangingPhase={bulkChangePhase.isPending}
                />
            )}

            {/* Bulk Delete Confirmation */}
            <ConfirmDialog
                open={deleteConfirmOpen}
                onOpenChange={setDeleteConfirmOpen}
                title={`Archive ${selectedIds.size} case(s)?`}
                description={`This will archive ${selectedIds.size} selected case(s). You can restore archived cases later from the archive view.`}
                confirmLabel="Archive All"
                onConfirm={() => bulkDelete.mutate({})}
                isLoading={bulkDelete.isPending}
                variant="destructive"
            />
        </>
    );
}
