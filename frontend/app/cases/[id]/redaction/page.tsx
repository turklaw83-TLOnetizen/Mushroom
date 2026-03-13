// ---- AI Redaction Engine --------------------------------------------------
// Scans case documents for PII and privileged content. Supports regex-based
// and LLM-based detection, redaction preview, and discovery-compliant logs.
// Four views:
//   1. Category Selection  — pick PII categories + scan trigger
//   2. Scan Results        — per-file findings with count badges
//   3. Finding Details     — expanded file with category/confidence badges
//   4. Redaction Log       — privilege log table for discovery compliance
"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { routes } from "@/lib/api-routes";
import { queryKeys } from "@/lib/query-keys";
import {
    formatDate,
    formatLabel,
    CONFIDENCE_COLORS,
} from "@/lib/constants";
import { useRole } from "@/hooks/use-role";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type {
    RedactionCategory,
    RedactionFinding,
    RedactionReport,
} from "@/types/api";

// ---- Types / Constants ---------------------------------------------------

type ViewMode = "setup" | "scanning" | "results" | "history";

const REDACTION_STYLE_OPTIONS = [
    { value: "blackout", label: "Blackout", description: "Replace with [REDACTED]" },
    { value: "category", label: "Category Labels", description: "Replace with [REDACTED - Category]" },
    { value: "placeholder", label: "Placeholder", description: "Replace with XXX-XX-XXXX style" },
];

const CATEGORY_COLORS: Record<string, string> = {
    ssn: "bg-red-500/15 text-red-400 border-red-500/30",
    phone: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    email: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30",
    credit_card: "bg-orange-500/15 text-orange-400 border-orange-500/30",
    dob: "bg-purple-500/15 text-purple-400 border-purple-500/30",
    address: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    medical: "bg-pink-500/15 text-pink-400 border-pink-500/30",
    financial: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    privilege: "bg-indigo-500/15 text-indigo-400 border-indigo-500/30",
    work_product: "bg-violet-500/15 text-violet-400 border-violet-500/30",
};

// ---- Scan result shape from API -----------------------------------------

interface ScanResult {
    status: string;
    files_scanned?: number;
    total_findings?: number;
    summary?: Record<string, number>;
    files?: Record<string, {
        findings_count: number;
        summary: Record<string, number>;
        findings: RedactionFinding[];
    }>;
    // Single-file scan
    filename?: string;
    findings_count?: number;
    findings?: RedactionFinding[];
    redaction_log?: {
        document: string;
        total_redactions: number;
        entries: { id: number; category: string; basis: string; description: string }[];
    };
}

interface ApplyResult {
    status: string;
    filename: string;
    original_length: number;
    redacted_length: number;
    findings_count: number;
    summary: Record<string, number>;
    redacted_text: string;
    redaction_log: {
        document: string;
        total_redactions: number;
        entries: { id: number; category: string; category_label?: string; basis: string; description: string }[];
    };
}

// ---- Main Page -----------------------------------------------------------

export default function RedactionPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { canEdit } = useRole();
    const queryClient = useQueryClient();

    const [view, setView] = useState<ViewMode>("setup");
    const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());
    const [expandedFile, setExpandedFile] = useState<string | null>(null);
    const [redactionStyle, setRedactionStyle] = useState("category");
    const [scanResult, setScanResult] = useState<ScanResult | null>(null);
    const [applyResult, setApplyResult] = useState<ApplyResult | null>(null);
    const [showRedactionLog, setShowRedactionLog] = useState(false);
    const [categoriesInitialized, setCategoriesInitialized] = useState(false);

    // ---- Data Fetching --------------------------------------------------

    const categoriesQuery = useQuery({
        queryKey: [...queryKeys.redaction.categories(caseId)],
        queryFn: () =>
            api.get<{ categories: RedactionCategory[] }>(
                routes.redaction.categories(caseId),
                { getToken },
            ),
    });

    const reportsQuery = useQuery({
        queryKey: [...queryKeys.redaction.reports(caseId)],
        queryFn: () =>
            api.get<{ reports: RedactionReport[] }>(
                routes.redaction.reports(caseId),
                { getToken },
            ),
    });

    // Initialize categories from API defaults
    const categories = categoriesQuery.data?.categories ?? [];
    if (categories.length > 0 && !categoriesInitialized) {
        const defaults = new Set<string>();
        for (const cat of categories) {
            if (cat.default) defaults.add(cat.key);
        }
        setSelectedCategories(defaults);
        setCategoriesInitialized(true);
    }

    const reports = reportsQuery.data?.reports ?? [];

    // ---- Mutations ------------------------------------------------------

    const scanAll = useMutation<ScanResult, Error>({
        mutationFn: () =>
            api.post<ScanResult>(
                routes.redaction.scan(caseId),
                {
                    categories: Array.from(selectedCategories),
                    use_llm: true,
                },
                { getToken },
            ),
        onMutate: () => {
            setView("scanning");
        },
        onSuccess: (data) => {
            setScanResult(data);
            toast.success("Scan complete", {
                description: `Found ${data.total_findings ?? 0} findings across ${data.files_scanned ?? 0} files`,
            });
            queryClient.invalidateQueries({
                queryKey: [...queryKeys.redaction.reports(caseId)],
            });
            setView("results");
        },
        onError: (err) => {
            toast.error("PII scan failed", { description: err.message });
            setView("setup");
        },
    });

    const applyRedaction = useMutation<ApplyResult, Error, string>({
        mutationFn: (filename) =>
            api.post<ApplyResult>(
                routes.redaction.apply(caseId),
                {
                    filename,
                    categories: Array.from(selectedCategories),
                    redaction_style: redactionStyle,
                    use_llm: true,
                },
                { getToken },
            ),
        onSuccess: (data) => {
            setApplyResult(data);
            toast.success(`Redacted ${data.findings_count} items in ${data.filename}`);
            queryClient.invalidateQueries({
                queryKey: [...queryKeys.redaction.reports(caseId)],
            });
        },
        onError: (err) => {
            toast.error("Redaction failed", { description: err.message });
        },
    });

    // ---- Helpers --------------------------------------------------------

    const toggleCategory = (key: string) => {
        setSelectedCategories((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
        });
    };

    const selectAll = () => {
        setSelectedCategories(new Set(categories.map((c) => c.key)));
    };

    const deselectAll = () => {
        setSelectedCategories(new Set());
    };

    const maskText = (text: string): string => {
        if (!text) return "";
        if (text.length <= 4) return "****";
        return text.slice(0, 2) + "*".repeat(Math.min(text.length - 4, 20)) + text.slice(-2);
    };

    const fileEntries = useMemo(() => {
        if (!scanResult?.files) return [];
        return Object.entries(scanResult.files)
            .map(([name, data]) => ({ name, ...data }))
            .sort((a, b) => b.findings_count - a.findings_count);
    }, [scanResult]);

    // ---- Loading --------------------------------------------------------

    if (categoriesQuery.isLoading) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-8 w-48" />
                <Skeleton className="h-64 w-full" />
            </div>
        );
    }

    // ---- Scanning View --------------------------------------------------

    if (view === "scanning") {
        return (
            <div className="space-y-6">
                <h2 className="text-xl font-bold tracking-tight">
                    Redaction Engine
                </h2>
                <Card>
                    <CardContent className="py-12 text-center space-y-4">
                        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-400" />
                        <h3 className="text-lg font-semibold">
                            Scanning Documents for PII
                        </h3>
                        <p className="text-sm text-muted-foreground max-w-md mx-auto">
                            Running regex and AI-based detection across all case documents.
                            This may take a few minutes for large document sets.
                        </p>
                        <div className="flex justify-center flex-wrap gap-2 pt-4">
                            {Array.from(selectedCategories).map((cat) => {
                                const info = categories.find((c) => c.key === cat);
                                return (
                                    <Badge
                                        key={cat}
                                        variant="outline"
                                        className={CATEGORY_COLORS[cat] ?? "bg-zinc-500/15 text-zinc-400 border-zinc-500/30"}
                                    >
                                        {info?.label ?? formatLabel(cat)}
                                    </Badge>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            </div>
        );
    }

    // ---- Apply Result Overlay -------------------------------------------

    if (applyResult) {
        return (
            <div className="space-y-6">
                <div className="flex items-center justify-between">
                    <h2 className="text-xl font-bold tracking-tight">
                        Redaction Preview &mdash; {applyResult.filename}
                    </h2>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setApplyResult(null)}
                    >
                        Back to Scan Results
                    </Button>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-4">
                    <Card>
                        <CardContent className="p-4 text-center">
                            <p className="text-2xl font-bold text-red-400">
                                {applyResult.findings_count}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">Redactions Applied</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="p-4 text-center">
                            <p className="text-2xl font-bold text-blue-400">
                                {applyResult.original_length.toLocaleString()}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">Original Characters</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="p-4 text-center">
                            <p className="text-2xl font-bold text-green-400">
                                {applyResult.redacted_length.toLocaleString()}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">Redacted Characters</p>
                        </CardContent>
                    </Card>
                </div>

                {/* Redacted Text Preview */}
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Redacted Text Preview</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <pre className="text-xs font-mono whitespace-pre-wrap bg-muted/50 rounded-md p-4 max-h-96 overflow-y-auto">
                            {applyResult.redacted_text.slice(0, 5000)}
                            {applyResult.redacted_text.length > 5000 && (
                                <span className="text-muted-foreground">
                                    {"\n\n"}... ({(applyResult.redacted_text.length - 5000).toLocaleString()} more characters)
                                </span>
                            )}
                        </pre>
                    </CardContent>
                </Card>

                {/* Redaction Log */}
                {applyResult.redaction_log && (
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm">
                                Redaction Log ({applyResult.redaction_log.total_redactions} entries)
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="overflow-x-auto">
                                <table className="w-full text-xs">
                                    <thead>
                                        <tr className="border-b border-border text-left text-muted-foreground">
                                            <th className="pb-2 pr-3">#</th>
                                            <th className="pb-2 pr-3">Category</th>
                                            <th className="pb-2 pr-3">Legal Basis</th>
                                            <th className="pb-2">Description</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border">
                                        {applyResult.redaction_log.entries.map((entry) => (
                                            <tr key={entry.id}>
                                                <td className="py-2 pr-3 text-muted-foreground">
                                                    {entry.id}
                                                </td>
                                                <td className="py-2 pr-3">
                                                    <Badge
                                                        variant="outline"
                                                        className={
                                                            CATEGORY_COLORS[entry.category] ??
                                                            "bg-zinc-500/15 text-zinc-400 border-zinc-500/30"
                                                        }
                                                    >
                                                        {formatLabel(entry.category)}
                                                    </Badge>
                                                </td>
                                                <td className="py-2 pr-3">{entry.basis}</td>
                                                <td className="py-2">{entry.description}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </CardContent>
                    </Card>
                )}
            </div>
        );
    }

    // ---- Results View ---------------------------------------------------

    if (view === "results" && scanResult) {
        return (
            <div className="space-y-6">
                <div className="flex items-center justify-between">
                    <h2 className="text-xl font-bold tracking-tight">
                        Scan Results
                    </h2>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                                setScanResult(null);
                                setView("setup");
                            }}
                        >
                            New Scan
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setView("history")}
                        >
                            History
                        </Button>
                    </div>
                </div>

                {/* Summary Stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card>
                        <CardContent className="p-4 text-center">
                            <p className="text-2xl font-bold text-red-400">
                                {scanResult.total_findings ?? 0}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">Total Findings</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="p-4 text-center">
                            <p className="text-2xl font-bold text-blue-400">
                                {scanResult.files_scanned ?? 0}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">Files Scanned</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="p-4 text-center">
                            <p className="text-2xl font-bold text-purple-400">
                                {Object.keys(scanResult.summary ?? {}).length}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">Categories Found</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="p-4 text-center">
                            <p className="text-2xl font-bold text-amber-400">
                                {selectedCategories.size}
                            </p>
                            <p className="text-xs text-muted-foreground mt-1">Categories Scanned</p>
                        </CardContent>
                    </Card>
                </div>

                {/* Category breakdown */}
                {scanResult.summary && Object.keys(scanResult.summary).length > 0 && (
                    <div className="flex flex-wrap gap-2">
                        {Object.entries(scanResult.summary)
                            .sort(([, a], [, b]) => b - a)
                            .map(([cat, count]) => (
                                <Badge
                                    key={cat}
                                    variant="outline"
                                    className={CATEGORY_COLORS[cat] ?? "bg-zinc-500/15 text-zinc-400 border-zinc-500/30"}
                                >
                                    {formatLabel(cat)}: {count}
                                </Badge>
                            ))}
                    </div>
                )}

                {/* Redaction Style Selector */}
                <Card>
                    <CardContent className="p-4">
                        <p className="text-xs font-medium text-muted-foreground mb-2">
                            Redaction Style
                        </p>
                        <div className="flex gap-3">
                            {REDACTION_STYLE_OPTIONS.map((opt) => (
                                <button
                                    key={opt.value}
                                    onClick={() => setRedactionStyle(opt.value)}
                                    className={`flex-1 rounded-md border p-3 text-left text-xs transition-colors ${
                                        redactionStyle === opt.value
                                            ? "border-indigo-500 bg-indigo-500/5"
                                            : "border-border hover:border-muted-foreground/50"
                                    }`}
                                >
                                    <p className="font-medium">{opt.label}</p>
                                    <p className="text-muted-foreground mt-0.5">
                                        {opt.description}
                                    </p>
                                </button>
                            ))}
                        </div>
                    </CardContent>
                </Card>

                {/* Per-File Results */}
                <div className="space-y-3">
                    {fileEntries.length === 0 ? (
                        <Card>
                            <CardContent className="py-8 text-center text-sm text-muted-foreground">
                                No PII findings detected in any files.
                            </CardContent>
                        </Card>
                    ) : (
                        fileEntries.map((file) => {
                            const isExpanded = expandedFile === file.name;
                            return (
                                <Card key={file.name} className="overflow-hidden">
                                    <CardContent className="p-0">
                                        {/* File Header */}
                                        <button
                                            onClick={() =>
                                                setExpandedFile(isExpanded ? null : file.name)
                                            }
                                            className="w-full flex items-center justify-between p-4 text-left hover:bg-muted/30 transition-colors"
                                        >
                                            <div className="flex items-center gap-3">
                                                <span className="text-sm font-medium">
                                                    {file.name}
                                                </span>
                                                <div className="flex gap-1">
                                                    {Object.entries(file.summary ?? {}).map(([cat, n]) => (
                                                        <Badge
                                                            key={cat}
                                                            variant="outline"
                                                            className={`text-[10px] ${CATEGORY_COLORS[cat] ?? ""}`}
                                                        >
                                                            {formatLabel(cat)}: {n}
                                                        </Badge>
                                                    ))}
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <Badge
                                                    variant={file.findings_count > 0 ? "destructive" : "secondary"}
                                                    className="text-[10px]"
                                                >
                                                    {file.findings_count} finding{file.findings_count !== 1 ? "s" : ""}
                                                </Badge>
                                                <span className="text-muted-foreground text-xs">
                                                    {isExpanded ? "\u25B2" : "\u25BC"}
                                                </span>
                                            </div>
                                        </button>

                                        {/* Expanded Findings */}
                                        {isExpanded && (
                                            <div className="border-t border-border px-4 pb-4">
                                                {/* Apply button */}
                                                {canEdit && file.findings_count > 0 && (
                                                    <div className="py-3 border-b border-border mb-3">
                                                        <Button
                                                            size="sm"
                                                            onClick={() =>
                                                                applyRedaction.mutate(file.name)
                                                            }
                                                            disabled={applyRedaction.isPending}
                                                        >
                                                            {applyRedaction.isPending
                                                                ? "Applying..."
                                                                : `Apply Redactions (${redactionStyle})`}
                                                        </Button>
                                                    </div>
                                                )}

                                                {/* Finding items */}
                                                <div className="space-y-2">
                                                    {(file.findings ?? []).map((f, idx) => (
                                                        <div
                                                            key={idx}
                                                            className="rounded-md border border-border p-3 text-xs space-y-1.5"
                                                        >
                                                            <div className="flex items-center gap-2 flex-wrap">
                                                                <Badge
                                                                    variant="outline"
                                                                    className={
                                                                        CATEGORY_COLORS[f.category] ??
                                                                        "bg-zinc-500/15 text-zinc-400 border-zinc-500/30"
                                                                    }
                                                                >
                                                                    {formatLabel(f.category)}
                                                                </Badge>
                                                                <Badge
                                                                    variant="outline"
                                                                    className={
                                                                        CONFIDENCE_COLORS[f.confidence] ??
                                                                        "bg-zinc-500/15 text-zinc-400 border-zinc-500/30"
                                                                    }
                                                                >
                                                                    {f.confidence} confidence
                                                                </Badge>
                                                                <Badge variant="secondary">
                                                                    {f.source}
                                                                </Badge>
                                                            </div>
                                                            <p className="font-mono bg-muted/50 rounded px-2 py-1">
                                                                {maskText(f.text)}
                                                            </p>
                                                            {f.context && (
                                                                <p className="text-muted-foreground">
                                                                    ...{f.context.slice(0, 100)}...
                                                                </p>
                                                            )}
                                                        </div>
                                                    ))}
                                                    {(file.findings ?? []).length === 0 && (
                                                        <p className="text-xs text-muted-foreground py-2">
                                                            No detailed findings available.
                                                        </p>
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            );
                        })
                    )}
                </div>
            </div>
        );
    }

    // ---- History View ---------------------------------------------------

    if (view === "history") {
        return (
            <div className="space-y-6">
                <div className="flex items-center justify-between">
                    <h2 className="text-xl font-bold tracking-tight">
                        Scan History
                    </h2>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setView("setup")}
                    >
                        New Scan
                    </Button>
                </div>

                {reports.length === 0 ? (
                    <Card>
                        <CardContent className="py-8 text-center text-sm text-muted-foreground">
                            No previous scan reports found.
                        </CardContent>
                    </Card>
                ) : (
                    <div className="space-y-3">
                        {reports.map((report) => (
                            <Card key={report.id}>
                                <CardContent className="p-4">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-sm font-medium">
                                                {report.filename || report.scan_type || `Batch scan`}
                                            </p>
                                            <p className="text-xs text-muted-foreground mt-0.5">
                                                {formatDate(report.saved_at)}
                                            </p>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Badge variant="outline">
                                                {report.total_redactions ?? report.total_findings ?? 0} findings
                                            </Badge>
                                            {report.by_category && (
                                                <div className="flex gap-1">
                                                    {Object.entries(report.by_category).slice(0, 3).map(([cat, n]) => (
                                                        <Badge
                                                            key={cat}
                                                            variant="outline"
                                                            className={`text-[10px] ${CATEGORY_COLORS[cat] ?? ""}`}
                                                        >
                                                            {formatLabel(cat)}: {n}
                                                        </Badge>
                                                    ))}
                                                </div>
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

    // ---- Setup View (Category Selection) --------------------------------

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold tracking-tight">
                    Redaction Engine
                </h2>
                {reports.length > 0 && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setView("history")}
                    >
                        Scan History ({reports.length})
                    </Button>
                )}
            </div>

            <Card>
                <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-sm">
                            PII Detection Categories
                        </CardTitle>
                        <div className="flex gap-2">
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 text-xs px-2"
                                onClick={selectAll}
                            >
                                Select All
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 text-xs px-2"
                                onClick={deselectAll}
                            >
                                Deselect All
                            </Button>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {categories.map((cat) => {
                            const isSelected = selectedCategories.has(cat.key);
                            return (
                                <button
                                    key={cat.key}
                                    onClick={() => toggleCategory(cat.key)}
                                    className={`flex items-center gap-3 rounded-md border p-3 text-left text-sm transition-colors ${
                                        isSelected
                                            ? "border-indigo-500 bg-indigo-500/5"
                                            : "border-border hover:border-muted-foreground/50"
                                    }`}
                                >
                                    <div
                                        className={`h-4 w-4 rounded border flex items-center justify-center shrink-0 ${
                                            isSelected
                                                ? "border-indigo-500 bg-indigo-500"
                                                : "border-muted-foreground/50"
                                        }`}
                                    >
                                        {isSelected && (
                                            <span className="text-white text-[10px]">&#x2713;</span>
                                        )}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <span className="font-medium">{cat.label}</span>
                                            {cat.requires_llm && (
                                                <Badge variant="secondary" className="text-[10px]">
                                                    AI
                                                </Badge>
                                            )}
                                            {cat.has_pattern && (
                                                <Badge variant="secondary" className="text-[10px]">
                                                    Regex
                                                </Badge>
                                            )}
                                        </div>
                                    </div>
                                    <Badge
                                        variant="outline"
                                        className={`text-[10px] shrink-0 ${CATEGORY_COLORS[cat.key] ?? ""}`}
                                    >
                                        {cat.key}
                                    </Badge>
                                </button>
                            );
                        })}
                    </div>
                </CardContent>
            </Card>

            {/* Scan button */}
            <div className="flex items-center gap-3">
                {canEdit && (
                    <Button
                        onClick={() => scanAll.mutate()}
                        disabled={scanAll.isPending || selectedCategories.size === 0}
                        className="min-w-[160px]"
                    >
                        {scanAll.isPending
                            ? "Starting..."
                            : `Scan All Files (${selectedCategories.size} categor${selectedCategories.size === 1 ? "y" : "ies"})`}
                    </Button>
                )}
                {selectedCategories.size === 0 && (
                    <span className="text-xs text-muted-foreground">
                        Select at least one category to scan.
                    </span>
                )}
            </div>
        </div>
    );
}
