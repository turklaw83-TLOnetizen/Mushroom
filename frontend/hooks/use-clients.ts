// ---- Client Hooks -------------------------------------------------------
// TanStack Query hooks for CRM client operations.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";

export interface ClientItem {
    id: string;
    name: string;
    first_name: string;
    last_name: string;
    email: string;
    phone: string;
    mailing_address: string;
}

interface ClientListResponse {
    items: ClientItem[];
}

export interface CreateClientInput {
    first_name: string;
    last_name: string;
    name?: string;
    phone?: string;
    email?: string;
    mailing_address?: string;
}

// ---- Queries ------------------------------------------------------------

export function useClients(query: string = "") {
    const { getToken } = useAuth();

    return useQuery({
        queryKey: ["clients", query],
        queryFn: () =>
            api.get<ClientListResponse>("/crm/clients", {
                params: query ? { q: query } : {},
                getToken,
            }),
        // Keep previous data while new query loads for smoother UX
        placeholderData: (prev) => prev,
    });
}

// ---- Mutations ----------------------------------------------------------

export function useCreateClient() {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (input: CreateClientInput) =>
            api.post<{ id: string; status: string }>("/crm/clients", input, { getToken }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["clients"] });
        },
    });
}
