// ---- Dashboard Page (with delete confirmation) --------------------------
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";

import Link from "next/link";
import { useCases, useCreateCase, type CaseItem, type CreateCaseInput } from "@/hooks/use-cases";
import { formatRelativeTime } from "@/lib/constants";
import { api } from "@/lib/api-client";
import { CaseTable } from "@/components/dashboard/case-table";
import { NewCaseDialog } from "@/components/dashboard/new-case-dialog";
import { DashboardStats } from "@/components/dashboard/dashboard-widgets";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/shared/empty-state";
import {
  FileUp,
  Brain,
  Clock,
  Briefcase,
  AlertCircle,
  Plus,
  FolderPlus,
  Download,
  Activity,
} from "lucide-react";

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

  // Attention items
  const { data: attentionData, error: attentionError } = useQuery({
    queryKey: ["attention-items"],
    queryFn: () =>
      api.get<{ items: Array<{ type: string; title: string; detail: string; case_id: string; severity: string }> }>(
        "/activity/attention",
        { getToken, params: { limit: 5 } },
      ),
    retry: false, // Don't retry if endpoint doesn't exist yet
    staleTime: 300000,
  });

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6 page-enter">
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

      {/* Attention Needed */}
      {attentionError ? (
        <p className="text-sm text-destructive">
          Failed to load attention items: {attentionError.message || "An unexpected error occurred"}
        </p>
      ) : attentionData?.items?.length ? (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-amber-500" /> Needs Attention
              <Badge variant="secondary" className="ml-auto text-xs">{attentionData.items.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-1.5">
            {attentionData.items.map((item, i) => {
              const severityBorder =
                item.severity === "critical" || item.severity === "high"
                  ? "border-l-4 border-l-red-500"
                  : item.severity === "medium"
                    ? "border-l-4 border-l-amber-500"
                    : item.severity === "low"
                      ? "border-l-4 border-l-blue-500"
                      : "border-l-4 border-l-muted-foreground";

              const AttentionIcon = getAttentionIcon(item.type);

              const content = (
                <div
                  className={`flex items-start gap-3 py-2.5 px-3 rounded-md bg-background/60 hover:bg-accent/50 transition-colors ${severityBorder}`}
                >
                  <div className={`mt-0.5 h-7 w-7 rounded-full flex items-center justify-center shrink-0 ${
                    item.severity === "critical" || item.severity === "high"
                      ? "bg-red-500/15" : item.severity === "medium"
                        ? "bg-amber-500/15" : "bg-blue-500/15"
                  }`}>
                    <AttentionIcon className={`h-3.5 w-3.5 ${
                      item.severity === "critical" || item.severity === "high"
                        ? "text-red-500" : item.severity === "medium"
                          ? "text-amber-500" : "text-blue-500"
                    }`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{item.title}</p>
                    <p className="text-xs text-muted-foreground truncate">{item.detail}</p>
                  </div>
                </div>
              );

              return item.case_id ? (
                <Link key={i} href={`/cases/${item.case_id}`} className="block">
                  {content}
                </Link>
              ) : (
                <div key={i}>{content}</div>
              );
            })}
          </CardContent>
        </Card>
      ) : null}

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


// ---- Attention Icon Helper ------------------------------------------------

function getAttentionIcon(type: string) {
  if (type === "file_uploaded" || type === "file") return FileUp;
  if (type.startsWith("analysis") || type === "analysis") return Brain;
  if (type === "deadline" || type === "calendar") return Clock;
  if (type === "case_created" || type === "case") return Briefcase;
  return AlertCircle;
}

// ---- Activity Icon Helper -------------------------------------------------

function getActivityIcon(type: string): { icon: typeof Activity; color: string; bg: string } {
  switch (type) {
    case "case_created":
      return { icon: Plus, color: "text-emerald-500", bg: "bg-emerald-500/15" };
    case "file_uploaded":
      return { icon: FileUp, color: "text-blue-500", bg: "bg-blue-500/15" };
    case "analysis_started":
    case "analysis_completed":
      return { icon: Brain, color: "text-violet-500", bg: "bg-violet-500/15" };
    case "prep_created":
      return { icon: FolderPlus, color: "text-indigo-500", bg: "bg-indigo-500/15" };
    case "export_generated":
      return { icon: Download, color: "text-cyan-500", bg: "bg-cyan-500/15" };
    default:
      return { icon: Activity, color: "text-muted-foreground", bg: "bg-muted" };
  }
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

function RecentActivityCard({ items, isLoading }: { items: ActivityItemShape[]; isLoading: boolean }) {
  const router = useRouter();
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
          <EmptyState
            icon="📋"
            title="No recent activity"
            description="Activity will appear here as you work on cases."
          />
        )}
        {items.slice(0, 10).map((item, i) => {
          const { icon: ItemIcon, color, bg } = getActivityIcon(item.type);
          return (
            <button
              key={`${item.type}-${item.timestamp}-${i}`}
              className="flex items-start gap-3 py-2.5 border-b last:border-0 w-full text-left hover:bg-accent/50 transition-colors rounded-md px-2 -mx-2"
              onClick={() => {
                if (item.case_id) {
                  router.push(`/cases/${item.case_id}`);
                }
              }}
            >
              <div className={`h-8 w-8 rounded-full ${bg} flex items-center justify-center shrink-0`}>
                <ItemIcon className={`h-4 w-4 ${color}`} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{item.title}</p>
                <p className="text-xs text-muted-foreground truncate">{item.detail}</p>
              </div>
              <span className="text-[10px] text-muted-foreground whitespace-nowrap mt-0.5">
                {formatRelativeTime(item.timestamp)}
              </span>
            </button>
          );
        })}
      </CardContent>
    </Card>
  );
}
