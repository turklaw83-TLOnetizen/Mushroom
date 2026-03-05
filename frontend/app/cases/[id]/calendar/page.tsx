// ---- Calendar Tab (with month grid + events list) -----------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import {
    useMonthCalendar,
    useUpdateEventStatus,
    type CalendarEvent as CalEvent,
} from "@/hooks/use-calendar";
import { DataPage } from "@/components/shared/data-page";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { DetailPanel, type DetailField } from "@/components/shared/detail-panel";
import {
    CalendarGrid,
    getEventTypeIcon,
} from "@/components/shared/calendar-grid";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";

interface CalendarEvent {
    id: string;
    title: string;
    date: string;
    time: string;
    type: string;
    event_type: string;
    description: string;
    location: string;
    status: string;
}

const typeColors: Record<string, string> = {
    hearing: "bg-red-500/15 text-red-400 border-red-500/30",
    deadline: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    meeting: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    event: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    "Court Date": "bg-red-500/15 text-red-400 border-red-500/30",
    "Filing Deadline": "bg-amber-500/15 text-amber-400 border-amber-500/30",
    "Client Meeting": "bg-blue-500/15 text-blue-400 border-blue-500/30",
    "Deposition": "bg-violet-500/15 text-violet-400 border-violet-500/30",
};

const statusColors: Record<string, string> = {
    scheduled: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    completed: "bg-green-500/15 text-green-400 border-green-500/30",
    cancelled: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
};

const eventSchema = z.object({
    title: z.string().min(1, "Title required").max(500),
    date: z.string().min(1, "Date required"),
    time: z.string().max(10).optional().default(""),
    type: z.string().min(1),
    description: z.string().max(2000).optional().default(""),
    location: z.string().max(500).optional().default(""),
});
type EventInput = z.infer<typeof eventSchema>;

const eventFields: FieldConfig<EventInput>[] = [
    { name: "title", label: "Title", required: true, placeholder: "e.g. Motion Hearing" },
    { name: "date", label: "Date", required: true, placeholder: "2024-03-15" },
    { name: "time", label: "Time", placeholder: "09:00 AM" },
    {
        name: "type", label: "Type", type: "select", required: true, options: [
            { value: "hearing", label: "Hearing" },
            { value: "deadline", label: "Deadline" },
            { value: "meeting", label: "Meeting" },
            { value: "event", label: "Other Event" },
        ],
    },
    { name: "description", label: "Description", type: "textarea" },
    { name: "location", label: "Location", placeholder: "Courtroom 4B" },
];

const detailFields: DetailField<EventInput>[] = [
    { name: "title", label: "Title" },
    { name: "date", label: "Date" },
    { name: "time", label: "Time" },
    {
        name: "type", label: "Type", type: "select", options: [
            { value: "hearing", label: "Hearing" },
            { value: "deadline", label: "Deadline" },
            { value: "meeting", label: "Meeting" },
            { value: "event", label: "Other Event" },
        ],
    },
    { name: "description", label: "Description", type: "textarea" },
    { name: "location", label: "Location" },
];

export default function CalendarPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { canEdit, canDelete } = useRole();
    const [dialogOpen, setDialogOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<CalendarEvent | null>(null);
    const [detailEvent, setDetailEvent] = useState<CalendarEvent | null>(null);

    // Month grid state
    const today = new Date();
    const [gridYear, setGridYear] = useState(today.getFullYear());
    const [gridMonth, setGridMonth] = useState(today.getMonth() + 1);
    const [selectedDate, setSelectedDate] = useState<string | null>(null);
    const [dayEvents, setDayEvents] = useState<CalEvent[]>([]);

    const query = useQuery({
        queryKey: ["calendar", caseId],
        queryFn: () =>
            api.get<CalendarEvent[]>("/calendar/events", {
                params: { case_id: caseId },
                getToken,
            }),
    });

    const { data: monthData, isLoading: monthLoading } = useMonthCalendar(gridYear, gridMonth);
    const updateStatus = useUpdateEventStatus();

    // Filter month data to only this case's events
    const filteredMonthData = monthData
        ? {
              ...monthData,
              weeks: monthData.weeks.map((week) =>
                  week.map((cell) => {
                      if (!cell) return null;
                      return {
                          ...cell,
                          events: cell.events.filter(
                              (e) => e.case_id === caseId
                          ),
                      };
                  })
              ),
          }
        : null;

    const createMutation = useMutationWithToast<EventInput>({
        mutationFn: (data) => api.post("/calendar/events", { ...data, case_id: caseId }, { getToken }),
        successMessage: "Event created",
        invalidateKeys: [["calendar", caseId], ["calendar", "month", gridYear, gridMonth]],
        onSuccess: () => setDialogOpen(false),
    });

    const deleteMutation = useMutationWithToast<string>({
        mutationFn: (eventId) => api.delete(`/calendar/events/${eventId}`, { getToken }),
        successMessage: "Event deleted",
        invalidateKeys: [["calendar", caseId], ["calendar", "month", gridYear, gridMonth]],
        onSuccess: () => setDeleteTarget(null),
    });

    const updateMutation = useMutationWithToast<EventInput>({
        mutationFn: (data) => {
            if (!detailEvent) throw new Error("No event selected");
            return api.put(`/calendar/events/${detailEvent.id}`, { ...data, case_id: caseId }, { getToken });
        },
        successMessage: "Event updated",
        invalidateKeys: [["calendar", caseId], ["calendar", "month", gridYear, gridMonth]],
        onSuccess: () => setDetailEvent(null),
    });

    const navigateMonth = (delta: number) => {
        let m = gridMonth + delta;
        let y = gridYear;
        if (m < 1) { m = 12; y--; }
        else if (m > 12) { m = 1; y++; }
        setGridMonth(m);
        setGridYear(y);
        setSelectedDate(null);
        setDayEvents([]);
    };

    const handleStatusChange = async (eventId: string, status: string) => {
        try {
            await updateStatus.mutateAsync({ eventId, status });
            toast.success(`Event ${status}`);
        } catch {
            toast.error("Failed to update status");
        }
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-semibold">Calendar</h2>
                    <p className="text-sm text-muted-foreground">
                        Events, deadlines, and hearings for this case
                    </p>
                </div>
                {canEdit && (
                    <Button size="sm" onClick={() => setDialogOpen(true)}>
                        + Add Event
                    </Button>
                )}
            </div>

            <Tabs defaultValue="calendar">
                <TabsList>
                    <TabsTrigger value="calendar">Calendar</TabsTrigger>
                    <TabsTrigger value="list">Events List</TabsTrigger>
                </TabsList>

                {/* Calendar Grid Tab */}
                <TabsContent value="calendar" className="space-y-4 mt-4">
                    {/* Month nav */}
                    <div className="flex items-center gap-2">
                        <Button variant="outline" size="sm" onClick={() => navigateMonth(-1)}>
                            Prev
                        </Button>
                        <span className="text-sm font-semibold flex-1 text-center">
                            {filteredMonthData?.month_name || ""} {gridYear}
                        </span>
                        <Button variant="outline" size="sm" onClick={() => navigateMonth(1)}>
                            Next
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => {
                            setGridYear(today.getFullYear());
                            setGridMonth(today.getMonth() + 1);
                        }}>
                            Today
                        </Button>
                    </div>

                    {monthLoading ? (
                        <Skeleton className="h-[400px] w-full rounded-lg" />
                    ) : filteredMonthData ? (
                        <CalendarGrid
                            weeks={filteredMonthData.weeks}
                            selectedDate={selectedDate ?? undefined}
                            onDayClick={(date, events) => {
                                setSelectedDate(date);
                                setDayEvents(events);
                            }}
                        />
                    ) : null}

                    {/* Day detail */}
                    {selectedDate && (
                        <Card>
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm">
                                    {selectedDate} &mdash; {dayEvents.length} event(s)
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                {dayEvents.length === 0 ? (
                                    <p className="text-sm text-muted-foreground">No events.</p>
                                ) : (
                                    <div className="space-y-2">
                                        {dayEvents.map((evt) => (
                                            <div key={evt.id} className="flex items-center gap-3 p-2 rounded hover:bg-accent/30">
                                                <span>{getEventTypeIcon(evt.event_type || evt.type)}</span>
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-sm font-medium">{evt.title}</p>
                                                    <p className="text-xs text-muted-foreground">
                                                        {evt.time}{evt.location && ` \u00b7 ${evt.location}`}
                                                    </p>
                                                </div>
                                                <div className="flex items-center gap-1">
                                                    <Badge variant="outline" className={statusColors[evt.status] || statusColors.scheduled}>
                                                        {evt.status || "scheduled"}
                                                    </Badge>
                                                    {canEdit && evt.status === "scheduled" && (
                                                        <>
                                                            <Button variant="ghost" size="sm" className="h-6 px-2 text-xs text-green-500"
                                                                onClick={() => handleStatusChange(evt.id, "completed")}>
                                                                Done
                                                            </Button>
                                                            <Button variant="ghost" size="sm" className="h-6 px-2 text-xs text-zinc-500"
                                                                onClick={() => handleStatusChange(evt.id, "cancelled")}>
                                                                Cancel
                                                            </Button>
                                                        </>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>

                {/* Events List Tab */}
                <TabsContent value="list" className="mt-4">
                    <DataPage
                        title=""
                        query={query}
                        searchFilter={(e, s) =>
                            e.title.toLowerCase().includes(s) || (e.type || "").toLowerCase().includes(s)
                        }
                        searchPlaceholder="Search events..."
                        renderItem={(event, i) => (
                            <Card
                                key={event.id || i}
                                className="hover:bg-accent/30 transition-colors group cursor-pointer"
                                onClick={() => setDetailEvent(event)}
                            >
                                <CardContent className="flex items-center justify-between py-3">
                                    <div className="flex items-center gap-3">
                                        <span aria-hidden="true" className="text-2xl">
                                            {getEventTypeIcon(event.event_type || event.type)}
                                        </span>
                                        <div>
                                            <p className="font-medium text-sm">{event.title}</p>
                                            <p className="text-xs text-muted-foreground">
                                                {event.date}{event.time && ` at ${event.time}`}
                                                {event.location && ` \u00b7 ${event.location}`}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {event.status && event.status !== "scheduled" && (
                                            <Badge variant="outline" className={statusColors[event.status] || ""}>
                                                {event.status}
                                            </Badge>
                                        )}
                                        <Badge variant="outline" className={typeColors[event.event_type || event.type] || typeColors.event}>
                                            {event.event_type || event.type}
                                        </Badge>
                                        {canDelete && (
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive"
                                                aria-label={`Delete ${event.title}`}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    setDeleteTarget(event);
                                                }}
                                            >
                                                &#x2715;
                                            </Button>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>
                        )}
                    />
                </TabsContent>
            </Tabs>

            {/* Dialogs */}
            {canEdit && (
                <FormDialog
                    open={dialogOpen}
                    onOpenChange={setDialogOpen}
                    title="Add Event"
                    description="Create a new calendar event for this case."
                    schema={eventSchema}
                    defaultValues={{ title: "", date: "", time: "", type: "hearing", description: "", location: "" }}
                    fields={eventFields}
                    onSubmit={(data) => createMutation.mutate(data)}
                    submitLabel="Create Event"
                    isLoading={createMutation.isPending}
                />
            )}
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
                title="Delete Event"
                description={`Delete "${deleteTarget?.title}"? This cannot be undone.`}
                onConfirm={() => { if (deleteTarget) deleteMutation.mutate(deleteTarget.id); }}
                isLoading={deleteMutation.isPending}
            />
            {detailEvent && (
                <DetailPanel
                    open={!!detailEvent}
                    onOpenChange={(open) => !open && setDetailEvent(null)}
                    title={detailEvent.title}
                    description={`${detailEvent.date}${detailEvent.time ? ` at ${detailEvent.time}` : ""}`}
                    schema={eventSchema}
                    values={detailEvent as unknown as EventInput}
                    fields={detailFields}
                    onSave={(data) => updateMutation.mutate(data)}
                    readOnly={!canEdit}
                    isLoading={updateMutation.isPending}
                    onDelete={canDelete ? () => {
                        setDeleteTarget(detailEvent);
                        setDetailEvent(null);
                    } : undefined}
                />
            )}
        </div>
    );
}
