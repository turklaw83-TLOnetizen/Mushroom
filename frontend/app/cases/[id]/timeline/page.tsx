// ---- Timeline Editor Tab ------------------------------------------------
"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import type { TimelineEvent } from "@/types/api";
import { usePrep } from "@/hooks/use-prep";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

// ---- Types --------------------------------------------------------------

interface PrepState {
    timeline?: TimelineEvent[];
    _custom_timeline_events?: TimelineEvent[];
    [key: string]: unknown;
}

// ---- Schema & Fields ----------------------------------------------------

const eventSchema = z.object({
    date: z.string().min(1, "Date is required").max(100),
    title: z.string().min(1, "Title is required").max(500),
    description: z.string().max(5000).optional().default(""),
    source_ref: z.string().max(500).optional().default(""),
});
type EventInput = z.infer<typeof eventSchema>;

const createFields: FieldConfig<EventInput>[] = [
    { name: "date", label: "Date", required: true, placeholder: "e.g. 2024-03-15 or March 15, 2024" },
    { name: "title", label: "Title", required: true, placeholder: "e.g. Arrest occurred" },
    { name: "description", label: "Description", type: "textarea", placeholder: "What happened..." },
    { name: "source_ref", label: "Source Reference", placeholder: "e.g. Police report p.3" },
];

// ---- Helpers ------------------------------------------------------------

function formatDate(dateStr: string): string {
    try {
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return d.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    } catch {
        return dateStr;
    }
}

function sortByDate(events: TimelineEvent[]): TimelineEvent[] {
    return [...events].sort((a, b) => {
        const da = new Date(a.date).getTime();
        const db = new Date(b.date).getTime();
        if (isNaN(da) && isNaN(db)) return 0;
        if (isNaN(da)) return 1;
        if (isNaN(db)) return -1;
        return da - db;
    });
}

// ---- Component ----------------------------------------------------------

export default function TimelinePage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, isLoading: prepLoading } = usePrep();
    const { canEdit, canDelete } = useRole();
    const queryClient = useQueryClient();

    const [dialogOpen, setDialogOpen] = useState(false);
    const [editIndex, setEditIndex] = useState<number | null>(null);
    const [editEvent, setEditEvent] = useState<TimelineEvent | null>(null);
    const [deleteIndex, setDeleteIndex] = useState<number | null>(null);
    const [deleteEvent, setDeleteEvent] = useState<TimelineEvent | null>(null);
    const [search, setSearch] = useState("");
    const [isEditing, setIsEditing] = useState(false);
    const [editForm, setEditForm] = useState<EventInput>({ date: "", title: "", description: "", source_ref: "" });

    const queryKey = ["timeline", caseId, activePrepId];

    // Fetch prep state which contains both AI-generated timeline and custom events
    const { data: prepState, isLoading } = useQuery({
        queryKey,
        queryFn: () =>
            api.get<PrepState>(
                `/cases/${caseId}/preparations/${activePrepId}`,
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    // Merge AI-generated timeline with custom events
    const allEvents = useMemo(() => {
        const aiEvents = (prepState?.timeline ?? []).map((e) => ({ ...e, _custom: false }));
        const customEvents = (prepState?._custom_timeline_events ?? []).map((e) => ({ ...e, _custom: true }));
        return sortByDate([...aiEvents, ...customEvents]);
    }, [prepState]);

    // Filter by search
    const filtered = useMemo(() => {
        if (!search) return allEvents;
        const s = search.toLowerCase();
        return allEvents.filter(
            (e) =>
                e.title?.toLowerCase().includes(s) ||
                e.description?.toLowerCase().includes(s) ||
                e.date?.toLowerCase().includes(s) ||
                e.source_ref?.toLowerCase().includes(s),
        );
    }, [allEvents, search]);

    // ---- Mutations ----------------------------------------------------------

    const addMutation = useMutationWithToast<EventInput>({
        mutationFn: async (data) => {
            const existing = prepState?._custom_timeline_events ?? [];
            const updated = [...existing, { ...data, _custom: true }];
            return api.put(
                `/cases/${caseId}/preparations/${activePrepId}/strategy`,
                { _custom_timeline_events: updated },
                { getToken },
            );
        },
        successMessage: "Event added to timeline",
        invalidateKeys: [queryKey],
        onSuccess: () => setDialogOpen(false),
    });

    const updateMutation = useMutationWithToast<{ index: number; data: EventInput }>({
        mutationFn: async ({ index, data }) => {
            // Find which custom event this corresponds to
            const event = allEvents[index];
            if (event?._custom) {
                const customEvents = [...(prepState?._custom_timeline_events ?? [])];
                const customIdx = customEvents.findIndex(
                    (ce) => ce.date === event.date && ce.title === event.title,
                );
                if (customIdx >= 0) {
                    customEvents[customIdx] = { ...data, _custom: true };
                    return api.put(
                        `/cases/${caseId}/preparations/${activePrepId}/strategy`,
                        { _custom_timeline_events: customEvents },
                        { getToken },
                    );
                }
            }
            // For AI-generated events, update via the timeline array
            const timeline = [...(prepState?.timeline ?? [])];
            const aiIdx = timeline.findIndex(
                (te) => te.date === event.date && te.title === event.title,
            );
            if (aiIdx >= 0) {
                timeline[aiIdx] = { ...data };
                return api.put(
                    `/cases/${caseId}/preparations/${activePrepId}/strategy`,
                    { timeline },
                    { getToken },
                );
            }
            throw new Error("Event not found");
        },
        successMessage: "Event updated",
        invalidateKeys: [queryKey],
        onSuccess: () => {
            setEditIndex(null);
            setEditEvent(null);
            setIsEditing(false);
        },
    });

    const deleteMutation = useMutationWithToast<number>({
        mutationFn: async (index) => {
            const event = allEvents[index];
            if (event?._custom) {
                const customEvents = (prepState?._custom_timeline_events ?? []).filter(
                    (ce) => !(ce.date === event.date && ce.title === event.title),
                );
                return api.put(
                    `/cases/${caseId}/preparations/${activePrepId}/strategy`,
                    { _custom_timeline_events: customEvents },
                    { getToken },
                );
            }
            // AI-generated: remove from timeline array
            const timeline = (prepState?.timeline ?? []).filter(
                (te) => !(te.date === event.date && te.title === event.title),
            );
            return api.put(
                `/cases/${caseId}/preparations/${activePrepId}/strategy`,
                { timeline },
                { getToken },
            );
        },
        successMessage: "Event removed",
        invalidateKeys: [queryKey],
        onSuccess: () => {
            setDeleteIndex(null);
            setDeleteEvent(null);
        },
    });

    // ---- Inline Edit Handlers -----------------------------------------------

    const startEdit = (event: TimelineEvent, index: number) => {
        if (!canEdit) return;
        setEditIndex(index);
        setEditEvent(event);
        setEditForm({
            date: event.date || "",
            title: event.title || "",
            description: event.description || "",
            source_ref: event.source_ref || "",
        });
        setIsEditing(true);
    };

    const cancelEdit = () => {
        setEditIndex(null);
        setEditEvent(null);
        setIsEditing(false);
    };

    const saveEdit = () => {
        if (editIndex === null) return;
        updateMutation.mutate({ index: editIndex, data: editForm });
    };

    // ---- Guard: no prep selected --------------------------------------------

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">Create a preparation first to view the timeline.</p>
            </div>
        );
    }

    // ---- Render -------------------------------------------------------------

    return (
        <div className="space-y-5">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">Timeline</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Chronological case events — AI-generated and custom
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {canEdit && (
                        <Button onClick={() => setDialogOpen(true)} size="sm" className="gap-1.5">
                            <span>+</span> Add Event
                        </Button>
                    )}
                </div>
            </div>

            {/* Search */}
            <div className="flex items-center gap-3">
                <Input
                    placeholder="Search timeline..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="max-w-sm"
                />
                {search && filtered.length !== allEvents.length && (
                    <span className="text-xs text-muted-foreground">
                        {filtered.length} of {allEvents.length}
                    </span>
                )}
            </div>

            {/* Timeline Content */}
            {isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 6 }).map((_, i) => (
                        <Skeleton key={i} className="h-20 w-full rounded-lg" />
                    ))}
                </div>
            ) : filtered.length === 0 ? (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        {search
                            ? "No events match your search."
                            : "No timeline events yet. Run analysis or add events manually."}
                    </CardContent>
                </Card>
            ) : (
                <div className="relative">
                    {/* Vertical line */}
                    <div className="absolute left-[19px] top-4 bottom-4 w-px bg-border" />

                    <div className="space-y-2">
                        {filtered.map((event, i) => {
                            const globalIndex = allEvents.indexOf(event);
                            const isEditingThis = isEditing && editIndex === globalIndex;

                            return (
                                <div key={`${event.date}-${event.title}-${i}`} className="flex gap-3 items-start relative">
                                    {/* Timeline dot */}
                                    <div className="w-10 h-10 rounded-full bg-card border border-border flex items-center justify-center shrink-0 z-10">
                                        <div
                                            className={`w-2.5 h-2.5 rounded-full ${
                                                event._custom
                                                    ? "bg-blue-400"
                                                    : "bg-muted-foreground"
                                            }`}
                                        />
                                    </div>

                                    {/* Event card */}
                                    {isEditingThis ? (
                                        <Card className="flex-1 border-primary/50">
                                            <CardContent className="py-3 space-y-3">
                                                <div className="grid grid-cols-2 gap-2">
                                                    <div className="space-y-1">
                                                        <label className="text-xs font-medium text-muted-foreground">Date</label>
                                                        <Input
                                                            value={editForm.date}
                                                            onChange={(e) => setEditForm((f) => ({ ...f, date: e.target.value }))}
                                                            className="h-8 text-sm"
                                                        />
                                                    </div>
                                                    <div className="space-y-1">
                                                        <label className="text-xs font-medium text-muted-foreground">Title</label>
                                                        <Input
                                                            value={editForm.title}
                                                            onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                                                            className="h-8 text-sm"
                                                        />
                                                    </div>
                                                </div>
                                                <div className="space-y-1">
                                                    <label className="text-xs font-medium text-muted-foreground">Description</label>
                                                    <textarea
                                                        value={editForm.description}
                                                        onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
                                                        rows={2}
                                                        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
                                                    />
                                                </div>
                                                <div className="space-y-1">
                                                    <label className="text-xs font-medium text-muted-foreground">Source Reference</label>
                                                    <Input
                                                        value={editForm.source_ref}
                                                        onChange={(e) => setEditForm((f) => ({ ...f, source_ref: e.target.value }))}
                                                        className="h-8 text-sm"
                                                    />
                                                </div>
                                                <div className="flex justify-end gap-2">
                                                    <Button variant="outline" size="sm" onClick={cancelEdit}>
                                                        Cancel
                                                    </Button>
                                                    <Button
                                                        size="sm"
                                                        onClick={saveEdit}
                                                        disabled={updateMutation.isPending}
                                                    >
                                                        {updateMutation.isPending ? "Saving..." : "Save"}
                                                    </Button>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ) : (
                                        <Card
                                            className="flex-1 hover:bg-accent/20 transition-colors group cursor-pointer"
                                            onClick={() => startEdit(event, globalIndex)}
                                        >
                                            <CardContent className="py-2.5">
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-xs font-mono text-muted-foreground whitespace-nowrap">
                                                            {formatDate(event.date)}
                                                        </span>
                                                        <p className="text-sm font-medium">{event.title}</p>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        {event._custom && (
                                                            <Badge variant="outline" className="text-[10px] text-blue-400 border-blue-500/30">
                                                                Custom
                                                            </Badge>
                                                        )}
                                                        {event.source_ref && (
                                                            <Badge variant="secondary" className="text-[10px]">
                                                                {event.source_ref}
                                                            </Badge>
                                                        )}
                                                        {canDelete && (
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive"
                                                                aria-label={`Delete ${event.title}`}
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    setDeleteIndex(globalIndex);
                                                                    setDeleteEvent(event);
                                                                }}
                                                            >
                                                                ✕
                                                            </Button>
                                                        )}
                                                    </div>
                                                </div>
                                                {event.description && (
                                                    <p className="text-xs text-muted-foreground mt-1 ml-0 line-clamp-2">
                                                        {event.description}
                                                    </p>
                                                )}
                                            </CardContent>
                                        </Card>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Summary */}
            {!isLoading && allEvents.length > 0 && (
                <div className="flex items-center gap-4 pt-2 border-t border-border">
                    <span className="text-xs text-muted-foreground">
                        {allEvents.length} event{allEvents.length !== 1 ? "s" : ""}
                    </span>
                    <span className="text-xs text-muted-foreground">
                        {allEvents.filter((e) => e._custom).length} custom
                    </span>
                    <span className="text-xs text-muted-foreground">
                        {allEvents.filter((e) => !e._custom).length} AI-generated
                    </span>
                </div>
            )}

            {/* Create Dialog */}
            {canEdit && (
                <FormDialog
                    open={dialogOpen}
                    onOpenChange={setDialogOpen}
                    title="Add Timeline Event"
                    description="Add a custom event to the case timeline."
                    schema={eventSchema}
                    defaultValues={{ date: "", title: "", description: "", source_ref: "" }}
                    fields={createFields}
                    onSubmit={(data) => addMutation.mutate(data)}
                    submitLabel="Add Event"
                    isLoading={addMutation.isPending}
                />
            )}

            {/* Delete Confirm */}
            <ConfirmDialog
                open={deleteIndex !== null}
                onOpenChange={(open) => {
                    if (!open) { setDeleteIndex(null); setDeleteEvent(null); }
                }}
                title="Remove Event"
                description={`Remove "${deleteEvent?.title}" from the timeline?`}
                confirmLabel="Remove"
                onConfirm={() => {
                    if (deleteIndex !== null) deleteMutation.mutate(deleteIndex);
                }}
                isLoading={deleteMutation.isPending}
            />
        </div>
    );
}
