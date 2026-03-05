// ---- Module Notes --------------------------------------------------------
// Expandable per-module attorney notes with auto-save on blur.
"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "@clerk/nextjs";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

interface ModuleNotesProps {
    caseId: string;
    prepId: string | null;
    moduleKey: string;
    /** Display label (defaults to moduleKey) */
    label?: string;
    /** Start collapsed (default: true) */
    defaultCollapsed?: boolean;
}

export function ModuleNotes({
    caseId,
    prepId,
    moduleKey,
    label = "Attorney Notes",
    defaultCollapsed = true,
}: ModuleNotesProps) {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [open, setOpen] = useState(!defaultCollapsed);
    const [localText, setLocalText] = useState("");
    const [isDirty, setIsDirty] = useState(false);
    const saveTimeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);

    // Load notes
    const { data, isLoading } = useQuery({
        queryKey: ["module-notes", caseId, prepId, moduleKey],
        queryFn: () =>
            api.get<{ module_key: string; text: string }>(
                `/cases/${caseId}/preparations/${prepId}/notes/${moduleKey}`,
                { getToken },
            ),
        enabled: !!prepId,
    });

    // Sync server data into local state
    useEffect(() => {
        if (data?.text !== undefined && !isDirty) {
            setLocalText(data.text);
        }
    }, [data, isDirty]);

    // Save mutation
    const saveMutation = useMutation({
        mutationFn: (text: string) =>
            api.put(
                `/cases/${caseId}/preparations/${prepId}/notes/${moduleKey}`,
                { text },
                { getToken },
            ),
        onSuccess: () => {
            setIsDirty(false);
            queryClient.invalidateQueries({
                queryKey: ["module-notes", caseId, prepId, moduleKey],
            });
        },
    });

    // Debounced auto-save (2s after last keystroke)
    const scheduleAutoSave = useCallback((text: string) => {
        if (saveTimeoutRef.current) {
            clearTimeout(saveTimeoutRef.current);
        }
        saveTimeoutRef.current = setTimeout(() => {
            if (prepId) {
                saveMutation.mutate(text);
            }
        }, 2000);
    }, [prepId, saveMutation]);

    // Clean up timeout on unmount
    useEffect(() => {
        return () => {
            if (saveTimeoutRef.current) {
                clearTimeout(saveTimeoutRef.current);
            }
        };
    }, []);

    const handleChange = (text: string) => {
        setLocalText(text);
        setIsDirty(true);
        scheduleAutoSave(text);
    };

    // Save on blur (immediate)
    const handleBlur = () => {
        if (isDirty && prepId) {
            if (saveTimeoutRef.current) {
                clearTimeout(saveTimeoutRef.current);
            }
            saveMutation.mutate(localText);
        }
    };

    if (!prepId) return null;

    const hasNotes = localText.trim().length > 0;

    return (
        <Collapsible open={open} onOpenChange={setOpen} className="mt-4">
            <CollapsibleTrigger asChild>
                <button
                    className={cn(
                        "flex items-center gap-2 text-xs font-medium w-full py-1.5 px-2 rounded hover:bg-accent/50 transition-colors text-left",
                        hasNotes ? "text-foreground" : "text-muted-foreground",
                    )}
                >
                    <span className={cn(
                        "transition-transform text-[10px]",
                        open ? "rotate-90" : "",
                    )}>
                        ▶
                    </span>
                    <span aria-hidden="true">📝</span>
                    {label}
                    {hasNotes && !open && (
                        <span className="ml-1 text-emerald-400" aria-hidden="true">●</span>
                    )}
                    {isDirty && (
                        <span className="ml-auto text-[10px] text-amber-400">unsaved</span>
                    )}
                    {saveMutation.isPending && (
                        <span className="ml-auto text-[10px] text-blue-400">saving...</span>
                    )}
                </button>
            </CollapsibleTrigger>

            <CollapsibleContent>
                <div className="mt-1">
                    <textarea
                        value={localText}
                        onChange={(e) => handleChange(e.target.value)}
                        onBlur={handleBlur}
                        placeholder="Add your notes here..."
                        rows={4}
                        className="w-full resize-y rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring min-h-[80px]"
                    />
                </div>
            </CollapsibleContent>
        </Collapsible>
    );
}
