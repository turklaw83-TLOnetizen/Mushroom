// ---- useFileUpload Hook -------------------------------------------------
// Provides file upload with progress tracking and drag-and-drop support.
"use client";

import { useState, useCallback, useRef, type DragEvent } from "react";
import { useAuth } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { extractFilesFromDrop } from "@/lib/stores/upload-store";

interface UploadProgress {
    /** 0 to 100 */
    percent: number;
    /** Currently uploading file name */
    fileName: string;
    /** Total files in batch */
    total: number;
    /** Current file index (1-based) */
    current: number;
}

interface UseFileUploadOptions {
    /** API path to upload to (e.g. "/cases/123/files") */
    uploadPath: string;
    /** Query keys to invalidate on success */
    invalidateKeys?: unknown[][];
    /** Accepted file types (e.g. [".pdf", ".docx"]) */
    accept?: string[];
    /** Max file size in bytes (default 20GB) */
    maxSize?: number;
    /** Called on successful upload */
    onSuccess?: () => void;
}

export function useFileUpload(options: UseFileUploadOptions) {
    const { uploadPath, invalidateKeys = [], accept, maxSize = 20 * 1024 * 1024 * 1024, onSuccess } = options;
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    const [isUploading, setIsUploading] = useState(false);
    const [progress, setProgress] = useState<UploadProgress | null>(null);
    const [isDragOver, setIsDragOver] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const uploadFiles = useCallback(
        async (files: File[]) => {
            if (files.length === 0) return;

            // Validate file types
            if (accept?.length) {
                const invalid = files.filter(
                    (f) => !accept.some((ext) => f.name.toLowerCase().endsWith(ext)),
                );
                if (invalid.length > 0) {
                    toast.error(`Invalid file type: ${invalid[0].name}`);
                    return;
                }
            }

            // Validate file sizes
            const tooLarge = files.filter((f) => f.size > maxSize);
            if (tooLarge.length > 0) {
                toast.error(`File too large: ${tooLarge[0].name} (max ${Math.round(maxSize / 1024 / 1024)}MB)`);
                return;
            }

            setIsUploading(true);
            const total = files.length;

            try {
                for (let i = 0; i < files.length; i++) {
                    const file = files[i];
                    setProgress({ percent: 0, fileName: file.name, total, current: i + 1 });

                    const formData = new FormData();
                    formData.append("files", file);

                    const token = await getToken?.();
                    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

                    // Use XMLHttpRequest for progress tracking
                    await new Promise<void>((resolve, reject) => {
                        const xhr = new XMLHttpRequest();
                        xhr.open("POST", `${API_BASE}/api/v1${uploadPath}`);
                        if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

                        xhr.upload.onprogress = (e) => {
                            if (e.lengthComputable) {
                                const percent = Math.round((e.loaded / e.total) * 100);
                                setProgress((prev) => prev ? { ...prev, percent } : null);
                            }
                        };

                        xhr.onload = () => {
                            if (xhr.status >= 200 && xhr.status < 300) {
                                resolve();
                            } else {
                                reject(new Error(`Upload failed: ${xhr.statusText}`));
                            }
                        };
                        xhr.onerror = () => reject(new Error("Upload failed"));
                        xhr.send(formData);
                    });
                }

                toast.success(`${total} file${total > 1 ? "s" : ""} uploaded`);
                invalidateKeys.forEach((key) => queryClient.invalidateQueries({ queryKey: key }));
                onSuccess?.();
            } catch (err) {
                toast.error(err instanceof Error ? err.message : "Upload failed");
            } finally {
                setIsUploading(false);
                setProgress(null);
            }
        },
        [uploadPath, getToken, queryClient, invalidateKeys, accept, maxSize, onSuccess],
    );

    // ---- Drag and drop handlers ----
    const onDragOver = useCallback((e: DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(true);
    }, []);

    const onDragLeave = useCallback((e: DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);
    }, []);

    const onDrop = useCallback(
        async (e: DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragOver(false);
            // Support folder drops via webkitGetAsEntry
            const files = await extractFilesFromDrop(e.dataTransfer);
            uploadFiles(files);
        },
        [uploadFiles],
    );

    const openFilePicker = useCallback(() => {
        fileInputRef.current?.click();
    }, []);

    const onFileInputChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            const files = e.target.files ? Array.from(e.target.files) : [];
            uploadFiles(files);
            // Reset input so same file can be re-uploaded
            if (fileInputRef.current) fileInputRef.current.value = "";
        },
        [uploadFiles],
    );

    return {
        isUploading,
        progress,
        isDragOver,
        fileInputRef,
        uploadFiles,
        openFilePicker,
        onFileInputChange,
        dragHandlers: { onDragOver, onDragLeave, onDrop },
    };
}
