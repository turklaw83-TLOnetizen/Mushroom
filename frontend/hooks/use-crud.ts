// ---- useCrud Hook --------------------------------------------------------
// Composable CRUD operations for any entity. Eliminates boilerplate across
// all pages: auto-handles toast, query invalidation, and loading states.
//
// Builds on top of useMutationWithToast and the existing api-client pattern,
// bundling list query + create/update/delete mutations into a single hook.
//
// Usage:
//   const { query, items, create, update, remove } = useCrud<Witness, WitnessInput>({
//       queryKey: queryKeys.witnesses.list(caseId, prepId),
//       listPath: routes.witnesses.list(caseId, prepId),
//       createPath: routes.witnesses.add(caseId, prepId),
//       updatePath: (id) => routes.witnesses.update(caseId, prepId, id),
//       deletePath: (id) => routes.witnesses.delete(caseId, prepId, id),
//       entityName: "Witness",
//   });
//
//   // Read:    items (Witness[]), isLoading, error
//   // Create:  create.mutate({ name: "John", type: "state" })
//   // Update:  update.mutate({ id: "abc", data: { name: "Jane" } })
//   // Delete:  remove.mutate("abc")
//   // Refetch: refetch()
"use client";

import { useQuery, useMutation, useQueryClient, type InvalidateQueryFilters } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";

// ---- Types ---------------------------------------------------------------

interface CrudConfig<TEntity, TCreateInput = Partial<TEntity>, TUpdateInput = Partial<TEntity>> {
    /** React Query cache key for the list query */
    queryKey: readonly unknown[];
    /** API path to GET the list */
    listPath: string;
    /** API path to POST a new entity (optional -- omit to disable create) */
    createPath?: string;
    /** Function that returns the API path for PUT/PATCH by entity ID */
    updatePath?: (id: string) => string;
    /** Function that returns the API path for DELETE by entity ID */
    deletePath?: (id: string) => string;
    /** Human-readable entity name for toast messages (e.g., "Witness", "Task") */
    entityName?: string;
    /** Additional query keys to invalidate on any mutation */
    extraInvalidateKeys?: InvalidateQueryFilters["queryKey"][];
    /** Use PATCH instead of PUT for updates */
    usePatch?: boolean;
    /** Transform the API response before caching (e.g., extract .items) */
    select?: (data: unknown) => TEntity[];
    /** Enable/disable the list query */
    enabled?: boolean;
    /** Callback after successful create */
    onCreateSuccess?: (result: unknown) => void;
    /** Callback after successful update */
    onUpdateSuccess?: (result: unknown) => void;
    /** Callback after successful delete */
    onDeleteSuccess?: () => void;
}

interface CrudReturn<TEntity, TCreateInput, TUpdateInput> {
    /** The list query result */
    query: ReturnType<typeof useQuery<TEntity[]>>;
    /** Shortcut: query.data ?? [] */
    items: TEntity[];
    /** Shortcut: query.isLoading */
    isLoading: boolean;
    /** Shortcut: query.error */
    error: Error | null;
    /** Create mutation -- call .mutate(input) or .mutateAsync(input) */
    create: ReturnType<typeof useMutation<unknown, Error, TCreateInput>>;
    /** Update mutation -- call .mutate({ id, data }) */
    update: ReturnType<typeof useMutation<unknown, Error, { id: string; data: TUpdateInput }>>;
    /** Delete mutation -- call .mutate(id) */
    remove: ReturnType<typeof useMutation<unknown, Error, string>>;
    /** Force refetch the list */
    refetch: () => void;
}

// ---- Hook ----------------------------------------------------------------

export function useCrud<
    TEntity,
    TCreateInput = Partial<TEntity>,
    TUpdateInput = Partial<TEntity>,
>({
    queryKey,
    listPath,
    createPath,
    updatePath,
    deletePath,
    entityName = "Item",
    extraInvalidateKeys = [],
    usePatch = false,
    select,
    enabled = true,
    onCreateSuccess,
    onUpdateSuccess,
    onDeleteSuccess,
}: CrudConfig<TEntity, TCreateInput, TUpdateInput>): CrudReturn<TEntity, TCreateInput, TUpdateInput> {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    // Invalidate list + any extras
    const invalidateAll = () => {
        queryClient.invalidateQueries({ queryKey: queryKey as unknown[] });
        extraInvalidateKeys.forEach((key) => {
            queryClient.invalidateQueries({ queryKey: key as unknown[] });
        });
    };

    // ---- List Query ---------------------------------------------------------
    const query = useQuery<TEntity[]>({
        queryKey: queryKey as unknown[],
        queryFn: async () => {
            const result = await api.get<unknown>(listPath, { getToken });
            if (select) return select(result);
            // Auto-detect response shape: bare array or { items: [...] }
            if (Array.isArray(result)) return result as TEntity[];
            if (result && typeof result === "object" && "items" in result) {
                return (result as { items: TEntity[] }).items;
            }
            return result as TEntity[];
        },
        enabled,
    });

    // ---- Create Mutation ----------------------------------------------------
    const create = useMutation<unknown, Error, TCreateInput>({
        mutationFn: async (input) => {
            if (!createPath) throw new Error(`Create not configured for ${entityName}`);
            return api.post(createPath, input, { getToken });
        },
        onSuccess: (result) => {
            toast.success(`${entityName} created`);
            invalidateAll();
            onCreateSuccess?.(result);
        },
        onError: (err) => {
            toast.error(`Failed to create ${entityName.toLowerCase()}`, { description: err.message });
        },
    });

    // ---- Update Mutation ----------------------------------------------------
    const update = useMutation<unknown, Error, { id: string; data: TUpdateInput }>({
        mutationFn: async ({ id, data }) => {
            if (!updatePath) throw new Error(`Update not configured for ${entityName}`);
            const path = updatePath(id);
            return usePatch
                ? api.patch(path, data, { getToken })
                : api.put(path, data, { getToken });
        },
        onSuccess: (result) => {
            toast.success(`${entityName} updated`);
            invalidateAll();
            onUpdateSuccess?.(result);
        },
        onError: (err) => {
            toast.error(`Failed to update ${entityName.toLowerCase()}`, { description: err.message });
        },
    });

    // ---- Delete Mutation ----------------------------------------------------
    const remove = useMutation<unknown, Error, string>({
        mutationFn: async (id) => {
            if (!deletePath) throw new Error(`Delete not configured for ${entityName}`);
            return api.delete(deletePath(id), { getToken });
        },
        onSuccess: () => {
            toast.success(`${entityName} deleted`);
            invalidateAll();
            onDeleteSuccess?.();
        },
        onError: (err) => {
            toast.error(`Failed to delete ${entityName.toLowerCase()}`, { description: err.message });
        },
    });

    return {
        query,
        items: (query.data as TEntity[]) ?? [],
        isLoading: query.isLoading,
        error: query.error,
        create,
        update,
        remove,
        refetch: () => query.refetch(),
    };
}
