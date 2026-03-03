// ---- Dashboard Page (with delete confirmation) --------------------------
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";

import { useCases, useCreateCase, type CaseItem } from "@/hooks/use-cases";
import { api } from "@/lib/api-client";
import { CaseTable } from "@/components/dashboard/case-table";
import { NewCaseDialog } from "@/components/dashboard/new-case-dialog";
import { DashboardStats, ActivityFeed } from "@/components/dashboard/dashboard-widgets";
import {
  BillingMetrics,
  CalendarMetrics,
  DeadlineUrgencyBoard,
  TeamWorkload,
  useDeadlineToasts,
} from "@/components/dashboard/dashboard-enrichment";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

const PER_PAGE_OPTIONS = [10, 25, 50] as const;

export default function DashboardPage() {
  const router = useRouter();
  const { getToken } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<CaseItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState<number>(25);
  const { data, isLoading, error } = useCases(page, perPage);
  const createCase = useCreateCase();

  const totalPages = data?.pages ?? 1;
  const totalCases = data?.total ?? 0;

  // Fire deadline toast notifications on mount (once per session)
  useDeadlineToasts();

  const cases = data?.items ?? [];
  const filtered = search
    ? cases.filter(
      (c: CaseItem) =>
        c.name.toLowerCase().includes(search.toLowerCase()) ||
        c.client_name?.toLowerCase().includes(search.toLowerCase()) ||
        c.case_category?.toLowerCase().includes(search.toLowerCase()),
    )
    : cases;

  const handleCreate = async (input: {
    case_name: string;
    description?: string;
    case_type?: string;
    case_category?: string;
    client_name?: string;
    jurisdiction?: string;
  }) => {
    try {
      const result = await createCase.mutateAsync(input);
      toast.success("Case created", { description: input.case_name });
      setDialogOpen(false);
      router.push(`/cases/${result.case_id}`);
    } catch (err) {
      toast.error("Failed to create case", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await api.delete(`/cases/${deleteTarget.id}`, { getToken });
      toast.success("Case deleted", { description: deleteTarget.name });
      queryClient.invalidateQueries({ queryKey: ["cases"] });
    } catch (err) {
      toast.error("Failed to delete case", {
        description: err instanceof Error ? err.message : "Unknown error",
      });
    } finally {
      setIsDeleting(false);
      setDeleteTarget(null);
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data ? `${totalCases} total cases` : "Loading..."}
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)} className="gap-2">
          <span>+</span> New Case
        </Button>
      </div>

      {/* Search */}
      <Input
        placeholder="Search cases by name, client, or category..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-md"
      />

      {/* Billing Metrics */}
      <BillingMetrics />

      {/* Stats */}
      <DashboardStats />

      {/* Deadline Urgency Board */}
      <DeadlineUrgencyBoard />

      {/* Calendar Metrics */}
      <CalendarMetrics />

      {/* Team Workload */}
      <TeamWorkload />

      {/* Case Table */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full rounded-md" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          Failed to load cases: {error.message}
        </div>
      ) : (
        <CaseTable
          cases={filtered}
          onRowClick={(c) => router.push(`/cases/${c.id}`)}
          onDelete={(c) => setDeleteTarget(c)}
        />
      )}

      {/* Pagination Controls */}
      {!isLoading && !error && (
        <div className="flex items-center justify-between border-t pt-4">
          {/* Left: total count */}
          <p className="text-sm text-muted-foreground">
            {totalCases} {totalCases === 1 ? "case" : "cases"} total
          </p>

          {/* Center: page navigation */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground px-2">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Next
            </Button>
          </div>

          {/* Right: per-page selector */}
          <div className="flex items-center gap-1">
            <span className="text-sm text-muted-foreground mr-1">Show</span>
            {PER_PAGE_OPTIONS.map((opt) => (
              <Button
                key={opt}
                variant={perPage === opt ? "default" : "ghost"}
                size="xs"
                onClick={() => {
                  setPerPage(opt);
                  setPage(1);
                }}
              >
                {opt}
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* New Case Dialog */}
      <NewCaseDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSubmit={handleCreate}
        isLoading={createCase.isPending}
      />

      {/* Delete Confirm */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Delete Case"
        description={`Permanently delete "${deleteTarget?.name}"? All files, analysis, and preparations will be lost. This cannot be undone.`}
        confirmLabel="Delete Case"
        onConfirm={handleDelete}
        isLoading={isDeleting}
      />
    </div>
  );
}
