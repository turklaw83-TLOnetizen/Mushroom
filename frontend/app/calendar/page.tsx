// ---- Master Calendar Page ------------------------------------------------
"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
    CalendarGrid,
    getEventTypeIcon,
    getUrgencyDot,
} from "@/components/shared/calendar-grid";
import {
    useMonthCalendar,
    useUpcomingEvents,
    useCalendarStats,
    useCreateCalendarEvent,
    type CalendarEvent,
} from "@/hooks/use-calendar";

const EVENT_TYPES = [
    "Court Date",
    "Filing Deadline",
    "Client Meeting",
    "Deposition",
    "Mediation",
    "Consultation",
    "Internal",
    "Other",
];

const statusColors: Record<string, string> = {
    scheduled: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    completed: "bg-green-500/15 text-green-400 border-green-500/30",
    cancelled: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    rescheduled: "bg-amber-500/15 text-amber-400 border-amber-500/30",
};

export default function MasterCalendarPage() {
    const today = new Date();
    const [year, setYear] = useState(today.getFullYear());
    const [month, setMonth] = useState(today.getMonth() + 1);
    const [selectedDate, setSelectedDate] = useState<string | null>(null);
    const [dayEvents, setDayEvents] = useState<CalendarEvent[]>([]);

    // Quick add form state
    const [newTitle, setNewTitle] = useState("");
    const [newDate, setNewDate] = useState("");
    const [newTime, setNewTime] = useState("");
    const [newType, setNewType] = useState("Other");
    const [newLocation, setNewLocation] = useState("");

    const { data: monthData, isLoading: monthLoading } = useMonthCalendar(year, month);
    const { data: upcoming } = useUpcomingEvents(14);
    const { data: stats } = useCalendarStats();
    const createEvent = useCreateCalendarEvent();

    const navigateMonth = (delta: number) => {
        let newMonth = month + delta;
        let newYear = year;
        if (newMonth < 1) {
            newMonth = 12;
            newYear--;
        } else if (newMonth > 12) {
            newMonth = 1;
            newYear++;
        }
        setMonth(newMonth);
        setYear(newYear);
        setSelectedDate(null);
        setDayEvents([]);
    };

    const goToToday = () => {
        setYear(today.getFullYear());
        setMonth(today.getMonth() + 1);
        setSelectedDate(null);
        setDayEvents([]);
    };

    const handleDayClick = (date: string, events: CalendarEvent[]) => {
        setSelectedDate(date);
        setDayEvents(events);
    };

    const handleQuickAdd = async () => {
        if (!newTitle.trim() || !newDate) return;
        try {
            await createEvent.mutateAsync({
                title: newTitle.trim(),
                date: newDate,
                time: newTime,
                type: newType,
                location: newLocation.trim(),
            });
            toast.success("Event created", { description: newTitle });
            setNewTitle("");
            setNewDate("");
            setNewTime("");
            setNewType("Other");
            setNewLocation("");
        } catch (err) {
            toast.error("Failed to create event", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        }
    };

    return (
        <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Master Calendar</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Firm-wide events, hearings, and deadlines
                </p>
            </div>

            {/* Stats bar */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    {[
                        { label: "Total", value: stats.total_events },
                        { label: "Upcoming", value: stats.upcoming },
                        { label: "This Week", value: stats.this_week },
                        { label: "Past Due", value: stats.past_due },
                        { label: "Completed", value: stats.completed },
                    ].map((s) => (
                        <Card key={s.label} className="glass-card">
                            <CardContent className="p-3 text-center">
                                <p className="text-2xl font-bold">{s.value}</p>
                                <p className="text-xs text-muted-foreground uppercase tracking-wider">
                                    {s.label}
                                </p>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-6">
                {/* Left: Calendar grid */}
                <div className="space-y-4">
                    {/* Month navigation */}
                    <div className="flex items-center gap-2">
                        <Button variant="outline" size="sm" onClick={() => navigateMonth(-1)}>
                            Prev
                        </Button>
                        <h2 className="text-lg font-semibold flex-1 text-center">
                            {monthData?.month_name || ""} {year}
                        </h2>
                        <Button variant="outline" size="sm" onClick={() => navigateMonth(1)}>
                            Next
                        </Button>
                        <Button variant="outline" size="sm" onClick={goToToday}>
                            Today
                        </Button>
                    </div>

                    {/* Grid */}
                    {monthLoading ? (
                        <Skeleton className="h-[480px] w-full rounded-lg" />
                    ) : monthData ? (
                        <CalendarGrid
                            weeks={monthData.weeks}
                            selectedDate={selectedDate ?? undefined}
                            onDayClick={handleDayClick}
                        />
                    ) : null}

                    {/* Day detail */}
                    {selectedDate && (
                        <Card>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-base">
                                    Events on {selectedDate}
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                {dayEvents.length === 0 ? (
                                    <p className="text-sm text-muted-foreground">
                                        No events on this date.
                                    </p>
                                ) : (
                                    <div className="space-y-3">
                                        {dayEvents.map((evt) => (
                                            <div
                                                key={evt.id}
                                                className="flex items-start gap-3 p-2 rounded-md hover:bg-accent/30 transition-colors"
                                            >
                                                <span className="text-xl mt-0.5">
                                                    {getEventTypeIcon(
                                                        evt.event_type || evt.type
                                                    )}
                                                </span>
                                                <div className="flex-1 min-w-0">
                                                    <p className="font-medium text-sm">
                                                        {evt.title}
                                                    </p>
                                                    <p className="text-xs text-muted-foreground">
                                                        {evt.time && `${evt.time} `}
                                                        {evt.location &&
                                                            `\u00b7 ${evt.location}`}
                                                    </p>
                                                    {evt.description && (
                                                        <p className="text-xs text-muted-foreground mt-1">
                                                            {evt.description}
                                                        </p>
                                                    )}
                                                </div>
                                                <Badge
                                                    variant="outline"
                                                    className={
                                                        statusColors[evt.status] ||
                                                        statusColors.scheduled
                                                    }
                                                >
                                                    {evt.status || "scheduled"}
                                                </Badge>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}
                </div>

                {/* Right: Upcoming sidebar */}
                <div className="space-y-4">
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base">
                                Upcoming (14 days)
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {!upcoming || upcoming.length === 0 ? (
                                <p className="text-sm text-muted-foreground">
                                    No upcoming events.
                                </p>
                            ) : (
                                <div className="space-y-2">
                                    {upcoming.slice(0, 12).map((evt) => (
                                        <div
                                            key={evt.id}
                                            className="flex items-start gap-2"
                                        >
                                            <span className="text-sm mt-0.5">
                                                {getUrgencyDot(evt.days_until ?? 999)}
                                            </span>
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium truncate">
                                                    {evt.title}
                                                </p>
                                                <p className="text-xs text-muted-foreground">
                                                    {evt.date}
                                                    {evt.time && ` ${evt.time}`}
                                                    {" "}({evt.days_until ?? "?"}d)
                                                </p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Quick Add */}
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-base">Quick Add Event</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-2">
                            <Input
                                placeholder="Event title *"
                                value={newTitle}
                                onChange={(e) => setNewTitle(e.target.value)}
                            />
                            <div className="grid grid-cols-2 gap-2">
                                <Input
                                    type="date"
                                    value={newDate}
                                    onChange={(e) => setNewDate(e.target.value)}
                                />
                                <Input
                                    type="time"
                                    value={newTime}
                                    onChange={(e) => setNewTime(e.target.value)}
                                />
                            </div>
                            <Select value={newType} onValueChange={setNewType}>
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {EVENT_TYPES.map((t) => (
                                        <SelectItem key={t} value={t}>
                                            {t}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <Input
                                placeholder="Location"
                                value={newLocation}
                                onChange={(e) => setNewLocation(e.target.value)}
                            />
                            <Button
                                className="w-full"
                                disabled={
                                    createEvent.isPending ||
                                    !newTitle.trim() ||
                                    !newDate
                                }
                                onClick={handleQuickAdd}
                            >
                                {createEvent.isPending ? "Creating..." : "Create Event"}
                            </Button>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}
