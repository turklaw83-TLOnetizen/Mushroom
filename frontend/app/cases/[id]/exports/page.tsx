// ---- Export Gallery Page -------------------------------------------------
// Download PDF reports, Word reports, IRAC briefs, and trial binders.
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { usePrep } from "@/hooks/use-prep";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ExportFormat {
    id: string;
    label: string;
    description: string;
    icon: string;
    endpoint: string;
    mime: string;
    extension: string;
}

const EXPORT_FORMATS: ExportFormat[] = [
    {
        id: "pdf",
        label: "PDF Report",
        description: "Full analysis report in PDF format with charts and tables",
        icon: "📄",
        endpoint: "pdf",
        mime: "application/pdf",
        extension: "pdf",
    },
    {
        id: "word",
        label: "Word Report",
        description: "Editable Word document with all analysis modules",
        icon: "📝",
        endpoint: "word",
        mime: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        extension: "docx",
    },
    {
        id: "brief",
        label: "IRAC Brief",
        description: "Issue-Rule-Application-Conclusion legal brief outline",
        icon: "⚖️",
        endpoint: "brief",
        mime: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        extension: "docx",
    },
    {
        id: "trial-binder",
        label: "Trial Binder",
        description: "Comprehensive 13-tab trial binder PDF for courtroom use",
        icon: "📚",
        endpoint: "trial-binder",
        mime: "application/pdf",
        extension: "pdf",
    },
    {
        id: "quick-cards",
        label: "Quick Cards",
        description: "Courtroom reference cards for witnesses, evidence, and objections",
        icon: "\uD83C\uDCCF",
        endpoint: "quick-cards",
        mime: "application/pdf",
        extension: "pdf",
    },
];

export default function ExportsPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { preparations, activePrepId } = usePrep();
    const [downloading, setDownloading] = useState<string | null>(null);
    const [selectedPrepId, setSelectedPrepId] = useState<string>(activePrepId || "");

    // Keep selectedPrepId in sync with activePrepId
    const prepId = selectedPrepId || activePrepId || "";

    const handleDownload = async (format: ExportFormat) => {
        if (!prepId) {
            toast.error("Select a preparation first");
            return;
        }
        setDownloading(format.id);
        try {
            const token = await getToken();
            const res = await fetch(
                `${API_URL}/api/v1/cases/${caseId}/export/${format.endpoint}/${prepId}`,
                {
                    headers: { Authorization: `Bearer ${token}` },
                },
            );
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: "Export failed" }));
                throw new Error(err.detail || "Export failed");
            }
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `export_${format.id}.${format.extension}`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            toast.success(`${format.label} downloaded`);
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Download failed";
            toast.error(message);
        } finally {
            setDownloading(null);
        }
    };

    const handleDownloadAll = async () => {
        if (!prepId) {
            toast.error("Select a preparation first");
            return;
        }
        setDownloading("all");
        let successCount = 0;
        for (const format of EXPORT_FORMATS) {
            try {
                const token = await getToken();
                const res = await fetch(
                    `${API_URL}/api/v1/cases/${caseId}/export/${format.endpoint}/${prepId}`,
                    {
                        headers: { Authorization: `Bearer ${token}` },
                    },
                );
                if (res.ok) {
                    const blob = await res.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `export_${format.id}.${format.extension}`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    URL.revokeObjectURL(url);
                    successCount++;
                }
            } catch {
                // Skip failed downloads in batch
            }
        }
        toast.success(`Downloaded ${successCount} of ${EXPORT_FORMATS.length} exports`);
        setDownloading(null);
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-bold tracking-tight">Export Gallery</h2>
                    <p className="text-sm text-muted-foreground">
                        Download analysis reports in multiple formats
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    {preparations.length > 0 && (
                        <Select value={prepId} onValueChange={setSelectedPrepId}>
                            <SelectTrigger className="w-48 h-9 text-sm">
                                <SelectValue placeholder="Select prep" />
                            </SelectTrigger>
                            <SelectContent>
                                {preparations.map((p) => (
                                    <SelectItem key={p.id} value={p.id}>
                                        {p.name || p.type} prep
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    )}
                    <Button
                        onClick={handleDownloadAll}
                        disabled={!prepId || downloading !== null}
                        size="sm"
                    >
                        {downloading === "all" ? "Downloading..." : "Download All"}
                    </Button>
                </div>
            </div>

            {!prepId && preparations.length === 0 && (
                <Card>
                    <CardContent className="py-12 text-center">
                        <p className="text-muted-foreground">
                            No preparations found. Run an analysis first to generate exportable reports.
                        </p>
                    </CardContent>
                </Card>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {EXPORT_FORMATS.map((format) => (
                    <Card key={format.id} className="hover:border-primary/30 transition-colors">
                        <CardHeader className="pb-3">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <span className="text-2xl">{format.icon}</span>
                                    <CardTitle className="text-base">{format.label}</CardTitle>
                                </div>
                                <Badge variant="outline" className="text-xs uppercase">
                                    .{format.extension}
                                </Badge>
                            </div>
                            <CardDescription>{format.description}</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Button
                                className="w-full"
                                variant="outline"
                                onClick={() => handleDownload(format)}
                                disabled={!prepId || downloading !== null}
                            >
                                {downloading === format.id ? "Generating..." : `Download ${format.label}`}
                            </Button>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
}
