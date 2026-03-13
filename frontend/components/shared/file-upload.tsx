// ---- File Upload Component -----------------------------------------------
// Drag-and-drop file/folder upload with progress tracking.
// Shows compatible file types and filters incompatible files.
"use client";

import { useState, useCallback, useRef } from "react";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const MAX_SIZE_BYTES = 20 * 1024 * 1024 * 1024; // 20 GB

// ---- Compatible file types (must match core/ingest.py) -------------------

const COMPATIBLE_TYPES: Record<string, string[]> = {
    "Documents": [".pdf", ".docx", ".doc", ".txt", ".rtf", ".md", ".pptx"],
    "Spreadsheets": [".xlsx", ".xls", ".csv", ".tsv"],
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".heic", ".heif", ".webp"],
    "Audio": [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma"],
    "Video": [".mp4", ".mpeg", ".mpga", ".webm", ".avi", ".mov", ".mkv"],
    "Data/Code": [".json", ".xml", ".html", ".htm", ".yaml", ".yml", ".log", ".ini", ".cfg", ".toml"],
};

const ALL_EXTENSIONS = new Set(
    Object.values(COMPATIBLE_TYPES).flat(),
);

// For the <input accept=""> attribute
const ACCEPT_STRING = Array.from(ALL_EXTENSIONS).join(",");

function isCompatible(filename: string): boolean {
    const ext = filename.lastIndexOf(".") >= 0
        ? filename.slice(filename.lastIndexOf(".")).toLowerCase()
        : "";
    return ALL_EXTENSIONS.has(ext);
}

// --------------------------------------------------------------------------

interface FileUploadProps {
    caseId: string;
    onUploadComplete?: () => void;
    maxSizeMB?: number;
}

interface UploadingFile {
    file: File;
    progress: number;
    status: "pending" | "uploading" | "done" | "error";
    error?: string;
}

function formatSizeLimit(mb: number): string {
    if (mb >= 1024) return `${(mb / 1024).toFixed(0)}GB`;
    return `${mb}MB`;
}

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

// Recursively read all files from a dropped directory entry
async function readEntryRecursive(entry: FileSystemEntry): Promise<File[]> {
    if (entry.isFile) {
        return new Promise<File[]>((resolve) => {
            (entry as FileSystemFileEntry).file(
                (f) => resolve([f]),
                () => resolve([]),
            );
        });
    }
    if (entry.isDirectory) {
        const dirReader = (entry as FileSystemDirectoryEntry).createReader();
        const files: File[] = [];
        const readBatch = (): Promise<FileSystemEntry[]> =>
            new Promise((resolve) => dirReader.readEntries(resolve, () => resolve([])));
        let batch = await readBatch();
        while (batch.length > 0) {
            for (const child of batch) {
                files.push(...(await readEntryRecursive(child)));
            }
            batch = await readBatch();
        }
        return files;
    }
    return [];
}

// Extract files from a DataTransfer, traversing directories
async function extractFilesFromDataTransfer(dt: DataTransfer): Promise<File[]> {
    const items = dt.items;
    if (items && items.length > 0 && typeof items[0].webkitGetAsEntry === "function") {
        const allFiles: File[] = [];
        const entries: FileSystemEntry[] = [];
        for (let i = 0; i < items.length; i++) {
            const entry = items[i].webkitGetAsEntry();
            if (entry) entries.push(entry);
        }
        for (const entry of entries) {
            allFiles.push(...(await readEntryRecursive(entry)));
        }
        return allFiles;
    }
    return Array.from(dt.files);
}

export function FileUpload({
    caseId,
    onUploadComplete,
    maxSizeMB = MAX_SIZE_BYTES / (1024 * 1024),
}: FileUploadProps) {
    const { getToken } = useAuth();
    const [dragOver, setDragOver] = useState(false);
    const [files, setFiles] = useState<UploadingFile[]>([]);
    const [isUploading, setIsUploading] = useState(false);
    const [showTypes, setShowTypes] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const folderInputRef = useRef<HTMLInputElement>(null);

    const maxSizeBytes = maxSizeMB * 1024 * 1024;

    const addFiles = useCallback(
        (newFiles: File[]) => {
            let skippedSize = 0;
            let skippedType = 0;
            let skippedHidden = 0;

            const valid = newFiles.filter((f) => {
                if (f.name.startsWith(".")) { skippedHidden++; return false; }
                if (!isCompatible(f.name)) { skippedType++; return false; }
                if (f.size > maxSizeBytes) {
                    skippedSize++;
                    toast.error(`${f.name} exceeds ${formatSizeLimit(maxSizeMB)} limit`);
                    return false;
                }
                return true;
            });

            if (valid.length > 0) {
                setFiles((prev) => [
                    ...prev,
                    ...valid.map((file) => ({
                        file,
                        progress: 0,
                        status: "pending" as const,
                    })),
                ]);
            }

            const totalSkipped = skippedSize + skippedType + skippedHidden;
            if (totalSkipped > 0) {
                const parts: string[] = [];
                if (skippedType > 0) parts.push(`${skippedType} unsupported type${skippedType > 1 ? "s" : ""}`);
                if (skippedSize > 0) parts.push(`${skippedSize} too large`);
                if (skippedHidden > 0) parts.push(`${skippedHidden} hidden`);
                toast.info(`${totalSkipped} file(s) skipped: ${parts.join(", ")}`);
            }
        },
        [maxSizeBytes, maxSizeMB],
    );

    const handleDrop = useCallback(
        async (e: React.DragEvent) => {
            e.preventDefault();
            setDragOver(false);
            const extracted = await extractFilesFromDataTransfer(e.dataTransfer);
            if (extracted.length > 0) {
                addFiles(extracted);
            }
        },
        [addFiles],
    );

    const uploadAll = async () => {
        const pendingFiles = files.filter((f) => f.status === "pending");
        if (pendingFiles.length === 0) return;

        setIsUploading(true);
        const token = await getToken();

        const formData = new FormData();
        pendingFiles.forEach((f) => formData.append("files", f.file));

        setFiles((prev) =>
            prev.map((f) =>
                f.status === "pending" ? { ...f, status: "uploading" as const, progress: 50 } : f,
            ),
        );

        try {
            // Read CSRF token from cookie
            const csrfMatch = document.cookie.match(/(?:^|;\s*)mc-csrf=([^;]*)/);
            const csrfToken = csrfMatch ? decodeURIComponent(csrfMatch[1]) : "";
            const uploadHeaders: Record<string, string> = {};
            if (token) uploadHeaders["Authorization"] = `Bearer ${token}`;
            if (csrfToken) uploadHeaders["X-CSRF-Token"] = csrfToken;

            const response = await fetch(
                `${API_BASE}/api/v1/cases/${caseId}/files`,
                {
                    method: "POST",
                    headers: uploadHeaders,
                    credentials: "include",
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
            toast.success(`${pendingFiles.length} file(s) uploaded`);
            onUploadComplete?.();

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

    const pendingCount = files.filter((f) => f.status === "pending").length;

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
                onClick={() => fileInputRef.current?.click()}
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
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept={ACCEPT_STRING}
                    onChange={(e) => {
                        if (e.target.files) addFiles(Array.from(e.target.files));
                        e.target.value = "";
                    }}
                    className="hidden"
                />
                <input
                    ref={folderInputRef}
                    type="file"
                    // @ts-expect-error webkitdirectory is not in the HTMLInputElement type
                    webkitdirectory=""
                    multiple
                    onChange={(e) => {
                        if (e.target.files) addFiles(Array.from(e.target.files));
                        e.target.value = "";
                    }}
                    className="hidden"
                />
                <div className="text-3xl mb-2">📄</div>
                <p className="text-sm font-medium">
                    {dragOver ? "Drop files here" : "Click to select files, or drag & drop"}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                    {formatSizeLimit(maxSizeMB)} max per file &middot; No file count limit
                </p>
                <div className="flex items-center justify-center gap-3 mt-2">
                    <Button
                        variant="link"
                        size="sm"
                        className="text-xs h-auto p-0"
                        onClick={(e) => {
                            e.stopPropagation();
                            folderInputRef.current?.click();
                        }}
                    >
                        Select a folder
                    </Button>
                    <span className="text-muted-foreground text-xs">|</span>
                    <Button
                        variant="link"
                        size="sm"
                        className="text-xs h-auto p-0"
                        onClick={(e) => {
                            e.stopPropagation();
                            setShowTypes((v) => !v);
                        }}
                    >
                        {showTypes ? "Hide" : "View"} compatible file types
                    </Button>
                </div>
            </div>

            {/* Compatible File Types Panel */}
            {showTypes && (
                <Card>
                    <CardContent className="py-3">
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                            {Object.entries(COMPATIBLE_TYPES).map(([category, exts]) => (
                                <div key={category}>
                                    <p className="text-xs font-medium text-muted-foreground mb-1">
                                        {category}
                                    </p>
                                    <div className="flex flex-wrap gap-1">
                                        {exts.map((ext) => (
                                            <Badge key={ext} variant="outline" className="text-[10px] font-mono px-1.5">
                                                {ext}
                                            </Badge>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* File List */}
            {files.length > 0 && (
                <div className="space-y-2">
                    {files.length > 20 ? (
                        <Card>
                            <CardContent className="py-3">
                                <p className="text-sm font-medium">
                                    {files.length} files queued
                                </p>
                                <p className="text-xs text-muted-foreground">
                                    {files.filter((f) => f.status === "done").length} done
                                    {files.filter((f) => f.status === "error").length > 0 &&
                                        ` · ${files.filter((f) => f.status === "error").length} failed`}
                                    {pendingCount > 0 && ` · ${pendingCount} pending`}
                                </p>
                            </CardContent>
                        </Card>
                    ) : (
                        files.map((f, i) => (
                            <Card key={i}>
                                <CardContent className="flex items-center justify-between py-2.5">
                                    <div className="flex items-center gap-2 flex-1 min-w-0">
                                        <span className="text-lg shrink-0">
                                            {f.status === "done" ? "✅" : f.status === "error" ? "❌" : "📄"}
                                        </span>
                                        <div className="min-w-0 flex-1">
                                            <p className="text-sm font-medium truncate">{f.file.name}</p>
                                            <p className="text-xs text-muted-foreground">
                                                {formatFileSize(f.file.size)}
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
                        ))
                    )}

                    <div className="flex justify-end gap-2">
                        <Button variant="outline" size="sm" onClick={clearAll} disabled={isUploading}>
                            Clear
                        </Button>
                        <Button
                            size="sm"
                            onClick={uploadAll}
                            disabled={isUploading || pendingCount === 0}
                        >
                            {isUploading ? "Uploading..." : `Upload ${pendingCount} file(s)`}
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
