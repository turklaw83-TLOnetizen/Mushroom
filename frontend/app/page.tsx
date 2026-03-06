// ---- Dashboard Page (with delete confirmation) --------------------------
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";

import { useCases, useCreateCase, type CaseItem, type CreateCaseInput } from "@/hooks/use-cases";
import { api } from "@/lib/api-client";
import { CaseTable } from "@/components/dashboard/case-table";
import { NewCaseDialog } from "@/components/dashboard/new-case-dialog";
import { DashboardStats, ActivityFeed } from "@/components/dashboard/dashboard-widgets";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function DashboardPage() {
  const router = useRouter();
  const { getToken } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<CaseItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const { data, isLoading, error } = useCases();
  const createCase = useCreateCase();

  const cases = data?.items ?? [];
  const filtered = search
    ? cases.filter(
      (c: CaseItem) =>
        c.name.toLowerCase().includes(search.toLowerCase()) ||
        c.client_name?.toLowerCase().includes(search.toLowerCase()) ||
        c.case_category?.toLowerCase().includes(search.toLowerCase()),
    )
    : cases;

  const handleCreate = async (input: CreateCaseInput) => {
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

  // Recent Activity feed
  const { data: activityData, isLoading: activityLoading } = useQuery({
    queryKey: ["recent-activity"],
    queryFn: () =>
      api.get<{ items: Array<{ type: string; title: string; detail: string; case_id: string; client_id?: string; timestamp: string }> }>(
        "/activity/recent",
        { getToken, params: { limit: 10 } },
      ),
  });

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data ? `${data.total} total cases` : "Loading..."}
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

      {/* Stats */}
      <DashboardStats />

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

      {/* Recent Activity */}
      <RecentActivityCard items={activityData?.items ?? []} isLoading={activityLoading} />

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


// ---- Recent Activity Card -----------------------------------------------

interface ActivityItemShape {
  type: string;
  title: string;
  detail: string;
  case_id: string;
  client_id?: string;
  timestamp: string;
}

function activityTypeIcon(type: string): string {
  switch (type) {
    case "comm": return "\uD83D\uDCAC";       // speech bubble
    case "payment": return "\uD83D\uDCB0";    // money bag
    case "analysis": return "\uD83D\uDD0D";   // magnifying glass
    default: return "\uD83D\uDCDD";           // memo
  }
}

function timeAgo(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function RecentActivityCard({ items, isLoading }: { items: ActivityItemShape[]; isLoading: boolean }) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Recent Activity</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent className="space-y-0">
        {items.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-4">
            No recent activity
          </p>
        )}
        {items.slice(0, 10).map((item, i) => (
          <div
            key={`${item.type}-${item.timestamp}-${i}`}
            className="flex items-start gap-3 py-2.5 border-b last:border-0"
          >
            <span className="text-base mt-0.5">{activityTypeIcon(item.type)}</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{item.title}</p>
              <p className="text-xs text-muted-foreground truncate">{item.detail}</p>
            </div>
            <span className="text-[10px] text-muted-foreground whitespace-nowrap mt-0.5">
              {timeAgo(item.timestamp)}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
