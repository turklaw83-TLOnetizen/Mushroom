// ---- PDF Viewer Component -----------------------------------------------
// Inline iframe-based PDF viewer for case documents.
"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface PdfViewerProps {
    /** Case ID for file path */
    caseId: string;
    /** Filename to view */
    filename: string;
    /** Trigger button label (optional, defaults to filename) */
    label?: string;
}

export function PdfViewer({ caseId, filename, label }: PdfViewerProps) {
    const [open, setOpen] = useState(false);
    const { getToken } = useAuth();
    const [pdfUrl, setPdfUrl] = useState<string | null>(null);

    const handleOpen = async () => {
        try {
            const token = await getToken();
            const res = await fetch(
                `${API_BASE}/api/v1/cases/${caseId}/files/${encodeURIComponent(filename)}`,
                { headers: { Authorization: `Bearer ${token}` } },
            );
            if (!res.ok) throw new Error("Failed to load file");
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            setPdfUrl(url);
            setOpen(true);
        } catch {
            setPdfUrl(null);
        }
    };

    const handleClose = () => {
        setOpen(false);
        if (pdfUrl) {
            URL.revokeObjectURL(pdfUrl);
            setPdfUrl(null);
        }
    };

    return (
        <>
            <Button
                variant="ghost"
                size="sm"
                className="text-xs truncate max-w-[200px]"
                onClick={handleOpen}
            >
                📄 {label || filename}
            </Button>

            <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
                <DialogContent className="max-w-4xl h-[85vh] p-0 gap-0 flex flex-col">
                    <DialogHeader className="p-4 pb-2 shrink-0 border-b">
                        <DialogTitle className="text-sm truncate">{filename}</DialogTitle>
                    </DialogHeader>
                    <div className="flex-1 min-h-0">
                        {pdfUrl ? (
                            <iframe
                                src={pdfUrl}
                                className="w-full h-full border-0"
                                title={filename}
                            />
                        ) : (
                            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                                Loading...
                            </div>
                        )}
                    </div>
                </DialogContent>
            </Dialog>
        </>
    );
}
