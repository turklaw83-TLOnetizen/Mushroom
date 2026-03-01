// ---- Export Panel --------------------------------------------------------
// Export controls for case overview: PDF, Word, IRAC brief, trial binder.
"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { usePrep } from "@/hooks/use-prep";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ExportOption {
    label: string;
    endpoint: string;
    icon: string;
    description: string;
}

const exports: ExportOption[] = [
    { label: "PDF Report", endpoint: "pdf", icon: "📕", description: "Full analysis report" },
    { label: "Word Report", endpoint: "word", icon: "📘", description: "Editable analysis report" },
    { label: "IRAC Brief", endpoint: "brief", icon: "📗", description: "Issue-Rule-Application-Conclusion" },
    { label: "Trial Binder", endpoint: "trial-binder", icon: "📙", description: "Complete 13-tab trial binder" },
];

export function ExportPanel({ caseId }: { caseId: string }) {
    const { getToken } = useAuth();
    const { activePrepId } = usePrep();
    const [downloading, setDownloading] = useState<string | null>(null);

    const handleExport = async (exp: ExportOption) => {
        if (!activePrepId) {
            toast.error("No preparation selected. Create a prep first.");
            return;
        }

        setDownloading(exp.endpoint);
        try {
            const token = await getToken();
            const response = await fetch(
                `${API_BASE}/api/cases/${caseId}/export/${exp.endpoint}/${activePrepId}`,
                {
                    headers: token ? { Authorization: `Bearer ${token}` } : {},
                },
            );

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || `Export failed (${response.status})`);
            }

            // Download the file
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;

            // Extract filename from Content-Disposition header
            const disposition = response.headers.get("Content-Disposition");
            const filename = disposition?.match(/filename="(.+)"/)?.[1] || `export.${exp.endpoint === "pdf" || exp.endpoint === "trial-binder" ? "pdf" : "docx"}`;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);

            toast.success(`${exp.label} downloaded`);
        } catch (error) {
            toast.error(`${exp.label} failed`, {
                description: error instanceof Error ? error.message : "Unknown error",
            });
        } finally {
            setDownloading(null);
        }
    };

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                    📤 Export Reports
                    {!activePrepId && (
                        <Badge variant="outline" className="text-amber-400 border-amber-500/30 text-xs">
                            No prep selected
                        </Badge>
                    )}
                </CardTitle>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {exports.map((exp) => (
                        <Button
                            key={exp.endpoint}
                            variant="outline"
                            className="h-auto py-3 px-4 justify-start gap-3"
                            disabled={downloading !== null || !activePrepId}
                            onClick={() => handleExport(exp)}
                        >
                            <span className="text-xl">{exp.icon}</span>
                            <div className="text-left">
                                <p className="text-sm font-medium">
                                    {downloading === exp.endpoint ? "Generating..." : exp.label}
                                </p>
                                <p className="text-[11px] text-muted-foreground font-normal">
                                    {exp.description}
                                </p>
                            </div>
                        </Button>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}
