// ---- File Upload Component -----------------------------------------------
// Drag-and-drop file upload with progress tracking.
"use client";

import { useState, useCallback, useRef } from "react";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { isDevAuthMode, getDevToken } from "@/lib/dev-auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FileUploadProps {
    caseId: string;
    onUploadComplete?: () => void;
    accept?: string;
    maxFiles?: number;
    maxSizeMB?: number;
}

interface UploadingFile {
    file: File;
    progress: number;
    status: "pending" | "uploading" | "done" | "error";
    error?: string;
}

export function FileUpload({
    caseId,
    onUploadComplete,
    accept = "*",
    maxFiles = 10,
    maxSizeMB = 50,
}: FileUploadProps) {
    const { getToken } = useAuth();
    const [dragOver, setDragOver] = useState(false);
    const [files, setFiles] = useState<UploadingFile[]>([]);
    const [isUploading, setIsUploading] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    const addFiles = useCallback(
        (newFiles: FileList | File[]) => {
            const arr = Array.from(newFiles);
            const valid = arr.filter((f) => {
                if (f.size > maxSizeMB * 1024 * 1024) {
                    toast.error(`${f.name} exceeds ${maxSizeMB}MB limit`);
                    return false;
                }
                return true;
            });

            if (files.length + valid.length > maxFiles) {
                toast.error(`Maximum ${maxFiles} files allowed`);
                return;
            }

            setFiles((prev) => [
                ...prev,
                ...valid.map((file) => ({
                    file,
                    progress: 0,
                    status: "pending" as const,
                })),
            ]);
        },
        [files.length, maxFiles, maxSizeMB],
    );

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            setDragOver(false);
            if (e.dataTransfer.files.length) {
                addFiles(e.dataTransfer.files);
            }
        },
        [addFiles],
    );

    const uploadAll = async () => {
        setIsUploading(true);
        let token = await getToken();
        if (!token && isDevAuthMode()) {
            token = await getDevToken();
        }

        const formData = new FormData();
        files.forEach((f) => {
            if (f.status === "pending") {
                formData.append("files", f.file);
            }
        });

        // Mark all as uploading
        setFiles((prev) =>
            prev.map((f) =>
                f.status === "pending" ? { ...f, status: "uploading" as const, progress: 50 } : f,
            ),
        );

        try {
            const response = await fetch(
                `${API_BASE}/api/v1/cases/${caseId}/files`,
                {
                    method: "POST",
                    headers: token ? { Authorization: `Bearer ${token}` } : {},
                    body: formData,
                },
            );

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || `Upload failed (${response.status})`);
            }

            setFiles((prev) =>
                prev.map((f) => ({ ...f, status: "done" as const, progress: 100 })),
            );
            toast.success(`${files.length} file(s) uploaded`);
            onUploadComplete?.();

            // Clear after 2s
            setTimeout(() => setFiles([]), 2000);
        } catch (error) {
            setFiles((prev) =>
                prev.map((f) =>
                    f.status === "uploading"
                        ? {
                            ...f,
                            status: "error" as const,
                            error: error instanceof Error ? error.message : "Upload failed",
                        }
                        : f,
                ),
            );
            toast.error("Upload failed", {
                description: error instanceof Error ? error.message : "Unknown error",
            });
        } finally {
            setIsUploading(false);
        }
    };

    const removeFile = (index: number) => {
        setFiles((prev) => prev.filter((_, i) => i !== index));
    };

    const clearAll = () => setFiles([]);

    return (
        <div className="space-y-3">
            {/* Drop Zone */}
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
                    onChange={(e) => e.target.files && addFiles(e.target.files)}
                    className="hidden"
                />
                <div className="text-3xl mb-2">📁</div>
                <p className="text-sm font-medium">
                    {dragOver ? "Drop files here" : "Drag & drop files, or click to browse"}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                    Up to {maxFiles} files, {maxSizeMB}MB max each
                </p>
            </div>

            {/* File List */}
            {files.length > 0 && (
                <div className="space-y-2">
                    {files.map((f, i) => (
                        <Card key={i}>
                            <CardContent className="flex items-center justify-between py-2.5">
                                <div className="flex items-center gap-2 flex-1 min-w-0">
                                    <span className="text-lg shrink-0">
                                        {f.status === "done" ? "✅" : f.status === "error" ? "❌" : "📄"}
                                    </span>
                                    <div className="min-w-0 flex-1">
                                        <p className="text-sm font-medium truncate">{f.file.name}</p>
                                        <p className="text-xs text-muted-foreground">
                                            {(f.file.size / 1024).toFixed(0)} KB
                                            {f.error && (
                                                <span className="text-destructive"> · {f.error}</span>
                                            )}
                                        </p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Badge
                                        variant="outline"
                                        className={
                                            f.status === "done"
                                                ? "text-emerald-400 border-emerald-500/30"
                                                : f.status === "error"
                                                    ? "text-red-400 border-red-500/30"
                                                    : f.status === "uploading"
                                                        ? "text-blue-400 border-blue-500/30 animate-pulse"
                                                        : "text-zinc-400"
                                        }
                                    >
                                        {f.status}
                                    </Badge>
                                    {f.status === "pending" && (
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-6 w-6"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                removeFile(i);
                                            }}
                                        >
                                            ✕
                                        </Button>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    ))}

                    <div className="flex justify-end gap-2">
                        <Button variant="outline" size="sm" onClick={clearAll} disabled={isUploading}>
                            Clear
                        </Button>
                        <Button
                            size="sm"
                            onClick={uploadAll}
                            disabled={isUploading || files.every((f) => f.status !== "pending")}
                        >
                            {isUploading ? "Uploading..." : `Upload ${files.filter((f) => f.status === "pending").length} file(s)`}
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
