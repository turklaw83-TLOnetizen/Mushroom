// ---- Case Hooks ---------------------------------------------------------
// TanStack Query hooks for case CRUD operations.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";

// ---- Types (until we auto-generate from OpenAPI) ------------------------

export interface CaseItem {
    id: string;
    name: string;
    description: string;
    case_type: string;
    case_category: string;
    case_subcategory: string;
    client_name: string;
    jurisdiction: string;
    phase: string;
    sub_phase: string;
    status: string;
    pinned: boolean;
    assigned_to: string[];
    docket_number: string;
    charges: string;
    court_name: string;
    date_of_incident: string;
    opposing_counsel: string;
    jurisdiction_type: string;
    county: string;
    district: string;
    created_at: string;
    last_updated: string;
    readiness_score?: number | null;
}

export interface PaginatedCases {
    items: CaseItem[];
    total: number;
    page: number;
    per_page: number;
    pages: number;
}

export interface CreateCaseInput {
    case_name: string;
    description?: string;
    case_category?: string;
    case_subcategory?: string;
    case_type?: string;
    client_name?: string;
    jurisdiction?: string;
    docket_number?: string;
    charges?: string;
    court_name?: string;
    date_of_incident?: string;
    opposing_counsel?: string;
    jurisdiction_type?: string;
    county?: string;
    district?: string;
    client_id?: string;
}

// ---- Queries ------------------------------------------------------------

export function useCases(page = 1, perPage = 25, includeArchived = false) {
    const { getToken } = useAuth();

    return useQuery({
        queryKey: ["cases", { page, perPage, includeArchived }],
        queryFn: () =>
            api.get<PaginatedCases>("/cases", {
                params: {
                    page,
                    per_page: perPage,
                    include_archived: includeArchived,
                },
                getToken,
            }),
        staleTime: 30_000,            // Don't refetch for 30 seconds
        retry: 1,                     // Only retry once on failure
        refetchOnWindowFocus: false,   // Don't refetch when tab gains focus
    });
}

export function useCase(caseId: string | null) {
    const { getToken } = useAuth();

    return useQuery({
        queryKey: ["cases", caseId],
        queryFn: () => api.get<CaseItem>(`/cases/${caseId}`, { getToken }),
        enabled: !!caseId,
    });
}

// ---- Mutations ----------------------------------------------------------

export function useCreateCase() {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (input: CreateCaseInput) =>
            api.post<{ case_id: string; message: string }>("/cases", input, { getToken }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["cases"] });
        },
    });
}

export function useDeleteCase() {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (caseId: string) =>
            api.delete(`/cases/${caseId}`, { getToken }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["cases"] });
        },
    });
}
