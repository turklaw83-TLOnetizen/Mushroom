// ---- Files Tab -----------------------------------------------------------
// Table view with size, upload date, ingestion date, and exclude checkbox.
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { FileUpload } from "@/components/shared/file-upload";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@/components/ui/table";
import {
    Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import type { FileItem } from "@/types/api";

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatDateTime(iso?: string): string {
    if (!iso) return "\u2014";
    try {
        const d = new Date(iso);
        return d.toLocaleDateString("en-US", {
            month: "short", day: "numeric", year: "numeric",
        }) + " " + d.toLocaleTimeString("en-US", {
            hour: "numeric", minute: "2-digit",
        });
    } catch {
        return iso;
    }
}

export default function FilesPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [uploadOpen, setUploadOpen] = useState(false);
    const [search, setSearch] = useState("");
    const [searchAnnotOpen, setSearchAnnotOpen] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");
    const [searchResults, setSearchResults] = useState<any[]>([]);
    const [searching, setSearching] = useState(false);

    const query = useQuery({
        queryKey: ["cases", caseId, "files"],
        queryFn: () => api.get<FileItem[]>(`/cases/${caseId}/files`, { getToken }),
    });

    const files = query.data ?? [];
    const filtered = search
        ? files.filter((f) => f.filename.toLowerCase().includes(search.toLowerCase()))
        : files;

    const excludeMutation = useMutationWithToast<{ filename: string; excluded: boolean }>({
        mutationFn: ({ filename, excluded }) =>
            excluded
                ? api.delete(`/cases/${caseId}/files/${encodeURIComponent(filename)}/exclude`, { getToken })
                : api.post(`/cases/${caseId}/files/${encodeURIComponent(filename)}/exclude`, {}, { getToken }),
        successMessage: "File exclusion updated",
        invalidateKeys: [["cases", caseId, "files"]],
    });

    const pinMutation = useMutationWithToast<{ filename: string; pinned: boolean }>({
        mutationFn: ({ filename, pinned }) =>
            pinned
                ? api.delete(`/cases/${caseId}/files/${encodeURIComponent(filename)}/pin`, { getToken })
                : api.post(`/cases/${caseId}/files/${encodeURIComponent(filename)}/pin`, {}, { getToken }),
        successMessage: "Pin updated",
        invalidateKeys: [["cases", caseId, "files"]],
    });

    const handleSearchAnnotations = async () => {
        if (!searchQuery || searchQuery.trim().length < 2) return;
        setSearching(true);
        try {
            const res = await api.get<{ items: any[]; total: number }>(
                `/cases/${caseId}/annotations/search?q=${encodeURIComponent(searchQuery)}`,
                { getToken },
            );
            setSearchResults(res.items || []);
        } catch {
            setSearchResults([]);
        } finally {
            setSearching(false);
        }
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
                <div>
                    <h2 className="text-lg font-semibold">Case Files</h2>
                    <p className="text-sm text-muted-foreground">
                        {files.length} file{files.length !== 1 ? "s" : ""} uploaded
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Input
                        placeholder="Search files..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="w-48 h-8 text-sm"
                    />
                    <Button variant="outline" size="sm" onClick={() => setSearchAnnotOpen(true)}>
                        Search Annotations
                    </Button>
                    <Button size="sm" onClick={() => setUploadOpen(true)}>
                        Upload
                    </Button>
                </div>
            </div>

            <Card>
                <CardContent className="p-0">
                    {query.isLoading ? (
                        <div className="p-6 space-y-3">
                            {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
                        </div>
                    ) : filtered.length === 0 ? (
                        <div className="text-center py-12 text-muted-foreground">
                            {search ? "No files match your search" : "No files uploaded yet"}
                        </div>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead className="w-8"></TableHead>
                                    <TableHead>Filename</TableHead>
                                    <TableHead className="w-24 text-right">Size</TableHead>
                                    <TableHead className="w-44">Uploaded</TableHead>
                                    <TableHead className="w-44">Ingested</TableHead>
                                    <TableHead className="w-24 text-center">Exclude</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {filtered.map((file) => (
                                    <TableRow
                                        key={file.filename}
                                        className={file.excluded ? "opacity-50" : ""}
                                    >
                                        <TableCell className="px-2">
                                            <button
                                                className={`text-sm transition-opacity ${file.pinned ? "opacity-100" : "opacity-30 hover:opacity-70"}`}
                                                title={file.pinned ? "Unpin" : "Pin"}
                                                onClick={() => pinMutation.mutate({ filename: file.filename, pinned: !!file.pinned })}
                                            >
                                                {"\uD83D\uDCCC"}
                                            </button>
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                <span className="font-medium text-sm">{file.filename}</span>
                                                {file.tags?.map((tag) => (
                                                    <Badge key={tag} variant="secondary" className="text-[10px] py-0 px-1">
                                                        {tag}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-right text-sm tabular-nums text-muted-foreground">
                                            {formatSize(file.size)}
                                        </TableCell>
                                        <TableCell className="text-sm text-muted-foreground">
                                            {formatDateTime(file.uploaded_at)}
                                        </TableCell>
                                        <TableCell className="text-sm">
                                            {file.ingested_at ? (
                                                <span className="text-emerald-500">{formatDateTime(file.ingested_at)}</span>
                                            ) : (
                                                <span className="text-muted-foreground">Not ingested</span>
                                            )}
                                        </TableCell>
                                        <TableCell className="text-center">
                                            <input
                                                type="checkbox"
                                                checked={!!file.excluded}
                                                onChange={() => excludeMutation.mutate({
                                                    filename: file.filename,
                                                    excluded: !!file.excluded,
                                                })}
                                                className="h-4 w-4 rounded border-border accent-destructive cursor-pointer"
                                                title={file.excluded ? "Click to include in analysis" : "Click to exclude from analysis"}
                                            />
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </CardContent>
            </Card>

            {/* Upload Dialog */}
            <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
                <DialogContent className="sm:max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Upload Files</DialogTitle>
                    </DialogHeader>
                    <FileUpload
                        caseId={caseId}
                        onUploadComplete={() => {
                            setUploadOpen(false);
                            queryClient.invalidateQueries({ queryKey: ["cases", caseId, "files"] });
                        }}
                    />
                </DialogContent>
            </Dialog>

            {/* Search Annotations Dialog */}
            <Dialog open={searchAnnotOpen} onOpenChange={setSearchAnnotOpen}>
                <DialogContent className="sm:max-w-lg max-h-[80vh] flex flex-col">
                    <DialogHeader>
                        <DialogTitle>Search Annotations</DialogTitle>
                    </DialogHeader>
                    <div className="flex gap-2">
                        <Input
                            placeholder="Search notes and highlights..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && handleSearchAnnotations()}
                        />
                        <Button onClick={handleSearchAnnotations} disabled={searching || searchQuery.trim().length < 2}>
                            {searching ? "..." : "Search"}
                        </Button>
                    </div>
                    <div className="overflow-y-auto flex-1 space-y-2 mt-2">
                        {searchResults.length === 0 && !searching && (
                            <p className="text-sm text-muted-foreground text-center py-4">
                                {searchQuery ? "No results found" : "Enter a search term"}
                            </p>
                        )}
                        {searchResults.map((ann, i) => {
                            const colorMap: Record<string, string> = {
                                yellow: "bg-yellow-500/20 text-yellow-700 dark:text-yellow-400",
                                green: "bg-green-500/20 text-green-700 dark:text-green-400",
                                blue: "bg-blue-500/20 text-blue-700 dark:text-blue-400",
                                red: "bg-red-500/20 text-red-700 dark:text-red-400",
                                purple: "bg-purple-500/20 text-purple-700 dark:text-purple-400",
                            };
                            const colorCls = colorMap[ann.color] || colorMap.yellow;
                            return (
                                <Card key={ann.id || i} className="p-3">
                                    <div className="flex items-start gap-2">
                                        <Badge className={`text-xs shrink-0 ${colorCls}`}>{ann.color || "yellow"}</Badge>
                                        <div className="min-w-0 flex-1">
                                            {ann.note && (
                                                <p className="text-sm font-medium truncate">
                                                    {ann.note.length > 100 ? ann.note.slice(0, 100) + "..." : ann.note}
                                                </p>
                                            )}
                                            {ann.text && (
                                                <p className="text-xs text-muted-foreground italic truncate mt-0.5">
                                                    &ldquo;{ann.text.length > 80 ? ann.text.slice(0, 80) + "..." : ann.text}&rdquo;
                                                </p>
                                            )}
                                            <p className="text-xs text-muted-foreground mt-1">
                                                Page {ann.page} &middot; {ann.filename}
                                            </p>
                                        </div>
                                    </div>
                                </Card>
                            );
                        })}
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}
