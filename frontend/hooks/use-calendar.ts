// ---- Calendar Hooks -----------------------------------------------------
// TanStack Query hooks for calendar operations.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";

// ---- Types --------------------------------------------------------------

export interface CalendarEvent {
    id: string;
    case_id: string;
    title: string;
    date: string;
    time: string;
    type: string;
    event_type: string;
    description: string;
    location: string;
    status: string;
    end_time: string;
    days_until?: number;
}

export interface DayCell {
    day: number;
    date: string;
    events: CalendarEvent[];
    is_today: boolean;
}

export interface MonthCalendar {
    year: number;
    month: number;
    month_name: string;
    weeks: (DayCell | null)[][];
    total_events: number;
}

export interface CalendarStats {
    total_events: number;
    active_events: number;
    upcoming: number;
    this_week: number;
    past_due: number;
    completed: number;
    cancelled: number;
    type_breakdown: Record<string, number>;
}

// ---- Queries ------------------------------------------------------------

export function useMonthCalendar(year: number, month: number) {
    const { getToken } = useAuth();

    return useQuery({
        queryKey: ["calendar", "month", year, month],
        queryFn: () =>
            api.get<MonthCalendar>("/calendar/month", {
                params: { year, month },
                getToken,
            }),
    });
}

export function useUpcomingEvents(days = 14) {
    const { getToken } = useAuth();

    return useQuery({
        queryKey: ["calendar", "upcoming", days],
        queryFn: () =>
            api.get<CalendarEvent[]>("/calendar/upcoming", {
                params: { days },
                getToken,
            }),
    });
}

export function useCalendarStats() {
    const { getToken } = useAuth();

    return useQuery({
        queryKey: ["calendar", "stats"],
        queryFn: () =>
            api.get<CalendarStats>("/calendar/stats", { getToken }),
    });
}

// ---- Mutations ----------------------------------------------------------

export function useCreateCalendarEvent() {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (input: {
            title: string;
            date: string;
            time?: string;
            type?: string;
            description?: string;
            location?: string;
            case_id?: string;
        }) =>
            api.post<{ status: string; id: string }>("/calendar/events", input, {
                getToken,
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["calendar"] });
        },
    });
}

export function useUpdateEventStatus() {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({
            eventId,
            status,
        }: {
            eventId: string;
            status: string;
        }) =>
            api.patch(`/calendar/events/${eventId}/status`, { status }, {
                getToken,
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["calendar"] });
        },
    });
}
