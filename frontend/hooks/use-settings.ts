// ---- Settings Hooks -----------------------------------------------------
// TanStack Query hooks for settings & Google Calendar integration.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";

// ---- Types --------------------------------------------------------------

export interface GCalStatus {
    connected: boolean;
    email: string;
    calendar_id: string;
    calendar_name: string;
    connected_at: string;
    has_credentials: boolean;
}

export interface GCalCalendar {
    id: string;
    summary: string;
    description: string;
    primary: boolean;
    access_role: string;
    background_color: string;
}

interface GCalCalendarsResponse {
    items: GCalCalendar[];
    connected: boolean;
}

// ---- Google Calendar Queries --------------------------------------------

export function useGoogleCalStatus() {
    const { getToken } = useAuth();

    return useQuery({
        queryKey: ["gcal-status"],
        queryFn: () =>
            api.get<GCalStatus>("/calendar/google/status", { getToken }),
    });
}

export function useGoogleCalendars(enabled = true) {
    const { getToken } = useAuth();

    return useQuery({
        queryKey: ["gcal-calendars"],
        queryFn: () =>
            api.get<GCalCalendarsResponse>("/calendar/google/calendars", { getToken }),
        enabled,
    });
}

// ---- Google Calendar Mutations ------------------------------------------

export function useConnectGoogleCal() {
    const { getToken } = useAuth();

    return useMutation({
        mutationFn: () =>
            api.post<{ auth_url: string }>("/calendar/google/connect", {}, { getToken }),
    });
}

export function useGoogleCalCallback() {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (input: { auth_code: string; email?: string }) =>
            api.post<{ status: string }>("/calendar/google/callback", input, { getToken }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["gcal-status"] });
            queryClient.invalidateQueries({ queryKey: ["gcal-calendars"] });
        },
    });
}

export function useDisconnectGoogleCal() {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: () =>
            api.post<{ status: string }>("/calendar/google/disconnect", {}, { getToken }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["gcal-status"] });
            queryClient.invalidateQueries({ queryKey: ["gcal-calendars"] });
        },
    });
}

export function useSaveCalendarChoice() {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (input: { calendar_id: string; calendar_name: string }) =>
            api.post<{ status: string }>("/calendar/google/calendars", input, { getToken }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["gcal-status"] });
        },
    });
}

export function useSyncGoogleCal() {
    const { getToken } = useAuth();

    return useMutation({
        mutationFn: (input: { case_id?: string; direction?: string }) =>
            api.post<{ status: string; result: Record<string, number> }>(
                "/calendar/google/sync",
                input,
                { getToken },
            ),
    });
}
