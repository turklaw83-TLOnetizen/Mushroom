// ---- Transcription Page (case subtab) -----------------------------------
// Start and monitor transcription jobs for case files.
"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
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

    const [showStartForm, setShowStartForm] = useState(false);
    const [fileKey, setFileKey] = useState("");
    const [language, setLanguage] = useState("en");

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
        </div>
    );
}
