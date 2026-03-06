// ---- Transcription Page (case subtab) -----------------------------------
// Start and monitor transcription jobs for case files.
// Includes timestamp bookmarks for transcript navigation.
"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
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

interface TranscriptionJob {
    job_id: string;
    file_key: string;
    language: string;
    status: string;
    created_at: string;
    completed_at?: string;
    download_url?: string;
}

interface JobsResponse {
    items: TranscriptionJob[];
}

interface StartResponse {
    status: string;
    job_id: string;
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

function formatSeconds(s: number): string {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, "0")}`;
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

export default function TranscriptionPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    const { canEdit, canDelete } = useRole();

    const [showStartForm, setShowStartForm] = useState(false);
    const [fileKey, setFileKey] = useState("");
    const [language, setLanguage] = useState("en");

    // Bookmark state
    const [bookmarkDialogOpen, setBookmarkDialogOpen] = useState(false);
    const [bmFileKey, setBmFileKey] = useState("");
    const [bmMinutes, setBmMinutes] = useState("");
    const [bmSeconds, setBmSeconds] = useState("");
    const [bmLabel, setBmLabel] = useState("");
    const [bmNote, setBmNote] = useState("");
    const [bmSubmitting, setBmSubmitting] = useState(false);

    // Check if any jobs are currently running
    const { data, isLoading } = useQuery({
        queryKey: ["transcription-jobs", caseId],
        queryFn: () =>
            api.get<JobsResponse>(`/cases/${caseId}/transcription/jobs`, { getToken }),
    });

    const jobs = data?.items ?? [];

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
        // Update the main query data on each poll
        select: (pollData) => {
            queryClient.setQueryData(["transcription-jobs", caseId], pollData);
            return pollData;
        },
    });

    // Start transcription mutation
    const startTranscription = useMutation({
        mutationFn: (body: { file_key: string; language: string }) =>
            api.post<StartResponse>(`/cases/${caseId}/transcription/start`, body, { getToken }),
        onSuccess: (result) => {
            toast.success("Transcription started", {
                description: `Job ${result.job_id} queued`,
            });
            queryClient.invalidateQueries({ queryKey: ["transcription-jobs", caseId] });
            setShowStartForm(false);
            setFileKey("");
            setLanguage("en");
        },
        onError: (err) => {
            toast.error("Failed to start transcription", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        },
    });

    const handleStart = () => {
        if (!fileKey.trim()) {
            toast.error("File key is required");
            return;
        }
        startTranscription.mutate({ file_key: fileKey.trim(), language });
    };

    // ---- Bookmarks ----------------------------------------------------------

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

    return (
        <div className="space-y-5">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">Transcription</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Audio and video transcription jobs
                    </p>
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowStartForm(!showStartForm)}
                >
                    {showStartForm ? "Cancel" : "Start Transcription"}
                </Button>
            </div>

            {/* Start transcription form */}
            {showStartForm && (
                <Card>
                    <CardContent className="py-4 space-y-3">
                        <p className="text-sm font-medium">Start Transcription</p>
                        <Input
                            placeholder="File key"
                            value={fileKey}
                            onChange={(e) => setFileKey(e.target.value)}
                        />
                        <div className="flex items-center gap-3">
                            <label className="text-sm text-muted-foreground">Language:</label>
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
                                disabled={startTranscription.isPending || !fileKey.trim()}
                            >
                                {startTranscription.isPending ? "Starting..." : "Start"}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Jobs list */}
            {isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-18 w-full rounded-lg" />
                    ))}
                </div>
            ) : jobs.length === 0 ? (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        No transcription jobs yet. Start one by clicking the button above.
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-2">
                    {jobs.map((job) => (
                        <Card key={job.job_id} className="hover:bg-accent/20 transition-colors">
                            <CardContent className="py-3">
                                <div className="flex items-center justify-between">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <p className="text-sm font-medium truncate">
                                                {job.file_key}
                                            </p>
                                            <Badge
                                                variant="outline"
                                                className={`text-[10px] shrink-0 ${statusColor[job.status] || ""}`}
                                            >
                                                {job.status}
                                            </Badge>
                                        </div>
                                        <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                            <span>
                                                Language: {languageOptions.find((l) => l.value === job.language)?.label || job.language}
                                            </span>
                                            <span>Created: {formatTimestamp(job.created_at)}</span>
                                            {job.completed_at && (
                                                <span>Completed: {formatTimestamp(job.completed_at)}</span>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0 ml-4">
                                        {job.status === "completed" && job.download_url && (
                                            <Button variant="outline" size="sm" asChild>
                                                <a
                                                    href={job.download_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                >
                                                    View
                                                </a>
                                            </Button>
                                        )}
                                        {(job.status === "running" || job.status === "pending") && (
                                            <span className="text-xs text-blue-400 animate-pulse">
                                                Processing...
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* ---- Bookmarks Section ---- */}
            <div className="border-t pt-5 mt-5">
                <div className="flex items-center justify-between mb-3">
                    <div>
                        <h3 className="text-lg font-semibold">Bookmarks</h3>
                        <p className="text-sm text-muted-foreground">
                            Mark important timestamps in transcripts for quick reference.
                        </p>
                    </div>
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

                {bookmarksQuery.isLoading ? (
                    <div className="flex gap-2 flex-wrap">
                        {Array.from({ length: 3 }).map((_, i) => (
                            <Skeleton key={i} className="h-8 w-28 rounded-full" />
                        ))}
                    </div>
                ) : bookmarks.length === 0 ? (
                    <p className="text-sm text-muted-foreground py-4">
                        No bookmarks yet. Add one to mark important transcript moments.
                    </p>
                ) : (
                    <div className="flex gap-2 flex-wrap">
                        {bookmarks.map((bm) => (
                            <div
                                key={bm.id}
                                className="group inline-flex items-center gap-1.5 rounded-full border bg-accent/30 hover:bg-accent/50 transition-colors px-3 py-1 cursor-default"
                                title={bm.note || bm.label}
                            >
                                <span className="text-xs font-mono text-blue-400">
                                    {formatSeconds(bm.timestamp_seconds)}
                                </span>
                                <span className="text-xs truncate max-w-[120px]">
                                    {bm.label}
                                </span>
                                {bm.file_key && (
                                    <span className="text-[10px] text-muted-foreground truncate max-w-[80px]">
                                        ({bm.file_key.split("/").pop()})
                                    </span>
                                )}
                                {canDelete && (
                                    <button
                                        className="text-destructive opacity-0 group-hover:opacity-100 transition-opacity text-xs ml-0.5"
                                        aria-label={`Delete bookmark ${bm.label}`}
                                        onClick={() => handleDeleteBookmark(bm.id)}
                                    >
                                        x
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>

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
                                File Key <span className="text-destructive">*</span>
                            </label>
                            <Input
                                placeholder="e.g. interview.mp3:1234567"
                                value={bmFileKey}
                                onChange={(e) => setBmFileKey(e.target.value)}
                            />
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
