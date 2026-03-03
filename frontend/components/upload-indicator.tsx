// ---- Upload Indicator ---------------------------------------------------
// Floating bottom-right widget showing background upload progress.
// Rendered in root layout — persists across all page navigation.
"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useUploadStore, type UploadItem } from "@/lib/stores/upload-store";
import { Button } from "@/components/ui/button";

// ---- Helpers ------------------------------------------------------------

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function statusIcon(status: UploadItem["status"]): string {
    switch (status) {
        case "queued":
            return "\u23F3"; // hourglass
        case "uploading":
            return "\u2B06\uFE0F"; // up arrow
        case "done":
            return "\u2705"; // check mark
        case "error":
            return "\u274C"; // cross
    }
}

// ---- Component ----------------------------------------------------------

export function UploadIndicator() {
    const items = useUploadStore((s) => s.items);
    const expanded = useUploadStore((s) => s.expanded);
    const setExpanded = useUploadStore((s) => s.setExpanded);
    const removeItem = useUploadStore((s) => s.removeItem);
    const clearCompleted = useUploadStore((s) => s.clearCompleted);
    const queryClient = useQueryClient();

    // Listen for upload-complete events to invalidate query cache
    useEffect(() => {
        function handleComplete(e: Event) {
            const detail = (e as CustomEvent).detail;
            if (detail?.caseId) {
                queryClient.invalidateQueries({
                    queryKey: ["cases", detail.caseId, "files"],
                });
            }
        }
        window.addEventListener("upload-complete", handleComplete);
        return () => window.removeEventListener("upload-complete", handleComplete);
    }, [queryClient]);

    // Nothing to show
    if (items.length === 0) return null;

    const uploading = items.filter((i) => i.status === "uploading");
    const queued = items.filter((i) => i.status === "queued");
    const done = items.filter((i) => i.status === "done");
    const errored = items.filter((i) => i.status === "error");
    const active = [...uploading, ...queued];
    const total = items.length;
    const completedCount = done.length + errored.length;

    // Overall progress
    const overallProgress =
        total > 0
            ? Math.round(
                  items.reduce((sum, i) => sum + (i.status === "done" ? 100 : i.progress), 0) /
                      total,
              )
            : 0;

    // Summary text
    let summaryText: string;
    if (active.length > 0) {
        const current = uploading[0];
        summaryText = current
            ? `Uploading ${completedCount + 1} of ${total}: ${current.fileName}`
            : `${queued.length} file(s) queued...`;
    } else if (errored.length > 0) {
        summaryText = `${errored.length} upload(s) failed`;
    } else {
        summaryText = `${done.length} file(s) uploaded`;
    }

    return (
        <div className="fixed bottom-4 right-4 z-50 w-80 max-w-[calc(100vw-2rem)]">
            {/* Collapsed bar */}
            <div
                className="bg-card border border-border rounded-lg shadow-2xl cursor-pointer overflow-hidden"
                onClick={() => setExpanded(!expanded)}
            >
                <div className="flex items-center justify-between px-3 py-2.5">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                        {active.length > 0 && (
                            <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin shrink-0" />
                        )}
                        <span className="text-sm font-medium truncate">
                            {summaryText}
                        </span>
                    </div>
                    <span className="text-xs text-muted-foreground shrink-0 ml-2">
                        {expanded ? "\u25BC" : "\u25B2"}
                    </span>
                </div>

                {/* Progress bar */}
                {active.length > 0 && (
                    <div className="h-1 bg-muted">
                        <div
                            className="h-full bg-primary transition-all duration-300"
                            style={{ width: `${overallProgress}%` }}
                        />
                    </div>
                )}
            </div>

            {/* Expanded panel */}
            {expanded && (
                <div className="mt-1 bg-card border border-border rounded-lg shadow-2xl max-h-64 overflow-y-auto">
                    {items.map((item) => (
                        <div
                            key={item.id}
                            className="flex items-center gap-2 px-3 py-2 border-b border-border last:border-b-0"
                        >
                            <span className="text-sm shrink-0">
                                {statusIcon(item.status)}
                            </span>
                            <div className="flex-1 min-w-0">
                                <p className="text-xs font-medium truncate">
                                    {item.fileName}
                                </p>
                                <div className="flex items-center gap-2">
                                    <span className="text-[10px] text-muted-foreground">
                                        {formatSize(item.fileSize)}
                                    </span>
                                    {item.status === "uploading" && (
                                        <>
                                            <div className="flex-1 h-1 bg-muted rounded-full overflow-hidden">
                                                <div
                                                    className="h-full bg-primary transition-all duration-200"
                                                    style={{ width: `${item.progress}%` }}
                                                />
                                            </div>
                                            <span className="text-[10px] text-muted-foreground">
                                                {item.progress}%
                                            </span>
                                        </>
                                    )}
                                    {item.status === "error" && (
                                        <span className="text-[10px] text-destructive truncate">
                                            {item.error}
                                        </span>
                                    )}
                                </div>
                            </div>
                            {(item.status === "done" || item.status === "error") && (
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-5 w-5 text-muted-foreground hover:text-foreground shrink-0"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        removeItem(item.id);
                                    }}
                                >
                                    <span className="text-xs">{"\u2715"}</span>
                                </Button>
                            )}
                        </div>
                    ))}

                    {/* Actions row */}
                    {(done.length > 0 || errored.length > 0) && (
                        <div className="flex justify-end px-3 py-1.5 border-t border-border">
                            <Button
                                variant="ghost"
                                size="sm"
                                className="text-xs h-6"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    clearCompleted();
                                }}
                            >
                                Clear finished
                            </Button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
