// ---- Calendar Grid Component --------------------------------------------
// Reusable month grid used by master calendar and case calendar.
"use client";

import { cn } from "@/lib/utils";
import type { DayCell, CalendarEvent } from "@/hooks/use-calendar";

// Event type → color class for dot indicators
const TYPE_DOT_COLORS: Record<string, string> = {
    "Court Date": "bg-red-500",
    "Filing Deadline": "bg-orange-500",
    "Client Meeting": "bg-blue-500",
    "Deposition": "bg-violet-500",
    "Mediation": "bg-cyan-500",
    "Consultation": "bg-green-500",
    "Internal": "bg-slate-500",
    "Other": "bg-purple-500",
    // Frontend shorthand types
    hearing: "bg-red-500",
    deadline: "bg-orange-500",
    meeting: "bg-blue-500",
    event: "bg-slate-400",
};

// Event type → emoji
const TYPE_ICONS: Record<string, string> = {
    "Court Date": "\u2696\ufe0f",
    "Filing Deadline": "\ud83d\udcc4",
    "Client Meeting": "\ud83d\udc64",
    "Deposition": "\ud83d\udccb",
    "Mediation": "\ud83e\udd1d",
    "Consultation": "\ud83d\udcac",
    "Internal": "\ud83c\udfe2",
    "Other": "\ud83d\udcc5",
    hearing: "\u2696\ufe0f",
    deadline: "\u23f0",
    meeting: "\ud83e\udd1d",
    event: "\ud83d\udcc5",
};

const DAY_HEADERS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

interface CalendarGridProps {
    weeks: (DayCell | null)[][];
    selectedDate?: string;
    onDayClick?: (date: string, events: CalendarEvent[]) => void;
}

export function CalendarGrid({
    weeks,
    selectedDate,
    onDayClick,
}: CalendarGridProps) {
    return (
        <div className="border rounded-lg overflow-hidden">
            {/* Day headers */}
            <div className="grid grid-cols-7 bg-muted/50 border-b">
                {DAY_HEADERS.map((h) => (
                    <div
                        key={h}
                        className="px-2 py-2 text-center text-xs font-medium text-muted-foreground"
                    >
                        {h}
                    </div>
                ))}
            </div>

            {/* Week rows */}
            {weeks.map((week, wi) => (
                <div key={wi} className="grid grid-cols-7 border-b last:border-b-0">
                    {week.map((cell, di) => {
                        if (!cell) {
                            return (
                                <div
                                    key={`${wi}-${di}`}
                                    className="min-h-[80px] border-r last:border-r-0 bg-muted/20"
                                />
                            );
                        }

                        const isSelected = selectedDate === cell.date;
                        const hasEvents = cell.events.length > 0;

                        return (
                            <button
                                key={cell.date}
                                type="button"
                                onClick={() =>
                                    onDayClick?.(cell.date, cell.events)
                                }
                                className={cn(
                                    "min-h-[80px] border-r last:border-r-0 p-1.5 text-left transition-colors hover:bg-accent/30",
                                    isSelected && "bg-accent/50 ring-1 ring-primary/50",
                                    cell.is_today && "bg-primary/5"
                                )}
                            >
                                {/* Day number */}
                                <span
                                    className={cn(
                                        "inline-flex items-center justify-center w-6 h-6 text-xs rounded-full",
                                        cell.is_today &&
                                            "bg-primary text-primary-foreground font-bold"
                                    )}
                                >
                                    {cell.day}
                                </span>

                                {/* Event indicators */}
                                {hasEvents && (
                                    <div className="mt-1 space-y-0.5">
                                        {cell.events.slice(0, 2).map((evt) => (
                                            <div
                                                key={evt.id}
                                                className="flex items-center gap-1 truncate"
                                            >
                                                <span
                                                    className={cn(
                                                        "w-1.5 h-1.5 rounded-full flex-shrink-0",
                                                        TYPE_DOT_COLORS[
                                                            evt.event_type || evt.type
                                                        ] || "bg-slate-400"
                                                    )}
                                                />
                                                <span className="text-[10px] truncate text-muted-foreground">
                                                    {evt.title}
                                                </span>
                                            </div>
                                        ))}
                                        {cell.events.length > 2 && (
                                            <span className="text-[10px] text-muted-foreground pl-2.5">
                                                +{cell.events.length - 2} more
                                            </span>
                                        )}
                                    </div>
                                )}
                            </button>
                        );
                    })}
                </div>
            ))}
        </div>
    );
}

// ---- Helper: get icon for event type ------------------------------------
export function getEventTypeIcon(type: string): string {
    return TYPE_ICONS[type] || "\ud83d\udcc5";
}

// ---- Helper: urgency color for days_until -------------------------------
export function getUrgencyColor(daysUntil: number): string {
    if (daysUntil <= 0) return "text-red-500";
    if (daysUntil <= 3) return "text-yellow-500";
    return "text-green-500";
}

export function getUrgencyDot(daysUntil: number): string {
    if (daysUntil <= 0) return "\ud83d\udd34";
    if (daysUntil <= 3) return "\ud83d\udfe1";
    return "\ud83d\udfe2";
}
