// ---- File Upload Component -----------------------------------------------
// Drag-and-drop zone for files AND folders.
// Files are immediately sent to the global upload queue (upload-store).
// No blocking dialog — user can navigate away while uploads continue.
"use client";

import { useState, useCallback, useRef } from "react";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { useUploadStore, extractFilesFromDrop } from "@/lib/stores/upload-store";

interface FileUploadProps {
    caseId: string;
    onUploadComplete?: () => void;
    accept?: string;
    maxSizeMB?: number;
}

export function FileUpload({
    caseId,
    onUploadComplete,
    accept = "*",
    maxSizeMB = 20480, // 20 GB default
}: FileUploadProps) {
    const { getToken } = useAuth();
    const enqueueFiles = useUploadStore((s) => s.enqueueFiles);
    const [dragOver, setDragOver] = useState(false);
    const [processing, setProcessing] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    const handleFiles = useCallback(
        (files: File[]) => {
            if (files.length === 0) return;

            // Size filter with user feedback
            const oversized = files.filter(
                (f) => f.size > maxSizeMB * 1024 * 1024,
            );
            if (oversized.length > 0) {
                const sizeLabel = maxSizeMB >= 1024
                    ? `${(maxSizeMB / 1024).toFixed(0)}GB`
                    : `${maxSizeMB}MB`;
                toast.error(
                    `${oversized.length} file(s) exceed the ${sizeLabel} limit and were skipped`,
                );
            }

            const validFiles = files.filter(
                (f) => f.size <= maxSizeMB * 1024 * 1024,
            );

            if (validFiles.length === 0) return;

            const { queued, filtered } = enqueueFiles(caseId, validFiles, getToken);

            if (filtered > 0) {
                toast.warning(
                    `${filtered} file(s) were skipped (hidden, blocked type, or empty)`,
                );
            }

            if (queued > 0) {
                toast.success(
                    `${queued} file${queued > 1 ? "s" : ""} queued for upload`,
                );
            }

            onUploadComplete?.();
        },
        [caseId, maxSizeMB, enqueueFiles, getToken, onUploadComplete],
    );

    const handleDrop = useCallback(
        async (e: React.DragEvent) => {
            e.preventDefault();
            setDragOver(false);
            setProcessing(true);

            try {
                // Extract files — supports folders via webkitGetAsEntry
                const files = await extractFilesFromDrop(e.dataTransfer);
                handleFiles(files);
            } catch {
                toast.error("Failed to read dropped files");
            } finally {
                setProcessing(false);
            }
        },
        [handleFiles],
    );

    const handleInputChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            if (e.target.files) {
                handleFiles(Array.from(e.target.files));
            }
            // Reset so same files can be re-selected
            if (inputRef.current) inputRef.current.value = "";
        },
        [handleFiles],
    );

    const sizeLabel = maxSizeMB >= 1024
        ? `${(maxSizeMB / 1024).toFixed(0)}GB`
        : `${maxSizeMB}MB`;

    return (
        <div
            onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            className={`
                border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
                transition-colors duration-200
                ${dragOver
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-muted-foreground/50"
                }
            `}
        >
            <input
                ref={inputRef}
                type="file"
                multiple
                accept={accept}
                onChange={handleInputChange}
                className="hidden"
            />
            <div className="text-3xl mb-2">
                {processing ? "\u23F3" : "\uD83D\uDCC1"}
            </div>
            <p className="text-sm font-medium">
                {processing
                    ? "Reading folder contents..."
                    : dragOver
                        ? "Drop files or folders here"
                        : "Drag & drop files or folders, or click to browse"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
                {sizeLabel} max per file &middot; uploads run in background
            </p>
        </div>
    );
}
