// ---- Export Dropdown Component -------------------------------------------
// Dropdown button for exporting case data (PDF, DOCX, exhibits, court docs).
"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

interface ExportDropdownProps {
    caseId: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function downloadExport(
    url: string,
    filename: string,
    getToken: () => Promise<string | null>,
) {
    try {
        const token = await getToken();
        const res = await fetch(`${API_BASE}${url}`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error(`Export failed: ${res.statusText}`);
        const blob = await res.blob();
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
        URL.revokeObjectURL(link.href);
        toast.success(`Downloaded ${filename}`);
    } catch (err) {
        toast.error("Export failed", { description: (err as Error).message });
    }
}

export function ExportDropdown({ caseId }: ExportDropdownProps) {
    const [open, setOpen] = useState(false);
    const [exporting, setExporting] = useState<string | null>(null);
    const { getToken } = useAuth();
    const ref = useRef<HTMLDivElement>(null);

    // Click outside to close
    useEffect(() => {
        function handle(e: MouseEvent) {
            if (ref.current && !ref.current.contains(e.target as Node)) {
                setOpen(false);
            }
        }
        if (open) document.addEventListener("mousedown", handle);
        return () => document.removeEventListener("mousedown", handle);
    }, [open]);

    const exportItems = [
        {
            key: "pdf",
            label: "📄 Case Report (PDF)",
            action: async () => {
                setExporting("pdf");
                await downloadExport(
                    `/api/v1/cases/${caseId}/exhibits/export/case-report?format=pdf`,
                    `case_${caseId}.pdf`,
                    getToken,
                );
                setExporting(null);
            },
        },
        {
            key: "docx",
            label: "📝 Case Report (Word)",
            action: async () => {
                setExporting("docx");
                await downloadExport(
                    `/api/v1/cases/${caseId}/exhibits/export/case-report?format=docx`,
                    `case_${caseId}.docx`,
                    getToken,
                );
                setExporting(null);
            },
        },
        {
            key: "exhibits",
            label: "📋 Exhibit List (PDF)",
            action: async () => {
                setExporting("exhibits");
                await downloadExport(
                    `/api/v1/cases/${caseId}/exhibits/export/pdf`,
                    `exhibits_${caseId}.pdf`,
                    getToken,
                );
                setExporting(null);
            },
        },
        {
            key: "motion",
            label: "⚖️ Motion Template",
            action: async () => {
                setExporting("motion");
                await downloadExport(
                    `/api/v1/cases/${caseId}/exhibits/export/court-docs?doc_type=motion`,
                    `motion_${caseId}.pdf`,
                    getToken,
                );
                setExporting(null);
            },
        },
    ];

    return (
        <div ref={ref} className="relative">
            <Button
                variant="outline"
                size="sm"
                onClick={() => setOpen(!open)}
            >
                📥 Export
            </Button>

            {open && (
                <div className="absolute right-0 top-full mt-1 w-56 bg-popover border rounded-lg shadow-xl z-50 py-1">
                    {exportItems.map((item) => (
                        <button
                            key={item.key}
                            className="w-full text-left px-3 py-2 text-sm hover:bg-accent/50 transition-colors disabled:opacity-50"
                            onClick={item.action}
                            disabled={exporting !== null}
                        >
                            {exporting === item.key ? "Exporting..." : item.label}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
