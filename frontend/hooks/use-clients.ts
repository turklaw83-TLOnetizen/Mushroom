// ---- Client Hooks -------------------------------------------------------
// TanStack Query hooks for CRM client operations.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";

export interface ClientItem {
    id: string;
    name: string;
    first_name?: string;
    last_name?: string;
    middle_name?: string;
    suffix?: string;
    email?: string;
    phone?: string;
    intake_status?: string;
    client_type?: string;
    home_address?: string;
}

export interface ClientListResponse {
    items: ClientItem[];
    total: number;
}

export interface CreateClientInput {
    first_name?: string;
    last_name?: string;
    middle_name?: string;
    suffix?: string;
    email?: string;
    phone?: string;
    mailing_address?: string;
}

/** Display name: prefer first+middle+last+suffix, fall back to name field. */
export function clientDisplayName(c: ClientItem): string {
    if (c.first_name || c.last_name) {
        const parts = [c.first_name, c.middle_name, c.last_name].filter(Boolean);
        let display = parts.join(" ");
        if (c.suffix) display += `, ${c.suffix}`;
        return display || "Unnamed Client";
    }
    return c.name || "Unnamed Client";
}

/** Fetch all clients for autocomplete / combobox use. */
export function useClients(enabled = true) {
    const { getToken } = useAuth();

    return useQuery({
        queryKey: ["crm-clients"],
        queryFn: () =>
            api.get<ClientListResponse>("/crm/clients", { getToken }),
        enabled,
        staleTime: 30_000,
    });
}

/** Create a new client via POST /crm/clients. */
export function useCreateClient() {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (input: CreateClientInput) =>
            api.post<{ id: string; status: string }>("/crm/clients", input, { getToken }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["crm-clients"] });
        },
    });
}
