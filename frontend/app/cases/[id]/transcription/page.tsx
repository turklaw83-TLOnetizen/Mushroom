// ---- Transcription Page (case subtab) -----------------------------------
// Start and monitor transcription jobs for case files.
// Includes transcript viewer, file selection, and timestamp bookmarks.
"use client";

import { useState, useMemo, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import type { FileItem } from "@/types/api";

// ---- Types ----------------------------------------------------------------

interface TranscriptionJob {
    job_id: string;
    file_key: string;
    language: string;
    status: string;
    created_at: string;
    completed_at?: string;
    download_url?: string;
    transcript_text?: string;
    progress?: number;
    error_message?: string;
}

interface JobsResponse {
    items: TranscriptionJob[];
}

interface StartResponse {
    status: string;
    job_id: string;
}

interface JobDetailResponse {
    job_id: string;
    file_key: string;
    language: string;
    status: string;
    created_at: string;
    completed_at?: string;
    transcript_text?: string;
    download_url?: string;
}

interface Bookmark {
    id: string;
    file_key: string;
    timestamp_seconds: number;
    label: string;
    note: string;
    created_by: string;
    created_at: string;
}

// ---- Helpers --------------------------------------------------------------

const MEDIA_EXTENSIONS = new Set([
    "mp4", "mp3", "wav", "m4a", "ogg", "webm", "flac", "aac",
    "wma", "avi", "mov", "mkv", "m4v", "3gp",
]);

function isMediaFile(filename: string): boolean {
    const ext = filename.split(".").pop()?.toLowerCase() ?? "";
    return MEDIA_EXTENSIONS.has(ext);
}

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatSeconds(s: number): string {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = Math.floor(s % 60);
    if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
    return `${m}:${sec.toString().padStart(2, "0")}`;
}

function formatTimestamp(ts: string): string {
    try {
        const d = new Date(ts);
        return d.toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
        });
    } catch {
        return ts;
    }
}

function computeDuration(created: string, completed?: string): string {
    if (!completed) return "";
    try {
        const start = new Date(created).getTime();
        const end = new Date(completed).getTime();
        const diffSec = Math.round((end - start) / 1000);
        if (diffSec < 60) return `${diffSec}s`;
        if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ${diffSec % 60}s`;
        const h = Math.floor(diffSec / 3600);
        const m = Math.floor((diffSec % 3600) / 60);
        return `${h}h ${m}m`;
    } catch {
        return "";
    }
}

const statusColor: Record<string, string> = {
    pending: "text-amber-400 border-amber-400/30 bg-amber-400/10",
    running: "text-blue-400 border-blue-400/30 bg-blue-400/10",
    completed: "text-green-400 border-green-400/30 bg-green-400/10",
    failed: "text-red-400 border-red-400/30 bg-red-400/10",
};

const languageOptions = [
    { value: "en", label: "English" },
    { value: "es", label: "Spanish" },
    { value: "fr", label: "French" },
    { value: "de", label: "German" },
];

// ---- Transcript Viewer Component ------------------------------------------

function TranscriptViewer({
    transcript,
    jobId,
    fileKey,
    onAddBookmark,
}: {
    transcript: string;
    jobId: string;
    fileKey: string;
    onAddBookmark?: (position: number) => void;
}) {
    const [search, setSearch] = useState("");
    const [copied, setCopied] = useState(false);
    const contentRef = useRef<HTMLDivElement>(null);

    const paragraphs = useMemo(() => {
        return transcript
            .split(/\n\n+/)
            .map((p) => p.trim())
            .filter(Boolean);
    }, [transcript]);

    const filteredParagraphs = useMemo(() => {
        if (!search.trim()) return paragraphs;
        const lower = search.toLowerCase();
        return paragraphs.filter((p) => p.toLowerCase().includes(lower));
    }, [paragraphs, search]);

    const handleCopy = useCallback(async () => {
        try {
            await navigator.clipboard.writeText(transcript);
            setCopied(true);
            toast.success("Transcript copied to clipboard");
            setTimeout(() => setCopied(false), 2000);
        } catch {
            toast.error("Failed to copy");
        }
    }, [transcript]);

    // Highlight matching text
    function highlightText(text: string): React.ReactNode {
        if (!search.trim()) return text;
        const lower = search.toLowerCase();
        const idx = text.toLowerCase().indexOf(lower);
        if (idx === -1) return text;
        return (
            <>
                {text.slice(0, idx)}
                <mark className="bg-yellow-300/40 dark:bg-yellow-500/30 text-inherit rounded px-0.5">
                    {text.slice(idx, idx + search.length)}
                </mark>
                {text.slice(idx + search.length)}
            </>
        );
    }

    return (
        <div className="space-y-3">
            {/* Toolbar */}
            <div className="flex items-center gap-2">
                <div className="relative flex-1">
                    <Input
                        placeholder="Search transcript..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="pr-8"
                    />
                    {search && (
                        <button
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground text-xs"
                            onClick={() => setSearch("")}
                            aria-label="Clear search"
                        >
                            x
                        </button>
                    )}
                </div>
                <Button variant="outline" size="sm" onClick={handleCopy}>
                    {copied ? "Copied!" : "Copy All"}
                </Button>
                {onAddBookmark && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onAddBookmark(0)}
                    >
                        + Bookmark
                    </Button>
                )}
            </div>

            {/* Match count */}
            {search.trim() && (
                <p className="text-xs text-muted-foreground">
                    {filteredParagraphs.length} of {paragraphs.length} paragraphs match
                </p>
            )}

            {/* Transcript content */}
            <div
                ref={contentRef}
                className="max-h-[500px] overflow-y-auto border rounded-lg p-4 bg-muted/20 space-y-3"
            >
                {filteredParagraphs.length === 0 ? (
                    <p className="text-sm text-muted-foreground italic">
                        {search.trim()
                            ? "No matching paragraphs found."
                            : "Transcript is empty."}
                    </p>
                ) : (
                    filteredParagraphs.map((para, i) => (
                        <p
                            key={`${jobId}-p-${i}`}
                            className="text-sm leading-relaxed text-foreground/90"
                        >
                            {highlightText(para)}
                        </p>
                    ))
                )}
            </div>
        </div>
    );
}

// ---- Job Card Component ---------------------------------------------------

function JobCard({
    job,
    isExpanded,
    onToggle,
    caseId,
    getToken,
    onAddBookmark,
}: {
    job: TranscriptionJob;
    isExpanded: boolean;
    onToggle: () => void;
    caseId: string;
    getToken: () => Promise<string | null>;
    onAddBookmark: (fileKey: string) => void;
}) {
    const duration = computeDuration(job.created_at, job.completed_at);
    const isActive = job.status === "running" || job.status === "pending";
    const isCompleted = job.status === "completed";

    // Fetch transcript when expanded
    const transcriptQuery = useQuery({
        queryKey: ["transcription-job-detail", caseId, job.job_id],
        queryFn: () =>
            api.get<JobDetailResponse>(
                `/cases/${caseId}/transcription/jobs/${job.job_id}`,
                { getToken },
            ),
        enabled: isExpanded && isCompleted,
        staleTime: 5 * 60 * 1000,
    });

    const transcriptText =
        transcriptQuery.data?.transcript_text || job.transcript_text || "";

    return (
        <Card
            className={`transition-colors ${
                isExpanded
                    ? "ring-1 ring-ring/30"
                    : "hover:bg-accent/20"
            }`}
        >
            <CardContent className="py-3">
                {/* Header row */}
                <div
                    className="flex items-center justify-between cursor-pointer"
                    onClick={onToggle}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onToggle();
                        }
                    }}
                >
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs text-muted-foreground select-none">
                                {isExpanded ? "\u25BC" : "\u25B6"}
                            </span>
                            <p className="text-sm font-medium truncate">
                                {job.file_key.split("/").pop() || job.file_key}
                            </p>
                            <Badge
                                variant="outline"
                                className={`text-[10px] shrink-0 ${statusColor[job.status] || ""}`}
                            >
                                {job.status}
                            </Badge>
                            {duration && isCompleted && (
                                <span className="text-[10px] text-muted-foreground">
                                    {duration}
                                </span>
                            )}
                        </div>
                        <div className="flex items-center gap-3 text-xs text-muted-foreground ml-5">
                            <span>
                                {languageOptions.find((l) => l.value === job.language)?.label || job.language}
                            </span>
                            <span>{formatTimestamp(job.created_at)}</span>
                            {job.completed_at && (
                                <span>Done: {formatTimestamp(job.completed_at)}</span>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 ml-4">
                        {isActive && (
                            <div className="flex items-center gap-2">
                                {job.progress !== undefined && job.progress > 0 ? (
                                    <div className="flex items-center gap-2">
                                        <div className="w-20 h-1.5 bg-muted rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-blue-500 rounded-full transition-all duration-500"
                                                style={{ width: `${Math.min(job.progress, 100)}%` }}
                                            />
                                        </div>
                                        <span className="text-[10px] text-blue-400 tabular-nums">
                                            {Math.round(job.progress)}%
                                        </span>
                                    </div>
                                ) : (
                                    <span className="text-xs text-blue-400 animate-pulse">
                                        Processing...
                                    </span>
                                )}
                            </div>
                        )}
                        {isCompleted && (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onToggle();
                                }}
                            >
                                {isExpanded ? "Hide" : "View Transcript"}
                            </Button>
                        )}
                        {job.status === "failed" && job.error_message && (
                            <span
                                className="text-[10px] text-red-400 max-w-[200px] truncate"
                                title={job.error_message}
                            >
                                {job.error_message}
                            </span>
                        )}
                    </div>
                </div>

                {/* Progress bar for running jobs */}
                {isActive && job.progress !== undefined && job.progress > 0 && (
                    <div className="mt-2 ml-5">
                        <div className="w-full h-1 bg-muted rounded-full overflow-hidden">
                            <div
                                className="h-full bg-blue-500 rounded-full transition-all duration-700 animate-pulse"
                                style={{ width: `${Math.min(job.progress, 100)}%` }}
                            />
                        </div>
                    </div>
                )}

                {/* Expanded transcript viewer */}
                {isExpanded && isCompleted && (
                    <div className="mt-4 ml-5 border-t pt-3">
                        {transcriptQuery.isLoading ? (
                            <div className="space-y-2">
                                <Skeleton className="h-4 w-full" />
                                <Skeleton className="h-4 w-4/5" />
                                <Skeleton className="h-4 w-3/5" />
                                <Skeleton className="h-4 w-full" />
                            </div>
                        ) : transcriptText ? (
                            <TranscriptViewer
                                transcript={transcriptText}
                                jobId={job.job_id}
                                fileKey={job.file_key}
                                onAddBookmark={() => onAddBookmark(job.file_key)}
                            />
                        ) : (
                            <div className="text-sm text-muted-foreground py-4">
                                <p>No transcript text available.</p>
                                {job.download_url && (
                                    <a
                                        href={job.download_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-blue-400 hover:underline text-xs mt-1 inline-block"
                                    >
                                        Download transcript file
                                    </a>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

// ---- Bookmarks Section Component ------------------------------------------

function BookmarksSection({
    bookmarks,
    isLoading,
    canEdit,
    canDelete,
    onAddBookmark,
    onDeleteBookmark,
    expandedNotes,
    toggleNote,
}: {
    bookmarks: Bookmark[];
    isLoading: boolean;
    canEdit: boolean;
    canDelete: boolean;
    onAddBookmark: () => void;
    onDeleteBookmark: (id: string) => void;
    expandedNotes: Set<string>;
    toggleNote: (id: string) => void;
}) {
    // Group bookmarks by file_key
    const grouped = useMemo(() => {
        const map = new Map<string, Bookmark[]>();
        for (const bm of bookmarks) {
            const key = bm.file_key || "(no file)";
            if (!map.has(key)) map.set(key, []);
            map.get(key)!.push(bm);
        }
        // Sort bookmarks within each group by timestamp
        for (const [, items] of map) {
            items.sort((a, b) => a.timestamp_seconds - b.timestamp_seconds);
        }
        return map;
    }, [bookmarks]);

    if (isLoading) {
        return (
            <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 w-full rounded-lg" />
                ))}
            </div>
        );
    }

    if (bookmarks.length === 0) {
        return (
            <p className="text-sm text-muted-foreground py-4">
                No bookmarks yet. Add one to mark important transcript moments.
            </p>
        );
    }

    return (
        <div className="space-y-4">
            {Array.from(grouped.entries()).map(([fileKey, items]) => (
                <div key={fileKey}>
                    <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">
                        {fileKey.split("/").pop() || fileKey}
                    </p>
                    <div className="space-y-1.5">
                        {items.map((bm) => {
                            const isExpanded = expandedNotes.has(bm.id);
                            return (
                                <div
                                    key={bm.id}
                                    className="group flex flex-col rounded-md border bg-accent/20 hover:bg-accent/40 transition-colors px-3 py-2"
                                >
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs font-mono text-blue-400 shrink-0 min-w-[40px]">
                                            {formatSeconds(bm.timestamp_seconds)}
                                        </span>
                                        <span className="text-sm truncate flex-1">
                                            {bm.label || "(no label)"}
                                        </span>
                                        {bm.note && (
                                            <button
                                                className="text-xs text-muted-foreground hover:text-foreground shrink-0"
                                                onClick={() => toggleNote(bm.id)}
                                                aria-label={isExpanded ? "Collapse note" : "Expand note"}
                                            >
                                                {isExpanded ? "\u25B4 less" : "\u25BE note"}
                                            </button>
                                        )}
                                        <span className="text-[10px] text-muted-foreground shrink-0">
                                            {formatTimestamp(bm.created_at)}
                                        </span>
                                        {canDelete && (
                                            <button
                                                className="text-destructive opacity-0 group-hover:opacity-100 transition-opacity text-xs ml-0.5 shrink-0"
                                                aria-label={`Delete bookmark ${bm.label}`}
                                                onClick={() => onDeleteBookmark(bm.id)}
                                            >
                                                x
                                            </button>
                                        )}
                                    </div>
                                    {isExpanded && bm.note && (
                                        <p className="text-xs text-muted-foreground mt-1.5 ml-[48px] whitespace-pre-wrap">
                                            {bm.note}
                                        </p>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            ))}
        </div>
    );
}

// ---- Main Page Component --------------------------------------------------

export default function TranscriptionPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const { canEdit, canDelete } = useRole();

    // UI state
    const [showStartForm, setShowStartForm] = useState(false);
    const [selectedFile, setSelectedFile] = useState("");
    const [language, setLanguage] = useState("en");
    const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
    const [expandedNotes, setExpandedNotes] = useState<Set<string>>(new Set());

    // Bookmark dialog state
    const [bookmarkDialogOpen, setBookmarkDialogOpen] = useState(false);
    const [bmFileKey, setBmFileKey] = useState("");
    const [bmMinutes, setBmMinutes] = useState("");
    const [bmSeconds, setBmSeconds] = useState("");
    const [bmLabel, setBmLabel] = useState("");
    const [bmNote, setBmNote] = useState("");
    const [bmSubmitting, setBmSubmitting] = useState(false);

    // ---- Data Queries -------------------------------------------------------

    // Case files (for file picker)
    const filesQuery = useQuery({
        queryKey: ["cases", caseId, "files"],
        queryFn: () => api.get<FileItem[]>(`/cases/${caseId}/files`, { getToken }),
        staleTime: 60_000,
    });

    const mediaFiles = useMemo(() => {
        const files = filesQuery.data ?? [];
        return files.filter((f) => isMediaFile(f.filename));
    }, [filesQuery.data]);

    // Transcription jobs
    const jobsQuery = useQuery({
        queryKey: ["transcription-jobs", caseId],
        queryFn: () =>
            api.get<JobsResponse>(`/cases/${caseId}/transcription/jobs`, { getToken }),
    });

    const jobs = jobsQuery.data?.items ?? [];

    const hasRunningJobs = useMemo(
        () => jobs.some((j) => j.status === "running" || j.status === "pending"),
        [jobs],
    );

    // Poll when there are active jobs
    useQuery({
        queryKey: ["transcription-jobs-poll", caseId],
        queryFn: () =>
            api.get<JobsResponse>(`/cases/${caseId}/transcription/jobs`, { getToken }),
        refetchInterval: hasRunningJobs ? 5000 : false,
        enabled: hasRunningJobs,
        select: (pollData) => {
            queryClient.setQueryData(["transcription-jobs", caseId], pollData);
            return pollData;
        },
    });

    // Bookmarks
    const bookmarksQueryKey = ["transcription-bookmarks", caseId];
    const bookmarksQuery = useQuery({
        queryKey: bookmarksQueryKey,
        queryFn: () =>
            api.get<{ items: Bookmark[] }>(
                `/cases/${caseId}/transcription/bookmarks`,
                { getToken },
            ),
    });
    const bookmarks = bookmarksQuery.data?.items ?? [];

    // ---- Mutations ----------------------------------------------------------

    const startTranscription = useMutationWithToast<{ file_key: string; language: string }, StartResponse>({
        mutationFn: (body) =>
            api.post<StartResponse>(`/cases/${caseId}/transcription/start`, body, { getToken }),
        successMessage: "Transcription started",
        invalidateKeys: [["transcription-jobs", caseId]],
        onSuccess: () => {
            setShowStartForm(false);
            setSelectedFile("");
            setLanguage("en");
        },
    });

    // ---- Handlers -----------------------------------------------------------

    const handleStart = () => {
        if (!selectedFile.trim()) {
            toast.error("Select a file to transcribe");
            return;
        }
        startTranscription.mutate({ file_key: selectedFile.trim(), language });
    };

    const toggleJobExpanded = (jobId: string) => {
        setExpandedJobId((prev) => (prev === jobId ? null : jobId));
    };

    const toggleNote = useCallback((bookmarkId: string) => {
        setExpandedNotes((prev) => {
            const next = new Set(prev);
            if (next.has(bookmarkId)) next.delete(bookmarkId);
            else next.add(bookmarkId);
            return next;
        });
    }, []);

    // Open bookmark dialog pre-filled with a file key
    const openBookmarkForFile = useCallback((fileKey: string) => {
        setBmFileKey(fileKey);
        setBookmarkDialogOpen(true);
    }, []);

    function resetBookmarkForm() {
        setBmFileKey("");
        setBmMinutes("");
        setBmSeconds("");
        setBmLabel("");
        setBmNote("");
    }

    async function handleAddBookmark() {
        if (!bmFileKey.trim()) {
            toast.error("File key is required");
            return;
        }
        const mins = parseInt(bmMinutes || "0", 10);
        const secs = parseInt(bmSeconds || "0", 10);
        if (isNaN(mins) || isNaN(secs) || mins < 0 || secs < 0 || secs >= 60) {
            toast.error("Invalid timestamp");
            return;
        }
        const totalSeconds = mins * 60 + secs;
        setBmSubmitting(true);
        try {
            await api.post(
                `/cases/${caseId}/transcription/bookmarks`,
                {
                    file_key: bmFileKey.trim(),
                    timestamp_seconds: totalSeconds,
                    label: bmLabel.trim(),
                    note: bmNote.trim(),
                },
                { getToken },
            );
            toast.success("Bookmark added");
            queryClient.invalidateQueries({ queryKey: bookmarksQueryKey });
            setBookmarkDialogOpen(false);
            resetBookmarkForm();
        } catch {
            toast.error("Failed to add bookmark");
        } finally {
            setBmSubmitting(false);
        }
    }

    async function handleDeleteBookmark(bookmarkId: string) {
        try {
            await api.delete(
                `/cases/${caseId}/transcription/bookmarks/${bookmarkId}`,
                { getToken },
            );
            toast.success("Bookmark deleted");
            queryClient.invalidateQueries({ queryKey: bookmarksQueryKey });
        } catch {
            toast.error("Failed to delete bookmark");
        }
    }

    // ---- Job stats ----------------------------------------------------------

    const jobStats = useMemo(() => {
        let completed = 0;
        let running = 0;
        let pending = 0;
        let failed = 0;
        for (const j of jobs) {
            if (j.status === "completed") completed++;
            else if (j.status === "running") running++;
            else if (j.status === "pending") pending++;
            else if (j.status === "failed") failed++;
        }
        return { completed, running, pending, failed, total: jobs.length };
    }, [jobs]);

    // ---- Render -------------------------------------------------------------

    return (
        <div className="space-y-5">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">Transcription</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Audio and video transcription jobs
                        {jobStats.total > 0 && (
                            <span className="ml-2">
                                &mdash; {jobStats.completed} completed
                                {jobStats.running > 0 && `, ${jobStats.running} running`}
                                {jobStats.pending > 0 && `, ${jobStats.pending} pending`}
                                {jobStats.failed > 0 && `, ${jobStats.failed} failed`}
                            </span>
                        )}
                    </p>
                </div>
                {canEdit && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowStartForm(!showStartForm)}
                    >
                        {showStartForm ? "Cancel" : "Start Transcription"}
                    </Button>
                )}
            </div>

            {/* Start transcription form */}
            {showStartForm && (
                <Card>
                    <CardContent className="py-4 space-y-3">
                        <p className="text-sm font-medium">Start Transcription</p>

                        {/* File selector */}
                        <div className="space-y-1.5">
                            <label className="text-xs font-medium text-muted-foreground">
                                Select File
                            </label>
                            {filesQuery.isLoading ? (
                                <Skeleton className="h-9 w-full" />
                            ) : mediaFiles.length > 0 ? (
                                <Select value={selectedFile} onValueChange={setSelectedFile}>
                                    <SelectTrigger className="w-full">
                                        <SelectValue placeholder="Choose a media file..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {mediaFiles.map((f) => (
                                            <SelectItem key={f.filename} value={f.filename}>
                                                <span className="flex items-center gap-2">
                                                    <span className="truncate">{f.filename}</span>
                                                    <span className="text-[10px] text-muted-foreground shrink-0">
                                                        {formatSize(f.size)}
                                                    </span>
                                                </span>
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            ) : (
                                <div className="space-y-2">
                                    <p className="text-xs text-muted-foreground">
                                        No media files found in this case. Upload media files first, or enter a file key manually.
                                    </p>
                                    <Input
                                        placeholder="Enter file key manually..."
                                        value={selectedFile}
                                        onChange={(e) => setSelectedFile(e.target.value)}
                                    />
                                </div>
                            )}
                        </div>

                        {/* Language selector */}
                        <div className="flex items-center gap-3">
                            <label className="text-xs font-medium text-muted-foreground">
                                Language:
                            </label>
                            <Select value={language} onValueChange={setLanguage}>
                                <SelectTrigger className="w-40">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {languageOptions.map((opt) => (
                                        <SelectItem key={opt.value} value={opt.value}>
                                            {opt.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="flex justify-end">
                            <Button
                                size="sm"
                                onClick={handleStart}
                                disabled={startTranscription.isPending || !selectedFile.trim()}
                            >
                                {startTranscription.isPending ? "Starting..." : "Start"}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Main content tabs */}
            <Tabs defaultValue="jobs" className="w-full">
                <TabsList>
                    <TabsTrigger value="jobs">
                        Jobs{" "}
                        {jobStats.total > 0 && (
                            <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5">
                                {jobStats.total}
                            </Badge>
                        )}
                    </TabsTrigger>
                    <TabsTrigger value="bookmarks">
                        Bookmarks{" "}
                        {bookmarks.length > 0 && (
                            <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5">
                                {bookmarks.length}
                            </Badge>
                        )}
                    </TabsTrigger>
                </TabsList>

                {/* ---- Jobs Tab ---- */}
                <TabsContent value="jobs" className="mt-4">
                    {jobsQuery.isLoading ? (
                        <div className="space-y-3">
                            {Array.from({ length: 4 }).map((_, i) => (
                                <Skeleton key={i} className="h-18 w-full rounded-lg" />
                            ))}
                        </div>
                    ) : jobs.length === 0 ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                <p className="text-base mb-1">No transcription jobs yet</p>
                                <p className="text-sm">
                                    Start one by clicking the button above. Supported formats:
                                    MP3, MP4, WAV, M4A, OGG, WebM, and more.
                                </p>
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="space-y-2">
                            {jobs.map((job) => (
                                <JobCard
                                    key={job.job_id}
                                    job={job}
                                    isExpanded={expandedJobId === job.job_id}
                                    onToggle={() => toggleJobExpanded(job.job_id)}
                                    caseId={caseId}
                                    getToken={getToken}
                                    onAddBookmark={openBookmarkForFile}
                                />
                            ))}
                        </div>
                    )}
                </TabsContent>

                {/* ---- Bookmarks Tab ---- */}
                <TabsContent value="bookmarks" className="mt-4">
                    <div className="flex items-center justify-between mb-3">
                        <p className="text-sm text-muted-foreground">
                            Mark important timestamps in transcripts for quick reference.
                        </p>
                        {canEdit && (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setBookmarkDialogOpen(true)}
                            >
                                + Add Bookmark
                            </Button>
                        )}
                    </div>
                    <BookmarksSection
                        bookmarks={bookmarks}
                        isLoading={bookmarksQuery.isLoading}
                        canEdit={canEdit}
                        canDelete={canDelete}
                        onAddBookmark={() => setBookmarkDialogOpen(true)}
                        onDeleteBookmark={handleDeleteBookmark}
                        expandedNotes={expandedNotes}
                        toggleNote={toggleNote}
                    />
                </TabsContent>
            </Tabs>

            {/* Add Bookmark Dialog */}
            <Dialog
                open={bookmarkDialogOpen}
                onOpenChange={(open) => {
                    setBookmarkDialogOpen(open);
                    if (!open) resetBookmarkForm();
                }}
            >
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Add Bookmark</DialogTitle>
                        <DialogDescription>
                            Bookmark a specific timestamp in a transcript.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-3 py-2">
                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">
                                File <span className="text-destructive">*</span>
                            </label>
                            {/* Use a dropdown if media files exist, otherwise free text */}
                            {mediaFiles.length > 0 || jobs.length > 0 ? (
                                <Select value={bmFileKey} onValueChange={setBmFileKey}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select file..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {/* Show files from completed jobs first */}
                                        {Array.from(
                                            new Set(
                                                [
                                                    ...jobs
                                                        .filter((j) => j.status === "completed")
                                                        .map((j) => j.file_key),
                                                    ...mediaFiles.map((f) => f.filename),
                                                ],
                                            ),
                                        ).map((key) => (
                                            <SelectItem key={key} value={key}>
                                                {key.split("/").pop() || key}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            ) : (
                                <Input
                                    placeholder="e.g. interview.mp3"
                                    value={bmFileKey}
                                    onChange={(e) => setBmFileKey(e.target.value)}
                                />
                            )}
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">
                                Timestamp <span className="text-destructive">*</span>
                            </label>
                            <div className="flex items-center gap-2">
                                <Input
                                    type="number"
                                    min={0}
                                    placeholder="Min"
                                    className="w-24"
                                    value={bmMinutes}
                                    onChange={(e) => setBmMinutes(e.target.value)}
                                />
                                <span className="text-muted-foreground">:</span>
                                <Input
                                    type="number"
                                    min={0}
                                    max={59}
                                    placeholder="Sec"
                                    className="w-24"
                                    value={bmSeconds}
                                    onChange={(e) => setBmSeconds(e.target.value)}
                                />
                            </div>
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">Label</label>
                            <Input
                                placeholder="e.g. Key admission"
                                value={bmLabel}
                                onChange={(e) => setBmLabel(e.target.value)}
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">Note</label>
                            <textarea
                                className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:border-ring min-h-[60px] resize-y dark:bg-input/30"
                                placeholder="Optional note about this moment..."
                                value={bmNote}
                                onChange={(e) => setBmNote(e.target.value)}
                            />
                        </div>
                    </div>

                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => {
                                setBookmarkDialogOpen(false);
                                resetBookmarkForm();
                            }}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={handleAddBookmark}
                            disabled={bmSubmitting}
                        >
                            {bmSubmitting ? "Adding..." : "Add Bookmark"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
