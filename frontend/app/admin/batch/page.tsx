"use client";
// ---- Batch Operations Page -----------------------------------------------
// Bulk status update, assign, export, and archive for multiple cases.
export const dynamic = "force-dynamic";

import { useState, useMemo, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";

// ---- Types ----------------------------------------------------------------

interface CaseListItem {
    id: string;
    name: string;
    status: string;
    phase: string;
    client_name: string;
}

interface PaginatedCases {
    items: CaseListItem[];
    total: number;
}

interface BatchResult {
    status: string;
    message: string;
    affected?: number;
    download_url?: string;
}

// ---- Main Page ------------------------------------------------------------

export default function BatchPage() {
    const { getToken } = useAuth();
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [statusValue, setStatusValue] = useState("active");
    const [reasonValue, setReasonValue] = useState("");
    const [assigneeValue, setAssigneeValue] = useState("");
    const [exportFormat, setExportFormat] = useState("csv");
    const [exportResult, setExportResult] = useState<BatchResult | null>(null);

    // Fetch all cases
    const casesQuery = useQuery({
        queryKey: ["batch-cases"],
        queryFn: () =>
            api.get<PaginatedCases>("/cases", {
                params: { per_page: 500, include_archived: true },
                getToken,
            }),
    });

    const cases = casesQuery.data?.items ?? [];
    const selectedCount = selected.size;

    const toggleCase = useCallback((caseId: string) => {
        setSelected((prev) => {
            const next = new Set(prev);
            if (next.has(caseId)) {
                next.delete(caseId);
            } else {
                next.add(caseId);
            }
            return next;
        });
    }, []);

    const selectAll = useCallback(() => {
        setSelected(new Set(cases.map((c) => c.id)));
    }, [cases]);

    const selectNone = useCallback(() => {
        setSelected(new Set());
    }, []);

    const selectedIds = useMemo(() => Array.from(selected), [selected]);

    // Bulk status update
    const bulkStatus = useMutationWithToast<void, BatchResult>({
        mutationFn: () =>
            api.post<BatchResult>("/batch/cases/status", {
                case_ids: selectedIds,
                status: statusValue,
                reason: reasonValue,
            }, { getToken }),
        successMessage: "Status updated for selected cases",
        errorMessage: "Bulk status update failed",
        invalidateKeys: [["batch-cases"], ["cases"]],
    });

    // Bulk assign
    const bulkAssign = useMutationWithToast<void, BatchResult>({
        mutationFn: () =>
            api.post<BatchResult>("/batch/cases/assign", {
                case_ids: selectedIds,
                assignee: assigneeValue,
            }, { getToken }),
        successMessage: "Cases assigned successfully",
        errorMessage: "Bulk assignment failed",
        invalidateKeys: [["batch-cases"], ["cases"]],
    });

    // Bulk export
    const bulkExport = useMutationWithToast<void, BatchResult>({
        mutationFn: () =>
            api.post<BatchResult>("/batch/cases/export", {
                case_ids: selectedIds,
                format: exportFormat,
            }, { getToken }),
        successMessage: "Export generated",
        errorMessage: "Bulk export failed",
        onSuccess: (result) => setExportResult(result),
    });

    // Bulk archive
    const bulkArchive = useMutationWithToast<void, BatchResult>({
        mutationFn: () =>
            api.post<BatchResult>("/batch/cases/archive", {
                case_ids: selectedIds,
            }, { getToken }),
        successMessage: "Cases archived successfully",
        errorMessage: "Bulk archive failed",
        invalidateKeys: [["batch-cases"], ["cases"]],
        onSuccess: () => setSelected(new Set()),
    });

    return (
        <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Batch Operations</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Bulk actions across multiple cases
                    </p>
                </div>
                {selectedCount > 0 && (
                    <Badge className="text-sm px-3 py-1">
                        {selectedCount} case{selectedCount !== 1 ? "s" : ""} selected
                    </Badge>
                )}
            </div>

            {/* Case Selection */}
            <Card>
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-base">Select Cases</CardTitle>
                        <div className="flex gap-2">
                            <Button size="sm" variant="outline" onClick={selectAll}>
                                Select All
                            </Button>
                            <Button size="sm" variant="outline" onClick={selectNone}>
                                Select None
                            </Button>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    {casesQuery.isLoading ? (
                        <div className="space-y-2">
                            {Array.from({ length: 5 }).map((_, i) => (
                                <Skeleton key={i} className="h-10 w-full" />
                            ))}
                        </div>
                    ) : cases.length === 0 ? (
                        <p className="text-sm text-muted-foreground py-4">No cases found.</p>
                    ) : (
                        <div className="max-h-80 overflow-y-auto divide-y">
                            {cases.map((c) => (
                                <label
                                    key={c.id}
                                    className="flex items-center gap-3 py-2.5 px-1 cursor-pointer hover:bg-accent/30 rounded-sm transition-colors"
                                >
                                    <Checkbox
                                        checked={selected.has(c.id)}
                                        onCheckedChange={() => toggleCase(c.id)}
                                    />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium truncate">{c.name}</p>
                                        <p className="text-xs text-muted-foreground">
                                            {c.client_name || "No client"} · {c.id.slice(0, 8)}
                                        </p>
                                    </div>
                                    <Badge variant="outline" className="text-xs capitalize shrink-0">
                                        {c.phase || c.status || "unknown"}
                                    </Badge>
                                </label>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Operation Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* 1. Bulk Status Update */}
                <Card className={cn(selectedCount === 0 && "opacity-50 pointer-events-none")}>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Bulk Status Update</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="space-y-2">
                            <label className="text-xs font-medium text-muted-foreground">New Status</label>
                            <Select value={statusValue} onValueChange={setStatusValue}>
                                <SelectTrigger className="w-full h-9 text-sm">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="active">Active</SelectItem>
                                    <SelectItem value="closed">Closed</SelectItem>
                                    <SelectItem value="archived">Archived</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-medium text-muted-foreground">Reason (optional)</label>
                            <Input
                                placeholder="Reason for status change..."
                                value={reasonValue}
                                onChange={(e) => setReasonValue(e.target.value)}
                            />
                        </div>
                        <Button
                            size="sm"
                            onClick={() => bulkStatus.mutate()}
                            disabled={selectedCount === 0 || bulkStatus.isPending}
                        >
                            {bulkStatus.isPending ? "Updating..." : "Update Status"}
                        </Button>
                    </CardContent>
                </Card>

                {/* 2. Bulk Assign */}
                <Card className={cn(selectedCount === 0 && "opacity-50 pointer-events-none")}>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Bulk Assign</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="space-y-2">
                            <label className="text-xs font-medium text-muted-foreground">Assignee</label>
                            <Input
                                placeholder="Attorney name or user ID..."
                                value={assigneeValue}
                                onChange={(e) => setAssigneeValue(e.target.value)}
                            />
                        </div>
                        <Button
                            size="sm"
                            onClick={() => bulkAssign.mutate()}
                            disabled={selectedCount === 0 || !assigneeValue.trim() || bulkAssign.isPending}
                        >
                            {bulkAssign.isPending ? "Assigning..." : "Assign Cases"}
                        </Button>
                    </CardContent>
                </Card>

                {/* 3. Bulk Export */}
                <Card className={cn(selectedCount === 0 && "opacity-50 pointer-events-none")}>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Bulk Export</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="space-y-2">
                            <label className="text-xs font-medium text-muted-foreground">Export Format</label>
                            <Select value={exportFormat} onValueChange={setExportFormat}>
                                <SelectTrigger className="w-full h-9 text-sm">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="csv">CSV</SelectItem>
                                    <SelectItem value="json">JSON</SelectItem>
                                    <SelectItem value="xlsx">Excel (XLSX)</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <Button
                            size="sm"
                            onClick={() => bulkExport.mutate()}
                            disabled={selectedCount === 0 || bulkExport.isPending}
                        >
                            {bulkExport.isPending ? "Exporting..." : "Export Cases"}
                        </Button>
                        {exportResult?.download_url && (
                            <a
                                href={exportResult.download_url}
                                className="text-xs text-primary underline underline-offset-2"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                Download exported file
                            </a>
                        )}
                    </CardContent>
                </Card>

                {/* 4. Bulk Archive */}
                <Card className={cn(selectedCount === 0 && "opacity-50 pointer-events-none")}>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Bulk Archive</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <p className="text-sm text-muted-foreground">
                            Archive all selected cases. Archived cases can be restored later from the admin dashboard.
                        </p>
                        <AlertDialog>
                            <AlertDialogTrigger asChild>
                                <Button
                                    size="sm"
                                    variant="destructive"
                                    disabled={selectedCount === 0 || bulkArchive.isPending}
                                >
                                    {bulkArchive.isPending ? "Archiving..." : "Archive Cases"}
                                </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                                <AlertDialogHeader>
                                    <AlertDialogTitle>Confirm Bulk Archive</AlertDialogTitle>
                                    <AlertDialogDescription>
                                        This will archive <strong>{selectedCount}</strong> case
                                        {selectedCount !== 1 ? "s" : ""}. Archived cases will be moved out
                                        of the active case list. This can be reversed later.
                                    </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                                    <AlertDialogAction
                                        variant="destructive"
                                        onClick={() => bulkArchive.mutate()}
                                    >
                                        Archive {selectedCount} Case{selectedCount !== 1 ? "s" : ""}
                                    </AlertDialogAction>
                                </AlertDialogFooter>
                            </AlertDialogContent>
                        </AlertDialog>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
