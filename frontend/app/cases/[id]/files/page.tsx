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
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

interface FileItem {
    filename: string;
    size: number;
    tags: string[];
    uploaded_at?: string;
    ocr_status?: string;
}

function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FilesPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [uploadOpen, setUploadOpen] = useState(false);

    const query = useQuery({
        queryKey: ["cases", caseId, "files"],
        queryFn: () => api.get<FileItem[]>(`/cases/${caseId}/files`, { getToken }),
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
            renderItem={(file, i) => (
                <Card key={i} className="hover:bg-accent/30 transition-colors cursor-pointer">
                    <CardContent className="flex items-center justify-between py-3">
                        <div className="flex items-center gap-3">
                            <span className="text-2xl">📄</span>
                            <div>
                                <p className="font-medium text-sm">{file.filename}</p>
                                <p className="text-xs text-muted-foreground">
                                    {formatSize(file.size)}
                                    {file.uploaded_at && ` · ${file.uploaded_at}`}
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
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
        </DataPage>
    );
}
