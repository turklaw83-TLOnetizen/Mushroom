// ---- Morning Brief — Daily Case Autopilot --------------------------------
// The attorney's command center. Opens every morning to surface everything
// that needs attention: triage items, schedule, and location suggestions.
"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { routes } from "@/lib/api-routes";
import { queryKeys } from "@/lib/query-keys";
import { formatDate } from "@/lib/constants";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// ---- TypeScript Interfaces ------------------------------------------------

interface TriageAction {
    type: string;
    label: string;
    endpoint: string;
    method: string;
    params: Record<string, unknown>;
}

interface TriageItem {
    id: string;
    type: string;
    title: string;
    detail: string;
    case_id: string;
    case_name: string;
    severity: "critical" | "high" | "medium" | "low";
    due_date: string;
    action: TriageAction;
    secondary_actions: TriageAction[];
    source: string;
    timestamp: string;
}

interface LocationOpportunity {
    title: string;
    case_id: string;
    case_name: string;
    detail: string;
    task_id: string;
    action: TriageAction;
}

interface LocationSuggestion {
    location: string;
    scheduled_event: {
        title: string;
        time: string;
        case_id: string;
        event_id: string;
    };
    opportunities: LocationOpportunity[];
}

interface ScheduleEvent {
    time: string;
    title: string;
    location: string;
    case_id: string;
    event_id: string;
}

interface MorningBrief {
    date: string;
    generated_at: string;
    summary: {
        total_items: number;
        critical_count: number;
        high_count: number;
        cases_with_activity: number;
        today_events_count: number;
    };
    triage_items: TriageItem[];
    location_suggestions: LocationSuggestion[];
    today_schedule: ScheduleEvent[];
}

// ---- Severity colors & source badges -------------------------------------

const SEVERITY_BORDER: Record<string, string> = {
    critical: "border-l-red-500",
    high: "border-l-orange-500",
    medium: "border-l-yellow-500",
    low: "border-l-gray-400",
};

const SEVERITY_BADGE: Record<string, string> = {
    critical: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    high: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
    medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
    low: "bg-gray-100 text-gray-700 dark:bg-gray-800/40 dark:text-gray-400",
};

const SOURCE_BADGE: Record<string, string> = {
    Calendar: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
    Tasks: "bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-300",
    Billing: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
    Comms: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
    Proactive: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300",
};

// ---- Helpers -------------------------------------------------------------

function formatTime(timeStr: string): string {
    try {
        // Handle time strings like "9:00 AM" or ISO timestamps
        if (timeStr.includes("T")) {
            const d = new Date(timeStr);
            return d.toLocaleTimeString("en-US", {
                hour: "numeric",
                minute: "2-digit",
            });
        }
        return timeStr;
    } catch {
        return timeStr;
    }
}

function formatFullDate(dateStr: string): string {
    try {
        const d = new Date(dateStr);
        return d.toLocaleDateString("en-US", {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
        });
    } catch {
        return dateStr;
    }
}

// ---- Main Page Component -------------------------------------------------

export default function MorningBriefPage() {
    const { getToken } = useAuth();
    const qc = useQueryClient();
    const router = useRouter();

    const [sendDigestOpen, setSendDigestOpen] = useState(false);

    // ---- Main Brief Query ----
    const {
        data: brief,
        isLoading,
        isError,
        refetch,
    } = useQuery({
        queryKey: queryKeys.morningBrief,
        queryFn: () => api.get<MorningBrief>(routes.morningBrief.get, { getToken }),
        refetchInterval: 300_000, // 5 min auto-refresh
    });

    // ---- Mutations ----
    const dismissMut = useMutation({
        mutationFn: (itemId: string) =>
            api.post<{ success: boolean; item_id: string }>(
                routes.morningBrief.dismissItem(itemId),
                {},
                { getToken },
            ),
        onSuccess: (_data, itemId) => {
            toast.success("Item dismissed");
            qc.invalidateQueries({ queryKey: [...queryKeys.morningBrief] });
        },
        onError: () => toast.error("Failed to dismiss item"),
    });

    const snoozeMut = useMutation({
        mutationFn: (itemId: string) =>
            api.post<{ success: boolean; item_id: string; snoozed_until: string }>(
                routes.morningBrief.snoozeItem(itemId),
                {},
                { getToken },
            ),
        onSuccess: (data) => {
            toast.success(`Snoozed until ${formatDate(data.snoozed_until)}`);
            qc.invalidateQueries({ queryKey: [...queryKeys.morningBrief] });
        },
        onError: () => toast.error("Failed to snooze item"),
    });

    const sendDigestMut = useMutation({
        mutationFn: () =>
            api.post<{ success: boolean; comm_id: string }>(
                routes.morningBrief.sendDigest,
                {},
                { getToken },
            ),
        onSuccess: () => {
            toast.success("Daily digest sent");
            setSendDigestOpen(false);
        },
        onError: () => toast.error("Failed to send digest"),
    });

    // ---- Derived data ----
    const summary = brief?.summary;
    const triageItems = brief?.triage_items ?? [];
    const locationSuggestions = brief?.location_suggestions ?? [];
    const schedule = useMemo(
        () =>
            [...(brief?.today_schedule ?? [])].sort((a, b) =>
                a.time.localeCompare(b.time),
            ),
        [brief?.today_schedule],
    );

    const todayDisplay = brief?.date
        ? formatFullDate(brief.date)
        : new Date().toLocaleDateString("en-US", {
              weekday: "long",
              year: "numeric",
              month: "long",
              day: "numeric",
          });

    // ---- Loading State ----
    if (isLoading) {
        return (
            <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
                <div className="space-y-2">
                    <Skeleton className="h-10 w-80" />
                    <Skeleton className="h-5 w-56" />
                </div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    {Array.from({ length: 5 }).map((_, i) => (
                        <Skeleton key={i} className="h-20 rounded-lg" />
                    ))}
                </div>
                <Skeleton className="h-32 rounded-lg" />
                <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-28 rounded-lg" />
                    ))}
                </div>
            </div>
        );
    }

    // ---- Error State ----
    if (isError) {
        return (
            <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Morning Brief</h1>
                    <p className="text-sm text-muted-foreground mt-1">{todayDisplay}</p>
                </div>
                <Card className="border-destructive/30">
                    <CardContent className="py-12 text-center space-y-4">
                        <p className="text-muted-foreground">
                            Failed to load the morning brief. The API may be unreachable.
                        </p>
                        <Button variant="outline" onClick={() => refetch()}>
                            Retry
                        </Button>
                    </CardContent>
                </Card>
            </div>
        );
    }

    // ---- Render ----
    return (
        <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
            {/* ================================================================
                SECTION 1: Header + Summary Bar
               ================================================================ */}
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Morning Brief</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        {todayDisplay}
                        {brief?.generated_at && (
                            <span className="ml-2 text-xs opacity-60">
                                Generated {formatTime(brief.generated_at)}
                            </span>
                        )}
                    </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => refetch()}
                    >
                        Refresh
                    </Button>
                    <Button
                        size="sm"
                        onClick={() => setSendDigestOpen(true)}
                    >
                        Send Digest
                    </Button>
                </div>
            </div>

            {/* Summary Badges Row */}
            {summary && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    <Card>
                        <CardContent className="pt-4 pb-3">
                            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                                Total Items
                            </p>
                            <p className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">
                                {summary.total_items}
                            </p>
                        </CardContent>
                    </Card>
                    <Card className={summary.critical_count > 0 ? "ring-1 ring-red-500/30" : ""}>
                        <CardContent className="pt-4 pb-3">
                            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                                Critical
                            </p>
                            <p className={`text-2xl font-bold ${summary.critical_count > 0 ? "text-red-500 animate-pulse" : "text-muted-foreground"}`}>
                                {summary.critical_count}
                            </p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-4 pb-3">
                            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                                High Priority
                            </p>
                            <p className="text-2xl font-bold text-orange-500">
                                {summary.high_count}
                            </p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-4 pb-3">
                            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                                Events Today
                            </p>
                            <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                                {summary.today_events_count}
                            </p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-4 pb-3">
                            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                                Cases Active
                            </p>
                            <p className="text-2xl font-bold text-muted-foreground">
                                {summary.cases_with_activity}
                            </p>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* ================================================================
                SECTION 2: Today's Schedule (horizontal timeline)
               ================================================================ */}
            {schedule.length > 0 && (
                <div>
                    <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                        Today&apos;s Schedule
                    </h2>
                    <div className="flex gap-4 overflow-x-auto pb-2">
                        {schedule.map((event) => (
                            <Card
                                key={event.event_id}
                                className="min-w-[200px] max-w-[260px] shrink-0 cursor-pointer hover:border-indigo-500/40 transition-colors"
                                onClick={() => router.push(`/cases/${event.case_id}/calendar`)}
                            >
                                <CardContent className="pt-4 pb-3">
                                    <p className="text-lg font-bold text-indigo-600 dark:text-indigo-400">
                                        {formatTime(event.time)}
                                    </p>
                                    <p className="text-sm font-medium mt-1 line-clamp-2">
                                        {event.title}
                                    </p>
                                    {event.location && (
                                        <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                                            <span aria-hidden="true">
                                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="size-3">
                                                    <path fillRule="evenodd" d="m7.539 14.841.003.003.002.002a.755.755 0 0 0 .912 0l.002-.002.003-.003.012-.009a5.57 5.57 0 0 0 .19-.153 15.588 15.588 0 0 0 2.046-2.082c1.101-1.362 2.291-3.342 2.291-5.597A5 5 0 0 0 3 7c0 2.255 1.19 4.235 2.291 5.597a15.591 15.591 0 0 0 2.236 2.235l.012.01ZM8 8.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z" clipRule="evenodd" />
                                                </svg>
                                            </span>
                                            <span className="truncate">{event.location}</span>
                                        </p>
                                    )}
                                    {event.case_id && (
                                        <Badge variant="outline" className="mt-2 text-[10px]">
                                            Case
                                        </Badge>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </div>
            )}

            {/* ================================================================
                SECTION 3: Triage Items
               ================================================================ */}
            <div>
                <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                    Triage
                </h2>
                <TriageSection
                    items={triageItems}
                    onDismiss={(id) => dismissMut.mutate(id)}
                    onSnooze={(id) => snoozeMut.mutate(id)}
                    dismissPending={dismissMut.isPending}
                    snoozePending={snoozeMut.isPending}
                    router={router}
                />
            </div>

            {/* ================================================================
                SECTION 4: Location-Aware Suggestions
               ================================================================ */}
            {locationSuggestions.length > 0 && (
                <div>
                    <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="size-4 text-emerald-500">
                            <path fillRule="evenodd" d="m7.539 14.841.003.003.002.002a.755.755 0 0 0 .912 0l.002-.002.003-.003.012-.009a5.57 5.57 0 0 0 .19-.153 15.588 15.588 0 0 0 2.046-2.082c1.101-1.362 2.291-3.342 2.291-5.597A5 5 0 0 0 3 7c0 2.255 1.19 4.235 2.291 5.597a15.591 15.591 0 0 0 2.236 2.235l.012.01ZM8 8.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z" clipRule="evenodd" />
                        </svg>
                        While You&apos;re There...
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {locationSuggestions.map((loc, idx) => (
                            <Card
                                key={idx}
                                className="border-l-4 border-l-emerald-500"
                            >
                                <CardHeader className="pb-2">
                                    <CardTitle className="text-sm font-semibold flex items-center gap-2">
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="size-4 text-emerald-500">
                                            <path fillRule="evenodd" d="m7.539 14.841.003.003.002.002a.755.755 0 0 0 .912 0l.002-.002.003-.003.012-.009a5.57 5.57 0 0 0 .19-.153 15.588 15.588 0 0 0 2.046-2.082c1.101-1.362 2.291-3.342 2.291-5.597A5 5 0 0 0 3 7c0 2.255 1.19 4.235 2.291 5.597a15.591 15.591 0 0 0 2.236 2.235l.012.01ZM8 8.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z" clipRule="evenodd" />
                                        </svg>
                                        {loc.location}
                                    </CardTitle>
                                    <CardDescription>
                                        Scheduled: {loc.scheduled_event.title} at{" "}
                                        {formatTime(loc.scheduled_event.time)}
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="space-y-3">
                                        {loc.opportunities.map((opp, oidx) => (
                                            <div
                                                key={oidx}
                                                className="flex items-start justify-between gap-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3"
                                            >
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-sm font-medium">
                                                        {opp.title}
                                                    </p>
                                                    <p className="text-xs text-muted-foreground mt-0.5">
                                                        {opp.case_name}
                                                    </p>
                                                    {opp.detail && (
                                                        <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                                                            {opp.detail}
                                                        </p>
                                                    )}
                                                </div>
                                                {opp.action && (
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        className="text-xs shrink-0 border-emerald-500/30 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-500/10"
                                                        onClick={() => {
                                                            if (opp.action.type === "navigate") {
                                                                router.push(opp.action.endpoint);
                                                            } else {
                                                                toast.info(`Action: ${opp.action.label}`);
                                                            }
                                                        }}
                                                    >
                                                        {opp.action.label}
                                                    </Button>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </div>
            )}

            {/* ---- Dialogs ---- */}
            <SendDigestDialog
                open={sendDigestOpen}
                onOpenChange={setSendDigestOpen}
                onConfirm={() => sendDigestMut.mutate()}
                isPending={sendDigestMut.isPending}
                summary={summary}
            />
        </div>
    );
}

// ---- Triage Section Component --------------------------------------------

function TriageSection({
    items,
    onDismiss,
    onSnooze,
    dismissPending,
    snoozePending,
    router,
}: {
    items: TriageItem[];
    onDismiss: (id: string) => void;
    onSnooze: (id: string) => void;
    dismissPending: boolean;
    snoozePending: boolean;
    router: ReturnType<typeof useRouter>;
}) {
    const [activeTab, setActiveTab] = useState("all");

    const filteredItems = useMemo(() => {
        switch (activeTab) {
            case "critical":
                return items.filter((i) => i.severity === "critical");
            case "high":
                return items.filter((i) => i.severity === "high");
            case "action":
                return items.filter((i) => i.action?.type !== "navigate");
            default:
                return items;
        }
    }, [items, activeTab]);

    const criticalCount = items.filter((i) => i.severity === "critical").length;
    const highCount = items.filter((i) => i.severity === "high").length;
    const actionCount = items.filter((i) => i.action?.type !== "navigate").length;

    if (items.length === 0) {
        return (
            <Card className="border-dashed">
                <CardContent className="py-12 text-center">
                    <p className="text-lg font-medium text-muted-foreground">
                        All clear! No urgent items for today.
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                        Enjoy your morning.
                    </p>
                </CardContent>
            </Card>
        );
    }

    return (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
                <TabsTrigger value="all">
                    All
                    <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5">
                        {items.length}
                    </Badge>
                </TabsTrigger>
                <TabsTrigger value="critical">
                    Critical
                    {criticalCount > 0 && (
                        <Badge variant="destructive" className="ml-1.5 text-[10px] px-1.5">
                            {criticalCount}
                        </Badge>
                    )}
                </TabsTrigger>
                <TabsTrigger value="high">
                    High
                    {highCount > 0 && (
                        <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5">
                            {highCount}
                        </Badge>
                    )}
                </TabsTrigger>
                <TabsTrigger value="action">
                    Action Needed
                    {actionCount > 0 && (
                        <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5">
                            {actionCount}
                        </Badge>
                    )}
                </TabsTrigger>
            </TabsList>

            <TabsContent value={activeTab} className="mt-4 space-y-3">
                {filteredItems.length === 0 ? (
                    <Card className="border-dashed">
                        <CardContent className="py-8 text-center text-muted-foreground text-sm">
                            No items in this category.
                        </CardContent>
                    </Card>
                ) : (
                    filteredItems.map((item) => (
                        <TriageCard
                            key={item.id}
                            item={item}
                            onDismiss={onDismiss}
                            onSnooze={onSnooze}
                            dismissPending={dismissPending}
                            snoozePending={snoozePending}
                            router={router}
                        />
                    ))
                )}
            </TabsContent>
        </Tabs>
    );
}

// ---- Individual Triage Card ----------------------------------------------

function TriageCard({
    item,
    onDismiss,
    onSnooze,
    dismissPending,
    snoozePending,
    router,
}: {
    item: TriageItem;
    onDismiss: (id: string) => void;
    onSnooze: (id: string) => void;
    dismissPending: boolean;
    snoozePending: boolean;
    router: ReturnType<typeof useRouter>;
}) {
    const severityBorder = SEVERITY_BORDER[item.severity] || SEVERITY_BORDER.low;
    const sourceBadgeCls = SOURCE_BADGE[item.source] || SOURCE_BADGE.Proactive;

    return (
        <Card className={`border-l-4 ${severityBorder}`}>
            <CardContent className="py-4">
                <div className="flex items-start justify-between gap-4">
                    {/* Left Content */}
                    <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2 mb-1">
                            <span className="text-sm font-semibold">{item.title}</span>
                            <Badge variant="outline" className="text-[10px]">
                                {item.case_name}
                            </Badge>
                            <span
                                className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium ${sourceBadgeCls}`}
                            >
                                {item.source}
                            </span>
                            <span
                                className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium capitalize ${SEVERITY_BADGE[item.severity] || ""}`}
                            >
                                {item.severity}
                            </span>
                        </div>
                        <p className="text-sm text-muted-foreground line-clamp-2">
                            {item.detail}
                        </p>
                        {item.due_date && (
                            <p className="text-[10px] text-muted-foreground mt-1">
                                Due: {formatDate(item.due_date)}
                            </p>
                        )}
                    </div>

                    {/* Right Actions */}
                    <div className="flex flex-col sm:flex-row gap-1.5 shrink-0">
                        {/* Primary action */}
                        {item.action && (
                            <Button
                                size="sm"
                                className="text-xs"
                                onClick={() => {
                                    if (item.action.type === "navigate") {
                                        router.push(item.action.endpoint);
                                    } else {
                                        toast.info(`Action: ${item.action.label}`);
                                    }
                                }}
                            >
                                {item.action.label}
                            </Button>
                        )}
                        {/* Snooze */}
                        <Button
                            size="sm"
                            variant="outline"
                            className="text-xs"
                            onClick={() => onSnooze(item.id)}
                            disabled={snoozePending}
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="size-3 mr-1">
                                <path fillRule="evenodd" d="M1 8a7 7 0 1 1 14 0A7 7 0 0 1 1 8Zm7.75-4.25a.75.75 0 0 0-1.5 0V8c0 .414.336.75.75.75h3.25a.75.75 0 0 0 0-1.5h-2.5v-3.5Z" clipRule="evenodd" />
                            </svg>
                            Snooze
                        </Button>
                        {/* Dismiss */}
                        <Button
                            size="sm"
                            variant="ghost"
                            className="text-xs text-muted-foreground hover:text-destructive"
                            onClick={() => onDismiss(item.id)}
                            disabled={dismissPending}
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="size-3 mr-1">
                                <path d="M5.28 4.22a.75.75 0 0 0-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 1 0 1.06 1.06L8 9.06l2.72 2.72a.75.75 0 1 0 1.06-1.06L9.06 8l2.72-2.72a.75.75 0 0 0-1.06-1.06L8 6.94 5.28 4.22Z" />
                            </svg>
                            Dismiss
                        </Button>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

// ---- Send Digest Dialog --------------------------------------------------

function SendDigestDialog({
    open,
    onOpenChange,
    onConfirm,
    isPending,
    summary,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void;
    isPending: boolean;
    summary?: MorningBrief["summary"];
}) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Send Daily Digest</DialogTitle>
                    <DialogDescription>
                        This will compile today&apos;s brief into a formatted digest
                        and send it to the configured recipients.
                    </DialogDescription>
                </DialogHeader>
                {summary && (
                    <div className="rounded-lg border p-4 space-y-2 text-sm">
                        <p>
                            <span className="font-medium">{summary.total_items}</span> triage items
                            {summary.critical_count > 0 && (
                                <span className="text-red-500 font-medium ml-1">
                                    ({summary.critical_count} critical)
                                </span>
                            )}
                        </p>
                        <p>
                            <span className="font-medium">{summary.today_events_count}</span> events
                            scheduled
                        </p>
                        <p>
                            <span className="font-medium">{summary.cases_with_activity}</span> cases
                            with activity
                        </p>
                    </div>
                )}
                <DialogFooter>
                    <Button
                        variant="outline"
                        onClick={() => onOpenChange(false)}
                        disabled={isPending}
                    >
                        Cancel
                    </Button>
                    <Button onClick={onConfirm} disabled={isPending}>
                        {isPending ? "Sending..." : "Send Digest"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

