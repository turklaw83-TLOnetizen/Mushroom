// ---- Files Tab (with FileUpload, Delete, Force OCR, and Bulk Operations) --
"use client";

import { useState, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { DataPage } from "@/components/shared/data-page";
import { FileUpload } from "@/components/shared/file-upload";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";

interface FileItem {
    filename: string;
    size: number;
    tags: string[];
    uploaded_at?: string;
    ocr_status?: string;
}

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

// ---- Bulk Actions Bar ---------------------------------------------------

function FileBulkBar({
    selectedCount,
    onDelete,
    onTag,
    onForceOcr,
    onClear,
    isDeleting,
    isTagging,
    isOcring,
}: {
    selectedCount: number;
    onDelete: () => void;
    onTag: () => void;
    onForceOcr: () => void;
    onClear: () => void;
    isDeleting: boolean;
    isTagging: boolean;
    isOcring: boolean;
}) {
    return (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 bg-card border border-border rounded-xl shadow-2xl px-5 py-3 flex items-center gap-4 animate-in slide-in-from-bottom-4 duration-200">
            <span className="text-sm font-medium whitespace-nowrap">
                {selectedCount} file(s) selected
            </span>
            <div className="h-5 w-px bg-border" />
            <Button
                size="sm"
                variant="outline"
                onClick={onForceOcr}
                disabled={isOcring}
            >
                {isOcring ? "Starting..." : "Force OCR Selected"}
            </Button>
            <Button
                size="sm"
                variant="outline"
                onClick={onTag}
                disabled={isTagging}
            >
                {isTagging ? "Tagging..." : "Tag Selected"}
            </Button>
            <Button
                size="sm"
                variant="destructive"
                onClick={onDelete}
                disabled={isDeleting}
            >
                {isDeleting ? "Deleting..." : "Delete Selected"}
            </Button>
            <div className="h-5 w-px bg-border" />
            <Button
                size="sm"
                variant="ghost"
                className="text-xs"
                onClick={onClear}
            >
                Clear
            </Button>
        </div>
    );
}

// ---- Main Component -----------------------------------------------------

export default function FilesPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [uploadOpen, setUploadOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

    // Bulk selection state
    const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
    const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
    const [tagDialogOpen, setTagDialogOpen] = useState(false);
    const [tagValue, setTagValue] = useState("");

    const query = useQuery({
        queryKey: ["cases", caseId, "files"],
        queryFn: () => api.get<FileItem[]>(`/cases/${caseId}/files`, { getToken }),
    });

    const files = useMemo(() => query.data ?? [], [query.data]);

    // Selection helpers
    const allSelected = files.length > 0 && selectedFiles.size === files.length;

    const toggleFile = useCallback((filename: string) => {
        setSelectedFiles((prev) => {
            const next = new Set(prev);
            if (next.has(filename)) next.delete(filename);
            else next.add(filename);
            return next;
        });
    }, []);

    const selectAll = useCallback(() => {
        setSelectedFiles(new Set(files.map((f) => f.filename)));
    }, [files]);

    const deselectAll = useCallback(() => {
        setSelectedFiles(new Set());
    }, []);

    // Delete file mutation (single)
    const deleteFile = useMutationWithToast({
        mutationFn: (filename: string) =>
            api.delete(`/cases/${caseId}/files/${encodeURIComponent(filename)}`, { getToken }),
        successMessage: "File deleted",
        errorMessage: "Failed to delete file",
        invalidateKeys: [["cases", caseId, "files"]],
        onSuccess: () => setDeleteTarget(null),
    });

    // Force OCR mutation (single)
    const forceOcr = useMutationWithToast({
        mutationFn: (filename: string) =>
            api.post(`/cases/${caseId}/analysis/ingestion/start`, {
                force_ocr: true,
                target_file: filename,
            }, { getToken }),
        successMessage: "Force OCR started for file",
        errorMessage: "Failed to start OCR",
    });

    // Bulk delete mutation (sequential delete of selected files)
    const bulkDelete = useMutationWithToast({
        mutationFn: async () => {
            const filenames = Array.from(selectedFiles);
            const results = await Promise.allSettled(
                filenames.map((fn) =>
                    api.delete(`/cases/${caseId}/files/${encodeURIComponent(fn)}`, { getToken })
                )
            );
            const failed = results.filter((r) => r.status === "rejected").length;
            if (failed > 0) {
                throw new Error(`${failed} of ${filenames.length} deletions failed`);
            }
            return { deleted: filenames.length };
        },
        successMessage: `${selectedFiles.size} file(s) deleted`,
        errorMessage: "Bulk delete encountered errors",
        invalidateKeys: [["cases", caseId, "files"]],
        onSuccess: () => {
            deselectAll();
            setBulkDeleteOpen(false);
        },
    });

    // Bulk force OCR mutation
    const bulkForceOcr = useMutationWithToast({
        mutationFn: async () => {
            const filenames = Array.from(selectedFiles);
            // Start OCR for each selected file
            await Promise.allSettled(
                filenames.map((fn) =>
                    api.post(`/cases/${caseId}/analysis/ingestion/start`, {
                        force_ocr: true,
                        target_file: fn,
                    }, { getToken })
                )
            );
            return { queued: filenames.length };
        },
        successMessage: `Force OCR queued for ${selectedFiles.size} file(s)`,
        errorMessage: "Failed to start bulk OCR",
    });

    // Bulk tag mutation
    const bulkTag = useMutationWithToast({
        mutationFn: async (tag: string) => {
            const filenames = Array.from(selectedFiles);
            await Promise.allSettled(
                filenames.map((fn) =>
                    api.patch(`/cases/${caseId}/files/${encodeURIComponent(fn)}/tags`, {
                        tags: [tag],
                        action: "add",
                    }, { getToken })
                )
            );
            return { tagged: filenames.length };
        },
        successMessage: `Tag applied to ${selectedFiles.size} file(s)`,
        errorMessage: "Failed to apply tags",
        invalidateKeys: [["cases", caseId, "files"]],
        onSuccess: () => {
            setTagDialogOpen(false);
            setTagValue("");
        },
    });

    return (
        <DataPage
            title="Files"
            subtitle="Uploaded documents and files for this case"
            query={query}
            searchFilter={(f, s) => f.filename.toLowerCase().includes(s)}
            searchPlaceholder="Search files..."
            createLabel="Upload"
            onCreateClick={() => setUploadOpen(true)}
            headerActions={
                files.length > 0 ? (
                    <div className="flex items-center gap-2">
                        <Button
                            size="sm"
                            variant="ghost"
                            className="text-xs"
                            onClick={allSelected ? deselectAll : selectAll}
                        >
                            {allSelected ? "Deselect All" : "Select All"}
                        </Button>
                        {selectedFiles.size > 0 && (
                            <span className="text-xs text-muted-foreground">
                                {selectedFiles.size} selected
                            </span>
                        )}
                    </div>
                ) : undefined
            }
            renderItem={(file, i) => {
                const isSelected = selectedFiles.has(file.filename);
                return (
                    <Card
                        key={i}
                        className={`group transition-colors ${
                            isSelected
                                ? "bg-primary/5 border-primary/30 hover:bg-primary/10"
                                : "hover:bg-accent/30"
                        }`}
                    >
                        <CardContent className="flex items-center justify-between py-3">
                            <div className="flex items-center gap-3">
                                <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={() => toggleFile(file.filename)}
                                    className="rounded border-border accent-primary cursor-pointer shrink-0"
                                    aria-label={`Select ${file.filename}`}
                                />
                                <span className="text-2xl">{"\u{1F4C4}"}</span>
                                <div>
                                    <p className="font-medium text-sm">{file.filename}</p>
                                    <p className="text-xs text-muted-foreground">
                                        {formatSize(file.size)}
                                        {file.uploaded_at && ` \u00B7 ${file.uploaded_at}`}
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                {/* Action buttons -- visible on hover */}
                                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            forceOcr.mutate(file.filename);
                                        }}
                                        disabled={forceOcr.isPending}
                                        title="Force OCR on this file"
                                    >
                                        {"\u{1F50D}"} OCR
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-7 px-2 text-xs text-muted-foreground hover:text-destructive"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setDeleteTarget(file.filename);
                                        }}
                                        title="Delete this file"
                                    >
                                        {"\u{1F5D1}\uFE0F"}
                                    </Button>
                                </div>
                                {file.tags?.map((tag) => (
                                    <Badge key={tag} variant="secondary" className="text-xs">
                                        {tag}
                                    </Badge>
                                ))}
                                {file.ocr_status && (
                                    <Badge
                                        variant="outline"
                                        className={
                                            file.ocr_status === "complete"
                                                ? "text-emerald-400 border-emerald-500/30"
                                                : "text-amber-400 border-amber-500/30"
                                        }
                                    >
                                        OCR: {file.ocr_status}
                                    </Badge>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                );
            }}
        >
            {/* Floating Bulk Action Bar */}
            {selectedFiles.size > 0 && (
                <FileBulkBar
                    selectedCount={selectedFiles.size}
                    onDelete={() => setBulkDeleteOpen(true)}
                    onTag={() => setTagDialogOpen(true)}
                    onForceOcr={() => bulkForceOcr.mutate({})}
                    onClear={deselectAll}
                    isDeleting={bulkDelete.isPending}
                    isTagging={bulkTag.isPending}
                    isOcring={bulkForceOcr.isPending}
                />
            )}

            {/* Inline Upload Zone (toggleable, not a modal) */}
            {uploadOpen && (
                <div className="mb-4">
                    <FileUpload
                        caseId={caseId}
                        onUploadComplete={() => {
                            // Don't close — user can keep adding files.
                            // Upload happens in background via global queue.
                            queryClient.invalidateQueries({ queryKey: ["cases", caseId, "files"] });
                        }}
                    />
                </div>
            )}

            {/* Single Delete Confirmation Dialog */}
            <ConfirmDialog
                open={deleteTarget !== null}
                onOpenChange={(open) => {
                    if (!open) setDeleteTarget(null);
                }}
                title="Delete file?"
                description={`This will permanently delete "${deleteTarget}". This action cannot be undone.`}
                confirmLabel="Delete"
                onConfirm={() => {
                    if (deleteTarget) deleteFile.mutate(deleteTarget);
                }}
                isLoading={deleteFile.isPending}
                variant="destructive"
            />

            {/* Bulk Delete Confirmation Dialog */}
            <ConfirmDialog
                open={bulkDeleteOpen}
                onOpenChange={setBulkDeleteOpen}
                title={`Delete ${selectedFiles.size} file(s)?`}
                description={`This will permanently delete ${selectedFiles.size} selected file(s). This action cannot be undone.`}
                confirmLabel={`Delete ${selectedFiles.size} File(s)`}
                onConfirm={() => bulkDelete.mutate({})}
                isLoading={bulkDelete.isPending}
                variant="destructive"
            />

            {/* Bulk Tag Dialog */}
            <Dialog open={tagDialogOpen} onOpenChange={setTagDialogOpen}>
                <DialogContent className="sm:max-w-sm">
                    <DialogHeader>
                        <DialogTitle>Tag {selectedFiles.size} File(s)</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-3 py-2">
                        <p className="text-sm text-muted-foreground">
                            Enter a tag to apply to all selected files.
                        </p>
                        <Input
                            placeholder="e.g. evidence, draft, exhibit"
                            value={tagValue}
                            onChange={(e) => setTagValue(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" && tagValue.trim()) {
                                    bulkTag.mutate(tagValue.trim());
                                }
                            }}
                            autoFocus
                        />
                    </div>
                    <DialogFooter>
                        <Button
                            variant="ghost"
                            onClick={() => {
                                setTagDialogOpen(false);
                                setTagValue("");
                            }}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={() => {
                                if (tagValue.trim()) bulkTag.mutate(tagValue.trim());
                            }}
                            disabled={!tagValue.trim() || bulkTag.isPending}
                        >
                            {bulkTag.isPending ? "Applying..." : "Apply Tag"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </DataPage>
    );
}
