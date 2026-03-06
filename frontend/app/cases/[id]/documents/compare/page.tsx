// ---- Document Comparison Viewer ------------------------------------------
// Side-by-side document diff: pick two files, compare line-by-line.
"use client";

import { useState, useMemo, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type { FileItem } from "@/types/api";

// ---- Types ---------------------------------------------------------------

interface DiffLine {
    type: "added" | "removed" | "unchanged";
    text: string;
    lineA?: number;
    lineB?: number;
}

interface DiffStats {
    totalLinesA: number;
    totalLinesB: number;
    added: number;
    removed: number;
    unchanged: number;
    similarity: number;
}

// ---- Diff Engine ---------------------------------------------------------

function computeLineDiff(textA: string, textB: string): { lines: DiffLine[]; stats: DiffStats } {
    const linesA = textA.split("\n");
    const linesB = textB.split("\n");

    const setA = new Set(linesA);
    const setB = new Set(linesB);

    const result: DiffLine[] = [];
    let lineNumA = 0;
    let lineNumB = 0;
    let added = 0;
    let removed = 0;
    let unchanged = 0;

    // Build a mapping of lines in B for quick lookup
    const bLineMap = new Map<string, number[]>();
    linesB.forEach((line, idx) => {
        const existing = bLineMap.get(line) || [];
        existing.push(idx);
        bLineMap.set(line, existing);
    });

    // Two-pointer merge: walk through both arrays
    const usedB = new Set<number>();

    for (let i = 0; i < linesA.length; i++) {
        const line = linesA[i];
        lineNumA = i + 1;

        if (setB.has(line)) {
            // Find matching line in B that hasn't been used
            const candidates = bLineMap.get(line) || [];
            const matchIdx = candidates.find((idx) => !usedB.has(idx));

            if (matchIdx !== undefined) {
                // Output any lines from B before this match that haven't been seen
                for (let j = 0; j < matchIdx; j++) {
                    if (!usedB.has(j) && !setA.has(linesB[j])) {
                        result.push({ type: "added", text: linesB[j], lineB: j + 1 });
                        usedB.add(j);
                        added++;
                    }
                }

                result.push({ type: "unchanged", text: line, lineA: lineNumA, lineB: matchIdx + 1 });
                usedB.add(matchIdx);
                unchanged++;
            } else {
                result.push({ type: "removed", text: line, lineA: lineNumA });
                removed++;
            }
        } else {
            result.push({ type: "removed", text: line, lineA: lineNumA });
            removed++;
        }
    }

    // Remaining lines in B not matched
    for (let j = 0; j < linesB.length; j++) {
        if (!usedB.has(j)) {
            result.push({ type: "added", text: linesB[j], lineB: j + 1 });
            added++;
        }
    }

    const totalLines = Math.max(linesA.length, linesB.length);
    const similarity = totalLines > 0 ? Math.round((unchanged / totalLines) * 100) : 100;

    return {
        lines: result,
        stats: {
            totalLinesA: linesA.length,
            totalLinesB: linesB.length,
            added,
            removed,
            unchanged,
            similarity,
        },
    };
}

// ---- Stat Card -----------------------------------------------------------

function StatCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
    return (
        <div className="text-center px-4 py-2">
            <div className={cn("text-2xl font-bold tabular-nums", color)}>{value}</div>
            <div className="text-xs text-muted-foreground">{label}</div>
        </div>
    );
}

// ---- Diff Line Component -------------------------------------------------

function DiffLineRow({ line }: { line: DiffLine }) {
    const bgClass =
        line.type === "added"
            ? "bg-emerald-500/10 border-l-2 border-emerald-500"
            : line.type === "removed"
                ? "bg-red-500/10 border-l-2 border-red-500"
                : "border-l-2 border-transparent";

    const prefixChar =
        line.type === "added" ? "+" : line.type === "removed" ? "-" : " ";

    const prefixColor =
        line.type === "added"
            ? "text-emerald-400"
            : line.type === "removed"
                ? "text-red-400"
                : "text-muted-foreground/30";

    return (
        <div className={cn("flex items-start gap-0 font-mono text-xs hover:bg-accent/20", bgClass)}>
            <span className="w-10 shrink-0 text-right pr-1 text-muted-foreground/50 select-none">
                {line.lineA ?? ""}
            </span>
            <span className="w-10 shrink-0 text-right pr-1 text-muted-foreground/50 select-none">
                {line.lineB ?? ""}
            </span>
            <span className={cn("w-4 shrink-0 text-center select-none font-bold", prefixColor)}>
                {prefixChar}
            </span>
            <span className="flex-1 whitespace-pre-wrap break-all py-px pr-2">
                {line.text || "\u00A0"}
            </span>
        </div>
    );
}

// ---- File Content Panel --------------------------------------------------

function FileContentPanel({
    label,
    fileName,
    content,
    isLoading,
}: {
    label: string;
    fileName: string | null;
    content: string | null;
    isLoading: boolean;
}) {
    if (!fileName) {
        return (
            <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm p-8 border rounded-lg border-dashed">
                Select a document for {label}
            </div>
        );
    }

    if (isLoading) {
        return (
            <div className="flex-1 space-y-2 p-4">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-4 w-5/6" />
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-4 w-4/5" />
            </div>
        );
    }

    return (
        <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
                <Badge variant="outline" className="text-xs truncate max-w-[200px]">
                    {fileName}
                </Badge>
                <span className="text-xs text-muted-foreground">
                    {content ? `${content.split("\n").length} lines` : "No content"}
                </span>
            </div>
            <div className="border rounded-lg overflow-auto max-h-[500px] bg-muted/20">
                {content ? (
                    <pre className="text-xs font-mono p-3 whitespace-pre-wrap break-words">
                        {content}
                    </pre>
                ) : (
                    <div className="p-6 text-center text-sm text-muted-foreground">
                        Content preview not available for this file type.
                        The file exists but its text content could not be loaded.
                    </div>
                )}
            </div>
        </div>
    );
}

// ---- Main Page -----------------------------------------------------------

export default function DocumentComparePage() {
    const params = useParams();
    const router = useRouter();
    const caseId = params.id as string;
    const { getToken } = useAuth();

    const [selectedFileA, setSelectedFileA] = useState<string | null>(null);
    const [selectedFileB, setSelectedFileB] = useState<string | null>(null);
    const [showDiff, setShowDiff] = useState(false);

    // Fetch case files
    const { data: files, isLoading: filesLoading } = useQuery({
        queryKey: ["cases", caseId, "files"],
        queryFn: () => api.get<FileItem[]>(`/cases/${caseId}/files`, { getToken }),
    });

    // Fetch content for file A
    const { data: contentA, isLoading: contentALoading } = useQuery({
        queryKey: ["cases", caseId, "file-content", selectedFileA],
        queryFn: () =>
            api.get<{ content: string }>(
                `/cases/${caseId}/files/${encodeURIComponent(selectedFileA!)}/content`,
                { getToken },
            ).then((r) => r.content)
            .catch(() => null),
        enabled: !!selectedFileA,
    });

    // Fetch content for file B
    const { data: contentB, isLoading: contentBLoading } = useQuery({
        queryKey: ["cases", caseId, "file-content", selectedFileB],
        queryFn: () =>
            api.get<{ content: string }>(
                `/cases/${caseId}/files/${encodeURIComponent(selectedFileB!)}/content`,
                { getToken },
            ).then((r) => r.content)
            .catch(() => null),
        enabled: !!selectedFileB,
    });

    // Compute diff when both files are loaded and user clicks Compare
    const diff = useMemo(() => {
        if (!showDiff || !contentA || !contentB) return null;
        return computeLineDiff(contentA, contentB);
    }, [showDiff, contentA, contentB]);

    const handleCompare = useCallback(() => {
        if (selectedFileA && selectedFileB) {
            setShowDiff(true);
        }
    }, [selectedFileA, selectedFileB]);

    const handleReset = useCallback(() => {
        setShowDiff(false);
    }, []);

    const canCompare = selectedFileA && selectedFileB && selectedFileA !== selectedFileB;

    // File list for selectors
    const fileList = files || [];

    // ---- Loading State ----
    if (filesLoading) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-8 w-64" />
                <div className="grid grid-cols-2 gap-4">
                    <Skeleton className="h-40 rounded-lg" />
                    <Skeleton className="h-40 rounded-lg" />
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* ---- Header ---- */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-xl font-semibold tracking-tight">Document Comparison</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Compare two documents side by side with line-by-line diff highlighting
                    </p>
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => router.push(`/cases/${caseId}/documents`)}
                >
                    Back to Documents
                </Button>
            </div>

            {/* ---- File Selectors ---- */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Select Documents</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Document A Selector */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-muted-foreground">
                                Document A (Base)
                            </label>
                            <Select
                                value={selectedFileA ?? ""}
                                onValueChange={(v) => {
                                    setSelectedFileA(v);
                                    setShowDiff(false);
                                }}
                            >
                                <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Select first document..." />
                                </SelectTrigger>
                                <SelectContent>
                                    {fileList.map((f) => (
                                        <SelectItem
                                            key={f.filename}
                                            value={f.filename}
                                            disabled={f.filename === selectedFileB}
                                        >
                                            {f.filename}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            {selectedFileA && (
                                <p className="text-xs text-muted-foreground">
                                    {fileList.find((f) => f.filename === selectedFileA)?.size
                                        ? `${(fileList.find((f) => f.filename === selectedFileA)!.size / 1024).toFixed(1)} KB`
                                        : ""}
                                </p>
                            )}
                        </div>

                        {/* Document B Selector */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-muted-foreground">
                                Document B (Compare)
                            </label>
                            <Select
                                value={selectedFileB ?? ""}
                                onValueChange={(v) => {
                                    setSelectedFileB(v);
                                    setShowDiff(false);
                                }}
                            >
                                <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Select second document..." />
                                </SelectTrigger>
                                <SelectContent>
                                    {fileList.map((f) => (
                                        <SelectItem
                                            key={f.filename}
                                            value={f.filename}
                                            disabled={f.filename === selectedFileA}
                                        >
                                            {f.filename}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            {selectedFileB && (
                                <p className="text-xs text-muted-foreground">
                                    {fileList.find((f) => f.filename === selectedFileB)?.size
                                        ? `${(fileList.find((f) => f.filename === selectedFileB)!.size / 1024).toFixed(1)} KB`
                                        : ""}
                                </p>
                            )}
                        </div>
                    </div>

                    {/* Compare Button */}
                    <div className="flex items-center gap-3 mt-4">
                        <Button
                            onClick={handleCompare}
                            disabled={!canCompare || contentALoading || contentBLoading}
                        >
                            {contentALoading || contentBLoading ? (
                                <span className="flex items-center gap-2">
                                    <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                    Loading...
                                </span>
                            ) : (
                                "Compare Documents"
                            )}
                        </Button>
                        {showDiff && (
                            <Button variant="outline" size="sm" onClick={handleReset}>
                                Reset
                            </Button>
                        )}
                        {selectedFileA && selectedFileB && selectedFileA === selectedFileB && (
                            <p className="text-xs text-amber-400">
                                Select two different documents to compare.
                            </p>
                        )}
                    </div>
                </CardContent>
            </Card>

            {/* ---- Diff Stats ---- */}
            {diff && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Comparison Results</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-center justify-center gap-6 flex-wrap">
                            <StatCard
                                label="Lines in A"
                                value={diff.stats.totalLinesA}
                            />
                            <StatCard
                                label="Lines in B"
                                value={diff.stats.totalLinesB}
                            />
                            <StatCard
                                label="Added"
                                value={`+${diff.stats.added}`}
                                color="text-emerald-400"
                            />
                            <StatCard
                                label="Removed"
                                value={`-${diff.stats.removed}`}
                                color="text-red-400"
                            />
                            <StatCard
                                label="Unchanged"
                                value={diff.stats.unchanged}
                                color="text-muted-foreground"
                            />
                            <StatCard
                                label="Similarity"
                                value={`${diff.stats.similarity}%`}
                                color={
                                    diff.stats.similarity >= 80
                                        ? "text-emerald-400"
                                        : diff.stats.similarity >= 50
                                            ? "text-amber-400"
                                            : "text-red-400"
                                }
                            />
                        </div>

                        {/* Similarity Bar */}
                        <div className="mt-4 space-y-1">
                            <div className="flex items-center justify-between text-xs text-muted-foreground">
                                <span>Similarity</span>
                                <span className="font-mono">{diff.stats.similarity}%</span>
                            </div>
                            <div className="h-2 bg-muted rounded-full overflow-hidden">
                                <div
                                    className={cn(
                                        "h-full rounded-full transition-all duration-500",
                                        diff.stats.similarity >= 80
                                            ? "bg-emerald-500"
                                            : diff.stats.similarity >= 50
                                                ? "bg-amber-500"
                                                : "bg-red-500",
                                    )}
                                    style={{ width: `${diff.stats.similarity}%` }}
                                />
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* ---- Side-by-Side View (pre-diff) ---- */}
            {!showDiff && (selectedFileA || selectedFileB) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <FileContentPanel
                        label="Document A"
                        fileName={selectedFileA}
                        content={(contentA as string | null | undefined) ?? null}
                        isLoading={contentALoading}
                    />
                    <FileContentPanel
                        label="Document B"
                        fileName={selectedFileB}
                        content={(contentB as string | null | undefined) ?? null}
                        isLoading={contentBLoading}
                    />
                </div>
            )}

            {/* ---- Diff Output ---- */}
            {diff && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base flex items-center gap-3">
                            <span>Line-by-Line Diff</span>
                            <Badge variant="secondary" className="text-xs">
                                {diff.lines.length} lines
                            </Badge>
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {/* Column Headers */}
                        <div className="flex items-center gap-0 font-mono text-xs text-muted-foreground border-b pb-1 mb-1">
                            <span className="w-10 shrink-0 text-right pr-1">A</span>
                            <span className="w-10 shrink-0 text-right pr-1">B</span>
                            <span className="w-4 shrink-0" />
                            <span className="flex-1">Content</span>
                        </div>

                        {/* Diff Lines */}
                        <div className="max-h-[600px] overflow-auto rounded border bg-background">
                            {diff.lines.length === 0 ? (
                                <div className="p-6 text-center text-sm text-muted-foreground">
                                    Both documents are empty.
                                </div>
                            ) : (
                                diff.lines.map((line, i) => (
                                    <DiffLineRow key={i} line={line} />
                                ))
                            )}
                        </div>

                        {/* Legend */}
                        <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
                            <span className="flex items-center gap-1.5">
                                <span className="w-3 h-3 rounded bg-red-500/20 border border-red-500/40" />
                                Removed (only in A)
                            </span>
                            <span className="flex items-center gap-1.5">
                                <span className="w-3 h-3 rounded bg-emerald-500/20 border border-emerald-500/40" />
                                Added (only in B)
                            </span>
                            <span className="flex items-center gap-1.5">
                                <span className="w-3 h-3 rounded bg-background border" />
                                Unchanged
                            </span>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* ---- Empty State ---- */}
            {fileList.length === 0 && (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center">
                        <p className="text-muted-foreground">
                            No files uploaded to this case yet.
                        </p>
                        <p className="text-sm text-muted-foreground mt-1">
                            Upload documents in the Files tab to enable comparison.
                        </p>
                        <Button
                            variant="outline"
                            size="sm"
                            className="mt-4"
                            onClick={() => router.push(`/cases/${caseId}/files`)}
                        >
                            Go to Files
                        </Button>
                    </CardContent>
                </Card>
            )}

            {fileList.length === 1 && (
                <Card className="border-dashed">
                    <CardContent className="py-8 text-center">
                        <p className="text-sm text-muted-foreground">
                            Only one file found. Upload at least two documents to compare.
                        </p>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
