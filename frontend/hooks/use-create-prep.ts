// ---- Prep Creation Hook -------------------------------------------------
// Hook for creating new preparations.
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { toast } from "sonner";

interface CreatePrepInput {
    type: string;
    name?: string;
}

export function useCreatePrep(caseId: string) {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (input: CreatePrepInput) =>
            api.post(`/cases/${caseId}/preparations`, { prep_type: input.type, name: input.name }, { getToken }),
        onSuccess: () => {
            toast.success("Preparation created");
            queryClient.invalidateQueries({ queryKey: ["cases", caseId, "preparations"] });
        },
        onError: (err: Error) => {
            toast.error("Failed to create preparation", { description: err.message });
        },
    });
}
