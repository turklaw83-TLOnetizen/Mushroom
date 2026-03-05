// ---- Timeline & Deadlines Tab -------------------------------------------
"use client";

import { useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SOLDeadline {
    status: string;
    incident_date: string;
    case_type: string;
    jurisdiction: string;
    sol_years: number;
    deadline: string;
    days_remaining: number;
    is_expired: boolean;
    is_urgent: boolean;
}

interface CalendarEvent {
    id: string;
    title: string;
    date: string;
    time?: string;
    type: string;
    event_type?: string;
    description?: string;
    location?: string;
    status?: string;
}

interface SOLReference {
    periods: Record<string, number | string>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
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

function toDateStr(iso: string): string {
    try {
        return new Date(iso).toISOString().split("T")[0];
    } catch {
        return iso;
    }
}

function todayStr(): string {
    return new Date().toISOString().split("T")[0];
}

/**
 * Returns urgency color classes based on days remaining.
 * green if >90, amber if 30-90, red if <30 or expired.
 */
function urgencyColor(daysRemaining: number, isExpired: boolean): {
    text: string;
    bg: string;
    border: string;
    progress: string;
} {
    if (isExpired || daysRemaining < 30) {
        return {
            text: "text-red-400",
            bg: "bg-red-500/15",
            border: "border-red-500/30",
            progress: "[&>[data-slot=progress-indicator]]:bg-red-500",
        };
    }
    if (daysRemaining <= 90) {
        return {
            text: "text-amber-400",
            bg: "bg-amber-500/15",
            border: "border-amber-500/30",
            progress: "[&>[data-slot=progress-indicator]]:bg-amber-500",
        };
    }
    return {
        text: "text-green-400",
        bg: "bg-green-500/15",
        border: "border-green-500/30",
        progress: "[&>[data-slot=progress-indicator]]:bg-green-500",
    };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function TimelinePage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();

    // ---- Queries -----------------------------------------------------------

    const solQuery = useQuery({
        queryKey: ["sol", "deadline", caseId],
        queryFn: () =>
            api.get<SOLDeadline>(`/cases/${caseId}/sol/deadline`, { getToken }),
    });

    const eventsQuery = useQuery({
        queryKey: ["calendar", "events", caseId],
        queryFn: () =>
            api.get<CalendarEvent[]>("/calendar/events", {
                params: { case_id: caseId },
                getToken,
            }),
    });

    const refQuery = useQuery({
        queryKey: ["sol", "reference", caseId],
        queryFn: () =>
            api.get<SOLReference>(`/cases/${caseId}/sol/reference`, {
                getToken,
            }),
    });

    const sol = solQuery.data;
    const events = eventsQuery.data ?? [];
    const reference = refQuery.data;

    // Sort events chronologically
    const sortedEvents = useMemo(
        () =>
            [...events].sort(
                (a, b) =>
                    new Date(a.date).getTime() - new Date(b.date).getTime(),
            ),
        [events],
    );

    const today = todayStr();

    // SOL progress: percentage of time elapsed from incident to deadline
    const solProgress = useMemo(() => {
        if (!sol || sol.status !== "calculated") return 0;
        const incidentMs = new Date(sol.incident_date).getTime();
        const deadlineMs = new Date(sol.deadline).getTime();
        const nowMs = Date.now();
        const total = deadlineMs - incidentMs;
        if (total <= 0) return 100;
        const elapsed = nowMs - incidentMs;
        return Math.min(100, Math.max(0, (elapsed / total) * 100));
    }, [sol]);

    // ---- Render ------------------------------------------------------------

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-xl font-bold tracking-tight">
                    Timeline &amp; Deadlines
                </h2>
                <p className="text-sm text-muted-foreground mt-0.5">
                    Statute of limitations tracking and case event timeline
                </p>
            </div>

            {/* ---- SOL Deadline Card ---------------------------------------- */}
            {solQuery.isLoading ? (
                <Skeleton className="h-36 w-full rounded-lg" />
            ) : sol && sol.status === "calculated" ? (
                <SOLCard sol={sol} progress={solProgress} />
            ) : (
                <Card className="border-dashed">
                    <CardContent className="py-8 text-center">
                        <p className="text-sm text-muted-foreground">
                            SOL not calculated.{" "}
                            <a
                                href={`/cases/${caseId}/compliance`}
                                className="text-primary underline underline-offset-4 hover:text-primary/80"
                            >
                                Set up in Compliance tab
                            </a>
                        </p>
                    </CardContent>
                </Card>
            )}

            {/* ---- Event Timeline ------------------------------------------- */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center justify-between">
                        Case Timeline
                        <Badge variant="secondary">
                            {sortedEvents.length} events
                        </Badge>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {eventsQuery.isLoading ? (
                        <div className="space-y-3">
                            {Array.from({ length: 5 }).map((_, i) => (
                                <Skeleton
                                    key={i}
                                    className="h-14 w-full rounded-lg"
                                />
                            ))}
                        </div>
                    ) : sortedEvents.length === 0 ? (
                        <p className="text-sm text-muted-foreground text-center py-8">
                            No events on the calendar for this case.
                        </p>
                    ) : (
                        <div className="relative">
                            {/* Vertical line */}
                            <div className="absolute left-[19px] top-4 bottom-4 w-px bg-border" />

                            <div className="space-y-1">
                                {sortedEvents.map((event, i) => {
                                    const eventDate = toDateStr(event.date);
                                    const isPast = eventDate < today;
                                    const isToday = eventDate === today;

                                    return (
                                        <div key={event.id || i}>
                                            {/* Today marker — render once before the first future/today event */}
                                            {isToday && i === sortedEvents.findIndex((e) => toDateStr(e.date) >= today) && (
                                                <div className="flex items-center gap-3 py-1 relative">
                                                    <div className="w-10 flex justify-center shrink-0 z-10">
                                                        <div className="w-3 h-3 rounded-full bg-primary ring-2 ring-primary/30" />
                                                    </div>
                                                    <div className="flex-1 h-px bg-primary/40" />
                                                    <span className="text-xs font-semibold text-primary shrink-0">
                                                        Today
                                                    </span>
                                                </div>
                                            )}

                                            <div
                                                className={`flex gap-3 items-start relative ${
                                                    isPast && !isToday
                                                        ? "opacity-50"
                                                        : ""
                                                }`}
                                            >
                                                {/* Dot */}
                                                <div className="w-10 h-10 rounded-full bg-card border border-border flex items-center justify-center shrink-0 z-10">
                                                    <div
                                                        className={`w-2.5 h-2.5 rounded-full ${
                                                            isToday
                                                                ? "bg-primary"
                                                                : "bg-muted-foreground"
                                                        }`}
                                                    />
                                                </div>

                                                <Card className="flex-1 hover:bg-accent/20 transition-colors">
                                                    <CardContent className="py-2.5 flex items-center justify-between">
                                                        <div className="min-w-0">
                                                            <div className="flex items-center gap-2">
                                                                <p className="text-sm font-medium truncate">
                                                                    {event.title}
                                                                </p>
                                                                <Badge
                                                                    variant="outline"
                                                                    className="text-[10px] shrink-0"
                                                                >
                                                                    {event.event_type ||
                                                                        event.type}
                                                                </Badge>
                                                            </div>
                                                            {event.description && (
                                                                <p className="text-xs text-muted-foreground mt-0.5 truncate">
                                                                    {event.description}
                                                                </p>
                                                            )}
                                                        </div>
                                                        <span className="text-xs text-muted-foreground whitespace-nowrap ml-3 shrink-0">
                                                            {formatDate(event.date)}
                                                            {event.time &&
                                                                ` at ${event.time}`}
                                                        </span>
                                                    </CardContent>
                                                </Card>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* ---- SOL Reference Table -------------------------------------- */}
            {refQuery.isLoading ? (
                <Skeleton className="h-48 w-full rounded-lg" />
            ) : reference && reference.periods && Object.keys(reference.periods).length > 0 ? (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">
                            SOL Reference Periods
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="rounded-md border">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b bg-muted/50">
                                        <th className="text-left font-medium px-4 py-2">
                                            Claim Type
                                        </th>
                                        <th className="text-right font-medium px-4 py-2">
                                            Period
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {Object.entries(reference.periods).map(
                                        ([claimType, period]) => (
                                            <tr
                                                key={claimType}
                                                className="border-b last:border-0"
                                            >
                                                <td className="px-4 py-2">
                                                    {claimType}
                                                </td>
                                                <td className="px-4 py-2 text-right text-muted-foreground">
                                                    {typeof period === "number"
                                                        ? `${period} year${period !== 1 ? "s" : ""}`
                                                        : String(period)}
                                                </td>
                                            </tr>
                                        ),
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </CardContent>
                </Card>
            ) : null}
        </div>
    );
}

// ---------------------------------------------------------------------------
// SOL Card subcomponent
// ---------------------------------------------------------------------------

function SOLCard({
    sol,
    progress,
}: {
    sol: SOLDeadline;
    progress: number;
}) {
    const colors = urgencyColor(sol.days_remaining, sol.is_expired);

    return (
        <Card>
            <CardContent className="pt-5 pb-4 space-y-4">
                <div className="flex items-start justify-between">
                    <div>
                        <p className="text-xs font-medium text-muted-foreground uppercase">
                            Statute of Limitations Deadline
                        </p>
                        <p className="text-lg font-bold mt-1">
                            {formatDate(sol.deadline)}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                            {sol.case_type} &middot; {sol.jurisdiction} &middot;{" "}
                            {sol.sol_years} year{sol.sol_years !== 1 ? "s" : ""}
                        </p>
                    </div>
                    <div className="text-right">
                        <p
                            className={`text-3xl font-extrabold tabular-nums ${colors.text}`}
                        >
                            {sol.is_expired ? 0 : sol.days_remaining}
                        </p>
                        <p className="text-xs text-muted-foreground">
                            days remaining
                        </p>
                    </div>
                </div>

                {/* Progress bar */}
                <Progress
                    value={progress}
                    className={`h-2 ${colors.progress}`}
                />

                {/* Warnings */}
                {sol.is_expired && (
                    <Badge
                        variant="outline"
                        className="bg-red-500/15 text-red-400 border-red-500/30"
                    >
                        EXPIRED
                    </Badge>
                )}
                {!sol.is_expired && sol.is_urgent && (
                    <Badge
                        variant="outline"
                        className="bg-amber-500/15 text-amber-400 border-amber-500/30"
                    >
                        URGENT - Deadline approaching
                    </Badge>
                )}
            </CardContent>
        </Card>
    );
}
