// ---- Calendar Tab (with detail panel) -----------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { DataPage } from "@/components/shared/data-page";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { DetailPanel, type DetailField } from "@/components/shared/detail-panel";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface CalendarEvent {
    id: string;
    title: string;
    date: string;
    time: string;
    type: string;
    description: string;
    location: string;
}

const typeColors: Record<string, string> = {
    hearing: "bg-red-500/15 text-red-400 border-red-500/30",
    deadline: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    meeting: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    event: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
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

    const query = useQuery({
        queryKey: ["calendar", caseId],
        queryFn: () =>
            api.get<CalendarEvent[]>("/calendar/events", {
                params: { case_id: caseId },
                getToken,
            }),
    });

    const createMutation = useMutationWithToast<EventInput>({
        mutationFn: (data) => api.post("/calendar/events", { ...data, case_id: caseId }, { getToken }),
        successMessage: "Event created",
        invalidateKeys: [["calendar", caseId]],
        onSuccess: () => setDialogOpen(false),
    });

    const deleteMutation = useMutationWithToast<string>({
        mutationFn: (eventId) => api.delete(`/calendar/events/${eventId}`, { getToken }),
        successMessage: "Event deleted",
        invalidateKeys: [["calendar", caseId]],
        onSuccess: () => setDeleteTarget(null),
    });

    const updateMutation = useMutationWithToast<EventInput>({
        mutationFn: (data) => {
            if (!detailEvent) throw new Error("No event selected");
            return api.put(`/calendar/events/${detailEvent.id}`, { ...data, case_id: caseId }, { getToken });
        },
        successMessage: "Event updated",
        invalidateKeys: [["calendar", caseId]],
        onSuccess: () => setDetailEvent(null),
    });

    return (
        <DataPage
            title="Calendar"
            subtitle="Events, deadlines, and hearings for this case"
            query={query}
            searchFilter={(e, s) =>
                e.title.toLowerCase().includes(s) || e.type.toLowerCase().includes(s)
            }
            searchPlaceholder="Search events..."
            createLabel={canEdit ? "Add Event" : null}
            onCreateClick={() => setDialogOpen(true)}
            renderItem={(event, i) => (
                <Card
                    key={event.id || i}
                    className="hover:bg-accent/30 transition-colors group cursor-pointer"
                    onClick={() => setDetailEvent(event)}
                >
                    <CardContent className="flex items-center justify-between py-3">
                        <div className="flex items-center gap-3">
                            <span aria-hidden="true" className="text-2xl">
                                {event.type === "hearing" ? "⚖️" :
                                    event.type === "deadline" ? "⏰" :
                                        event.type === "meeting" ? "🤝" : "📅"}
                            </span>
                            <div>
                                <p className="font-medium text-sm">{event.title}</p>
                                <p className="text-xs text-muted-foreground">
                                    {event.date}{event.time && ` at ${event.time}`}
                                    {event.location && ` · ${event.location}`}
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <Badge variant="outline" className={typeColors[event.type] || typeColors.event}>
                                {event.type}
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
                                    ✕
                                </Button>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}
        >
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
                    values={detailEvent as EventInput}
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
        </DataPage>
    );
}
