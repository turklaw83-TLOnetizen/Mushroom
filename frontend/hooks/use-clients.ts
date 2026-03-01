// ---- Client Hooks -------------------------------------------------------
// TanStack Query hook for fetching CRM clients (used by client combobox).

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";

export interface ClientItem {
    id: string;
    name: string;
    first_name?: string;
    last_name?: string;
    email?: string;
    phone?: string;
    intake_status?: string;
    client_type?: string;
}

export interface ClientListResponse {
    items: ClientItem[];
    total: number;
}

/** Display name: prefer first+last, fall back to name field. */
export function clientDisplayName(c: ClientItem): string {
    if (c.first_name || c.last_name) {
        return [c.first_name, c.last_name].filter(Boolean).join(" ");
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
        staleTime: 30_000, // Cache for 30s — clients don't change often
    });
}
