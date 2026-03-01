// ---- Transcription Tab (Phase 18) -----------------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

interface TranscriptSegment {
    speaker: string;
    start_time: number;
    end_time: number;
    text: string;
}

interface DepositionAnnotation {
    id: string;
    timestamp: number;
    type: "note" | "objection" | "key_testimony" | "impeachment" | "exhibit_reference";
    content: string;
    created_by: string;
    created_at: string;
}

interface TranscriptionJob {
    id: string;
    file_name: string;
    status: "pending" | "processing" | "complete" | "error";
    transcript?: TranscriptSegment[];
    annotations?: DepositionAnnotation[];
    duration_seconds?: number;
    speaker_count?: number;
    created_at: string;
}

const ANNOTATION_COLORS: Record<string, string> = {
    note: "bg-blue-500/10 text-blue-400 border-blue-500/30",
    objection: "bg-red-500/10 text-red-400 border-red-500/30",
    key_testimony: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    impeachment: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    exhibit_reference: "bg-purple-500/10 text-purple-400 border-purple-500/30",
};

function formatTime(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function TranscriptionPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [selectedJob, setSelectedJob] = useState<string | null>(null);
    const [annotationType, setAnnotationType] = useState<DepositionAnnotation["type"]>("note");
    const [annotationText, setAnnotationText] = useState("");
    const [selectedTimestamp, setSelectedTimestamp] = useState<number>(0);

    const { data: jobs, isLoading } = useQuery({
        queryKey: ["transcription-jobs", caseId],
        queryFn: () =>
            api.get<TranscriptionJob[]>(`/cases/${caseId}/transcription/jobs`, { getToken }),
    });

    const selectedJobData = jobs?.find((j) => j.id === selectedJob);

    const addAnnotationMutation = useMutation({
        mutationFn: (payload: { job_id: string; type: string; content: string; timestamp: number }) =>
            api.post(`/cases/${caseId}/transcription/jobs/${payload.job_id}/annotations`, payload, { getToken }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["transcription-jobs", caseId] });
            setAnnotationText("");
        },
    });

    return (
        <div className="space-y-5">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">Transcription & Depositions</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Audio transcription with speaker diarization and annotations
                    </p>
                </div>
            </div>

            {isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 3 }).map((_, i) => (
                        <Skeleton key={i} className="h-20 w-full rounded-lg" />
                    ))}
                </div>
            ) : !jobs || jobs.length === 0 ? (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        <p className="text-lg mb-2">No transcription jobs</p>
                        <p className="text-sm">
                            Upload an audio/video file in the Files tab and start transcription from there.
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    {/* Job List */}
                    <div className="space-y-2">
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                            Jobs ({jobs.length})
                        </p>
                        {jobs.map((job) => (
                            <Card
                                key={job.id}
                                className={`cursor-pointer transition-colors ${
                                    selectedJob === job.id
                                        ? "border-primary bg-primary/5"
                                        : "hover:bg-accent/30"
                                }`}
                                onClick={() => setSelectedJob(job.id)}
                            >
                                <CardContent className="py-3">
                                    <div className="flex items-center justify-between">
                                        <p className="text-sm font-medium truncate">{job.file_name}</p>
                                        <Badge
                                            variant={
                                                job.status === "complete"
                                                    ? "default"
                                                    : job.status === "error"
                                                    ? "destructive"
                                                    : "secondary"
                                            }
                                            className="text-[10px] shrink-0 ml-2"
                                        >
                                            {job.status}
                                        </Badge>
                                    </div>
                                    <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                                        {job.speaker_count && <span>{job.speaker_count} speakers</span>}
                                        {job.duration_seconds && (
                                            <span>{formatTime(job.duration_seconds)}</span>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>

                    {/* Transcript View */}
                    <div className="lg:col-span-2">
                        {selectedJobData ? (
                            <div className="space-y-4">
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="text-base">
                                            Transcript: {selectedJobData.file_name}
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="max-h-[500px] overflow-y-auto space-y-2">
                                        {selectedJobData.transcript?.map((seg, i) => (
                                            <div
                                                key={i}
                                                className={`flex gap-3 group cursor-pointer rounded px-1 -mx-1 transition-colors ${
                                                    selectedTimestamp === seg.start_time
                                                        ? "bg-primary/10"
                                                        : "hover:bg-accent/30"
                                                }`}
                                                onClick={() => setSelectedTimestamp(seg.start_time)}
                                            >
                                                <span className="text-xs text-muted-foreground w-14 shrink-0 pt-0.5 font-mono">
                                                    {formatTime(seg.start_time)}
                                                </span>
                                                <div>
                                                    <span className="text-xs font-semibold text-indigo-400">
                                                        {seg.speaker}:
                                                    </span>
                                                    <span className="text-sm ml-1">{seg.text}</span>
                                                </div>
                                            </div>
                                        )) || (
                                            <p className="text-sm text-muted-foreground italic">
                                                Transcript not available yet.
                                            </p>
                                        )}
                                    </CardContent>
                                </Card>

                                {/* Annotations */}
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="text-base">
                                            Annotations ({selectedJobData.annotations?.length || 0})
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-3">
                                        {selectedJobData.annotations?.map((ann) => (
                                            <div
                                                key={ann.id}
                                                className={`p-3 rounded-lg border ${ANNOTATION_COLORS[ann.type] || ""}`}
                                            >
                                                <div className="flex items-center gap-2 mb-1">
                                                    <Badge variant="outline" className="text-[10px] capitalize">
                                                        {ann.type.replace("_", " ")}
                                                    </Badge>
                                                    <span className="text-xs text-muted-foreground font-mono">
                                                        {formatTime(ann.timestamp)}
                                                    </span>
                                                </div>
                                                <p className="text-sm">{ann.content}</p>
                                            </div>
                                        ))}

                                        {/* Add Annotation */}
                                        <div className="pt-3 border-t border-border space-y-2">
                                            <p className="text-xs text-muted-foreground">
                                                Timestamp: <span className="font-mono">{formatTime(selectedTimestamp)}</span>
                                                <span className="ml-1 italic">(click a transcript segment to change)</span>
                                            </p>
                                            <div className="flex gap-2">
                                                <select
                                                    value={annotationType}
                                                    onChange={(e) =>
                                                        setAnnotationType(e.target.value as DepositionAnnotation["type"])
                                                    }
                                                    className="text-xs bg-muted border border-border rounded px-2 py-1"
                                                >
                                                    <option value="note">Note</option>
                                                    <option value="objection">Objection</option>
                                                    <option value="key_testimony">Key Testimony</option>
                                                    <option value="impeachment">Impeachment</option>
                                                    <option value="exhibit_reference">Exhibit Ref</option>
                                                </select>
                                                <input
                                                    type="text"
                                                    placeholder="Add annotation..."
                                                    value={annotationText}
                                                    onChange={(e) => setAnnotationText(e.target.value)}
                                                    className="flex-1 text-sm bg-muted border border-border rounded px-3 py-1"
                                                />
                                                <Button
                                                    size="sm"
                                                    disabled={!annotationText || addAnnotationMutation.isPending}
                                                    onClick={() =>
                                                        addAnnotationMutation.mutate({
                                                            job_id: selectedJobData.id,
                                                            type: annotationType,
                                                            content: annotationText,
                                                            timestamp: selectedTimestamp,
                                                        })
                                                    }
                                                >
                                                    Add
                                                </Button>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        ) : (
                            <Card className="border-dashed h-full">
                                <CardContent className="py-20 text-center text-muted-foreground">
                                    Select a transcription job to view the transcript.
                                </CardContent>
                            </Card>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
