// ---- Upload Store -------------------------------------------------------
// Global upload queue managed by Zustand.
// Uploads survive page navigation — processed sequentially via XHR.
"use client";

import { create } from "zustand";

// ---- Blocked extensions (mirrors api/file_scanner.py) -------------------
const BLOCKED_EXTENSIONS = new Set([
    ".exe", ".dll", ".bat", ".cmd", ".com", ".msi", ".scr",
    ".ps1", ".vbs", ".wsf", ".wsh",
    ".php", ".asp", ".aspx", ".jsp",
]);

function isBlockedFile(name: string): boolean {
    const lower = name.toLowerCase();
    for (const ext of BLOCKED_EXTENSIONS) {
        if (lower.endsWith(ext)) return true;
    }
    return false;
}

function isHiddenFile(name: string): boolean {
    return name.startsWith(".");
}

// ---- Types --------------------------------------------------------------

export type UploadStatus = "queued" | "uploading" | "done" | "error";

export interface UploadItem {
    id: string;
    caseId: string;
    file: File;
    fileName: string;
    fileSize: number;
    progress: number;       // 0-100
    status: UploadStatus;
    error?: string;
}

interface UploadState {
    items: UploadItem[];
    isProcessing: boolean;
    expanded: boolean;

    // Actions
    enqueueFiles: (
        caseId: string,
        files: File[],
        getToken: () => Promise<string | null>,
    ) => { queued: number; filtered: number };
    removeItem: (id: string) => void;
    clearCompleted: () => void;
    setExpanded: (open: boolean) => void;
}

// ---- Helpers ------------------------------------------------------------

let _nextId = 0;
function genId(): string {
    return `upload_${Date.now()}_${_nextId++}`;
}

const MAX_FILE_SIZE = 20 * 1024 * 1024 * 1024; // 20 GB

// API base
const API_BASE =
    typeof window !== "undefined"
        ? process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
        : "";

// ---- Store --------------------------------------------------------------

export const useUploadStore = create<UploadState>()((set, get) => {
    // ---- Internal: process queue one file at a time ---------------------
    async function processQueue(getToken: () => Promise<string | null>) {
        const state = get();
        if (state.isProcessing) return;

        const next = state.items.find((i) => i.status === "queued");
        if (!next) return;

        set({ isProcessing: true });

        // Mark as uploading
        set((s) => ({
            items: s.items.map((i) =>
                i.id === next.id ? { ...i, status: "uploading" as const, progress: 0 } : i,
            ),
        }));

        try {
            const token = await getToken();

            await new Promise<void>((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.open("POST", `${API_BASE}/api/v1/cases/${next.caseId}/files`);
                if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

                xhr.upload.onprogress = (e) => {
                    if (e.lengthComputable) {
                        const pct = Math.round((e.loaded / e.total) * 100);
                        set((s) => ({
                            items: s.items.map((i) =>
                                i.id === next.id ? { ...i, progress: pct } : i,
                            ),
                        }));
                    }
                };

                xhr.onload = () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        resolve();
                    } else {
                        let detail = `Upload failed (${xhr.status})`;
                        try {
                            const body = JSON.parse(xhr.responseText);
                            if (body.detail) detail = body.detail;
                        } catch { /* ignore */ }
                        reject(new Error(detail));
                    }
                };

                xhr.onerror = () => reject(new Error("Network error during upload"));
                xhr.ontimeout = () => reject(new Error("Upload timed out"));

                const formData = new FormData();
                formData.append("files", next.file);
                xhr.send(formData);
            });

            // Success
            set((s) => ({
                items: s.items.map((i) =>
                    i.id === next.id
                        ? { ...i, status: "done" as const, progress: 100 }
                        : i,
                ),
            }));

            // Invalidate React Query cache for this case's files
            // We dispatch a custom event that the upload-indicator listens for
            if (typeof window !== "undefined") {
                window.dispatchEvent(
                    new CustomEvent("upload-complete", {
                        detail: { caseId: next.caseId },
                    }),
                );
            }

            // Auto-remove completed item after 5 seconds
            setTimeout(() => {
                set((s) => ({
                    items: s.items.filter((i) => i.id !== next.id),
                }));
            }, 5000);
        } catch (err) {
            set((s) => ({
                items: s.items.map((i) =>
                    i.id === next.id
                        ? {
                              ...i,
                              status: "error" as const,
                              error: err instanceof Error ? err.message : "Upload failed",
                          }
                        : i,
                ),
            }));
        }

        set({ isProcessing: false });

        // Process next item in queue
        processQueue(getToken);
    }

    // ---- Saved getToken ref (set on first enqueue) ----------------------
    let _getToken: (() => Promise<string | null>) | null = null;

    return {
        items: [],
        isProcessing: false,
        expanded: false,

        enqueueFiles(caseId, files, getToken) {
            _getToken = getToken;

            let filtered = 0;
            const validFiles: File[] = [];

            for (const f of files) {
                if (isHiddenFile(f.name)) {
                    filtered++;
                    continue;
                }
                if (isBlockedFile(f.name)) {
                    filtered++;
                    continue;
                }
                if (f.size > MAX_FILE_SIZE) {
                    filtered++;
                    continue;
                }
                if (f.size === 0) {
                    filtered++;
                    continue;
                }
                validFiles.push(f);
            }

            const newItems: UploadItem[] = validFiles.map((file) => ({
                id: genId(),
                caseId,
                file,
                fileName: file.name,
                fileSize: file.size,
                progress: 0,
                status: "queued" as const,
            }));

            set((s) => ({ items: [...s.items, ...newItems] }));

            // Start processing
            if (newItems.length > 0) {
                processQueue(getToken);
            }

            return { queued: newItems.length, filtered };
        },

        removeItem(id) {
            set((s) => ({ items: s.items.filter((i) => i.id !== id) }));
        },

        clearCompleted() {
            set((s) => ({
                items: s.items.filter(
                    (i) => i.status !== "done" && i.status !== "error",
                ),
            }));
        },

        setExpanded(open) {
            set({ expanded: open });
        },
    };
});

// ---- Folder traversal helper --------------------------------------------
// Recursively extract all File objects from a dropped folder.

export async function traverseFileTree(
    entry: FileSystemEntry,
): Promise<File[]> {
    if (entry.isFile) {
        const fileEntry = entry as FileSystemFileEntry;
        const file = await new Promise<File>((resolve, reject) =>
            fileEntry.file(resolve, reject),
        );
        return [file];
    }

    if (entry.isDirectory) {
        const dirEntry = entry as FileSystemDirectoryEntry;
        const reader = dirEntry.createReader();
        const allFiles: File[] = [];

        // readEntries returns max ~100 entries per call — loop until empty
        let batch: FileSystemEntry[];
        do {
            batch = await new Promise<FileSystemEntry[]>((resolve, reject) =>
                reader.readEntries(resolve, reject),
            );
            for (const child of batch) {
                const childFiles = await traverseFileTree(child);
                allFiles.push(...childFiles);
            }
        } while (batch.length > 0);

        return allFiles;
    }

    return [];
}

// ---- Extract files from DataTransfer (supports folders) -----------------

export async function extractFilesFromDrop(
    dataTransfer: DataTransfer,
): Promise<File[]> {
    const items = dataTransfer.items;
    const allFiles: File[] = [];

    // Try webkitGetAsEntry for folder support
    const entries: FileSystemEntry[] = [];
    if (items) {
        for (let i = 0; i < items.length; i++) {
            const entry = items[i].webkitGetAsEntry?.();
            if (entry) {
                entries.push(entry);
            }
        }
    }

    if (entries.length > 0) {
        // We have entry access — traverse folders
        for (const entry of entries) {
            const files = await traverseFileTree(entry);
            allFiles.push(...files);
        }
    } else {
        // Fallback: just use dataTransfer.files
        for (let i = 0; i < dataTransfer.files.length; i++) {
            allFiles.push(dataTransfer.files[i]);
        }
    }

    return allFiles;
}
