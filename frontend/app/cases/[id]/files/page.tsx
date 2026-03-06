// ---- Files Tab (updated with FileUpload) --------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { DataPage } from "@/components/shared/data-page";
import { FileUpload } from "@/components/shared/file-upload";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import type { FileItem } from "@/types/api";

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export default function FilesPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [uploadOpen, setUploadOpen] = useState(false);
    const [searchOpen, setSearchOpen] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");
    const [searchResults, setSearchResults] = useState<any[]>([]);
    const [searching, setSearching] = useState(false);

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

    const query = useQuery({
        queryKey: ["cases", caseId, "files"],
        queryFn: () => api.get<FileItem[]>(`/cases/${caseId}/files`, { getToken }),
    });

    const pinMutation = useMutationWithToast<{ filename: string; pinned: boolean }>({
        mutationFn: ({ filename, pinned }) =>
            pinned
                ? api.delete(`/cases/${caseId}/files/${encodeURIComponent(filename)}/pin`, { getToken })
                : api.post(`/cases/${caseId}/files/${encodeURIComponent(filename)}/pin`, {}, { getToken }),
        successMessage: "Pin updated",
        invalidateKeys: [["cases", caseId, "files"]],
    });

    return (
        <DataPage
            title="Files"
            subtitle="Uploaded documents and files for this case"
            query={query}
            searchFilter={(f, s) => f.filename.toLowerCase().includes(s)}
            searchPlaceholder="Search files..."
            createLabel="Upload"
            onCreateClick={() => setUploadOpen(true)}
            headerActions={
                <Button variant="outline" size="sm" onClick={() => setSearchOpen(true)}>
                    Search Annotations
                </Button>
            }
            renderItem={(file, i) => (
                <Card key={i} className="group hover:bg-accent/30 transition-colors cursor-pointer">
                    <CardContent className="flex items-center justify-between py-3">
                        <div className="flex items-center gap-3">
                            <span className="text-2xl" aria-hidden="true">📄</span>
                            <div>
                                <p className="font-medium text-sm">{file.filename}</p>
                                <p className="text-xs text-muted-foreground">
                                    {formatSize(file.size)}
                                    {file.uploaded_at && ` · ${file.uploaded_at}`}
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            <Button
                                variant="ghost"
                                size="sm"
                                className={`h-7 w-7 p-0 ${file.pinned ? "opacity-100" : "opacity-0 group-hover:opacity-100"} transition-opacity`}
                                title={file.pinned ? "Unpin file" : "Pin file"}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    pinMutation.mutate({ filename: file.filename, pinned: !!file.pinned });
                                }}
                            >
                                <span aria-hidden="true" className={file.pinned ? "text-brand-indigo" : ""}>
                                    {"\uD83D\uDCCC"}
                                </span>
                            </Button>
                            {file.tags?.map((tag) => (
                                <Badge key={tag} variant="secondary" className="text-xs">
                                    {tag}
                                </Badge>
                            ))}
                            {file.ocr_status && (
                                <Badge
                                    variant="outline"
                                    className={
                                        file.ocr_status === "complete"
                                            ? "text-emerald-400 border-emerald-500/30"
                                            : "text-amber-400 border-amber-500/30"
                                    }
                                >
                                    OCR: {file.ocr_status}
                                </Badge>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}
        >
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
            <Dialog open={searchOpen} onOpenChange={setSearchOpen}>
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
        </DataPage>
    );
}
