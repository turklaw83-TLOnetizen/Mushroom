// ---- Timeline & Deadlines Tab -------------------------------------------
"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";

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

interface SOLCalcResult {
    case_type: string;
    jurisdiction: string;
    sol_years: number;
    deadline: string;
    days_remaining: number;
    is_expired: boolean;
    is_urgent: boolean;
}

const SOL_CASE_TYPES = [
    "personal_injury",
    "medical_malpractice",
    "breach_of_contract",
    "property_damage",
    "employment",
    "fraud",
    "wrongful_death",
    "product_liability",
    "defamation",
    "criminal",
] as const;

const SOL_JURISDICTIONS = ["default", "CA", "TX", "NY", "FL"] as const;

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

    // ---- Swim Lane Categorization ------------------------------------------

    type LaneType = "prosecution" | "defense" | "court" | "other";

    const LANE_KEYWORDS: Record<LaneType, string[]> = {
        prosecution: ["arrest", "charge", "police", "prosecution", "indictment", "warrant"],
        defense: ["defense", "attorney", "counsel", "motion", "filing"],
        court: ["hearing", "trial", "court", "arraignment", "sentencing", "conference"],
        other: [],
    };

    const LANE_COLORS: Record<LaneType, string> = {
        prosecution: "border-l-red-500",
        defense: "border-l-blue-500",
        court: "border-l-gray-500",
        other: "border-l-violet-500",
    };

    const classifyEvent = (event: CalendarEvent): LaneType => {
        const text = `${event.title} ${event.type} ${event.event_type ?? ""} ${event.description ?? ""}`.toLowerCase();
        for (const lane of ["prosecution", "defense", "court"] as LaneType[]) {
            if (LANE_KEYWORDS[lane].some((kw) => text.includes(kw))) return lane;
        }
        return "other";
    };

    const eventLanes = useMemo(
        () => new Map(sortedEvents.map((e) => [e.id ?? e.title, classifyEvent(e)])),
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [sortedEvents],
    );

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

            {/* ---- SOL Calculator ------------------------------------------- */}
            <SOLCalculator caseId={caseId} getToken={getToken} />

            {/* ---- Event Timeline ------------------------------------------- */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center justify-between">
                        Case Timeline
                        <Badge variant="secondary">
                            {sortedEvents.length} events
                        </Badge>
                    </CardTitle>
                    <div className="flex gap-2 mt-2">
                        <Badge className="bg-red-500/20 text-red-400 border-red-500/30">Prosecution</Badge>
                        <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">Defense</Badge>
                        <Badge className="bg-gray-500/20 text-gray-400 border-gray-500/30">Court</Badge>
                        <Badge className="bg-violet-500/20 text-violet-400 border-violet-500/30">Other</Badge>
                    </div>
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

                                                <Card className={`flex-1 hover:bg-accent/20 transition-colors border-l-4 ${LANE_COLORS[eventLanes.get(event.id ?? event.title) ?? "other"]}`}>
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

function SOLCalculator({
    caseId,
    getToken,
}: {
    caseId: string;
    getToken: () => Promise<string | null>;
}) {
    const [open, setOpen] = useState(false);
    const [incidentDate, setIncidentDate] = useState("");
    const [caseType, setCaseType] = useState<string>("");
    const [jurisdiction, setJurisdiction] = useState<string>("");

    const calcMutation = useMutation({
        mutationFn: () =>
            api.post<SOLCalcResult>(
                `/cases/${caseId}/sol/calculate`,
                {
                    incident_date: incidentDate,
                    case_type: caseType,
                    jurisdiction: jurisdiction,
                },
                { getToken },
            ),
        onError: (err: Error) => {
            toast.error("SOL calculation failed", { description: err.message });
        },
    });

    const result = calcMutation.data;
    const canCalculate = incidentDate && caseType && jurisdiction;

    return (
        <Collapsible open={open} onOpenChange={setOpen}>
            <Card>
                <CollapsibleTrigger asChild>
                    <CardHeader className="cursor-pointer hover:bg-accent/30 transition-colors">
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle className="text-base">
                                    SOL Calculator
                                </CardTitle>
                                <p className="text-xs text-muted-foreground mt-0.5">
                                    What-if scenario calculator
                                </p>
                            </div>
                            <Badge variant="outline" className="text-xs">
                                {open ? "Collapse" : "Expand"}
                            </Badge>
                        </div>
                    </CardHeader>
                </CollapsibleTrigger>
                <CollapsibleContent>
                    <CardContent className="space-y-4 pt-0">
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                            {/* Incident Date */}
                            <div className="space-y-1.5">
                                <label className="text-xs font-medium text-muted-foreground">
                                    Incident Date
                                </label>
                                <Input
                                    type="date"
                                    value={incidentDate}
                                    onChange={(e) => setIncidentDate(e.target.value)}
                                    className="h-9"
                                />
                            </div>

                            {/* Case Type */}
                            <div className="space-y-1.5">
                                <label className="text-xs font-medium text-muted-foreground">
                                    Case Type
                                </label>
                                <Select
                                    value={caseType}
                                    onValueChange={setCaseType}
                                >
                                    <SelectTrigger className="h-9">
                                        <SelectValue placeholder="Select type" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {SOL_CASE_TYPES.map((t) => (
                                            <SelectItem key={t} value={t}>
                                                {t
                                                    .split("_")
                                                    .map(
                                                        (w) =>
                                                            w.charAt(0).toUpperCase() +
                                                            w.slice(1),
                                                    )
                                                    .join(" ")}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            {/* Jurisdiction */}
                            <div className="space-y-1.5">
                                <label className="text-xs font-medium text-muted-foreground">
                                    Jurisdiction
                                </label>
                                <Select
                                    value={jurisdiction}
                                    onValueChange={setJurisdiction}
                                >
                                    <SelectTrigger className="h-9">
                                        <SelectValue placeholder="Select jurisdiction" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {SOL_JURISDICTIONS.map((j) => (
                                            <SelectItem key={j} value={j}>
                                                {j === "default" ? "Default" : j}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        <Button
                            size="sm"
                            onClick={() => calcMutation.mutate()}
                            disabled={!canCalculate || calcMutation.isPending}
                        >
                            {calcMutation.isPending
                                ? "Calculating..."
                                : "Calculate"}
                        </Button>

                        {/* Results */}
                        {result && (
                            <div className="rounded-lg border p-4 space-y-3 mt-2">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <p className="text-xs font-medium text-muted-foreground uppercase">
                                            Calculated Deadline
                                        </p>
                                        <p className="text-lg font-bold mt-1">
                                            {formatDate(result.deadline)}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-0.5">
                                            {result.case_type
                                                .split("_")
                                                .map(
                                                    (w) =>
                                                        w.charAt(0).toUpperCase() +
                                                        w.slice(1),
                                                )
                                                .join(" ")}{" "}
                                            &middot; {result.jurisdiction}{" "}
                                            &middot; {result.sol_years} year
                                            {result.sol_years !== 1 ? "s" : ""}
                                        </p>
                                    </div>
                                    <div className="text-right">
                                        <p
                                            className={`text-2xl font-extrabold tabular-nums ${
                                                urgencyColor(
                                                    result.days_remaining,
                                                    result.is_expired,
                                                ).text
                                            }`}
                                        >
                                            {result.is_expired
                                                ? 0
                                                : result.days_remaining}
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                            days remaining
                                        </p>
                                    </div>
                                </div>
                                {result.is_expired && (
                                    <Badge
                                        variant="outline"
                                        className="bg-red-500/15 text-red-400 border-red-500/30"
                                    >
                                        EXPIRED
                                    </Badge>
                                )}
                                {!result.is_expired && result.is_urgent && (
                                    <Badge
                                        variant="outline"
                                        className="bg-amber-500/15 text-amber-400 border-amber-500/30"
                                    >
                                        URGENT - Deadline approaching
                                    </Badge>
                                )}
                            </div>
                        )}
                    </CardContent>
                </CollapsibleContent>
            </Card>
        </Collapsible>
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
