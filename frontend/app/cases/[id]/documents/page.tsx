// ---- Major Document Drafter Page -----------------------------------------
// Full-featured document drafting with outline generation, section drafting,
// quality scoring, and AI review. Replaces the basic drafts+research view.
"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { usePrep } from "@/hooks/use-prep";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

// ---- Types --------------------------------------------------------------

interface Draft {
    id: string;
    title: string;
    type: string;
    court_type?: string;
    content: string;
    created_at: string;
    last_updated: string;
    quality_score?: number;
    quality_grade?: string;
    outline?: OutlineSection[];
    sections?: DraftSection[];
    citation_library?: Citation[];
    review_results?: ReviewResult;
    [key: string]: unknown;
}

interface OutlineSection {
    section_num: string;
    title: string;
    description: string;
    estimated_pages?: number;
}

interface DraftSection {
    section_num: string;
    title: string;
    content: string;
    citations_used?: Citation[];
}

interface Citation {
    case_name: string;
    citation: string;
    holding: string;
    relevance?: string;
    source?: string;
}

interface ReviewResult {
    overall_score: number;
    grade: string;
    issues: ReviewIssue[];
    strengths: string[];
    suggestions: string[];
}

interface ReviewIssue {
    category: string;
    severity: string;
    section: string;
    description: string;
    fix: string;
}

interface QualityBreakdown {
    score: number;
    grade: string;
    breakdown: Record<string, boolean>;
}

interface ResearchItem {
    topic: string;
    summary: string;
    source: string;
    citations: string[];
}

// ---- Constants ----------------------------------------------------------

const DOC_TYPE_OPTIONS = [
    { value: "motion", label: "Motion" },
    { value: "brief", label: "Brief" },
    { value: "memorandum", label: "Memorandum" },
    { value: "petition", label: "Petition" },
    { value: "response", label: "Response" },
    { value: "reply", label: "Reply" },
];

const COURT_TYPE_OPTIONS = [
    { value: "federal", label: "Federal" },
    { value: "state", label: "State" },
    { value: "appellate", label: "Appellate" },
];

const TYPE_COLORS: Record<string, string> = {
    motion: "text-amber-400 border-amber-500/30",
    brief: "text-blue-400 border-blue-500/30",
    memorandum: "text-violet-400 border-violet-500/30",
    memo: "text-violet-400 border-violet-500/30",
    petition: "text-emerald-400 border-emerald-500/30",
    response: "text-cyan-400 border-cyan-500/30",
    reply: "text-rose-400 border-rose-500/30",
    letter: "text-green-400 border-green-500/30",
    outline: "text-cyan-400 border-cyan-500/30",
    other: "text-zinc-400 border-zinc-500/30",
};

// ---- Helpers ------------------------------------------------------------

function scoreColor(score: number): string {
    if (score >= 80) return "text-emerald-400 border-emerald-500/30 bg-emerald-500/10";
    if (score >= 50) return "text-amber-400 border-amber-500/30 bg-amber-500/10";
    return "text-red-400 border-red-500/30 bg-red-500/10";
}

function gradeColor(grade: string): string {
    if (grade.startsWith("A")) return "text-emerald-400 border-emerald-500/30";
    if (grade === "B") return "text-blue-400 border-blue-500/30";
    if (grade === "C") return "text-amber-400 border-amber-500/30";
    return "text-red-400 border-red-500/30";
}

function formatTimestamp(ts: string): string {
    try {
        const d = new Date(ts);
        if (isNaN(d.getTime())) return ts;
        return d.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
        });
    } catch {
        return ts;
    }
}

function previewContent(content: string, maxLen = 200): string {
    if (!content) return "Empty draft";
    if (content.length <= maxLen) return content;
    return content.slice(0, maxLen) + "...";
}

function severityColor(severity: string): string {
    switch (severity) {
        case "high": return "text-red-400 border-red-500/30 bg-red-500/10";
        case "medium": return "text-amber-400 border-amber-500/30 bg-amber-500/10";
        default: return "text-blue-400 border-blue-500/30 bg-blue-500/10";
    }
}

// ---- Loading Spinner ----------------------------------------------------

function LoadingSpinner({ className = "h-4 w-4" }: { className?: string }) {
    return (
        <svg className={`animate-spin ${className}`} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
    );
}

// ---- Quality Score Bar --------------------------------------------------

function QualityBar({ label, passed }: { label: string; passed: boolean }) {
    return (
        <div className="flex items-center gap-2">
            <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                <div
                    className={`h-full rounded-full transition-all ${passed ? "bg-emerald-500 w-full" : "bg-red-500/30 w-0"}`}
                />
            </div>
            <span className={`text-xs whitespace-nowrap ${passed ? "text-emerald-400" : "text-muted-foreground"}`}>
                {passed ? "\u2713" : "\u2717"} {label}
            </span>
        </div>
    );
}

// ---- Quality Panel Component --------------------------------------------

function QualityPanel({ caseId, draftId }: { caseId: string; draftId: string }) {
    const { getToken } = useAuth();

    const qualityQuery = useQuery({
        queryKey: ["draft-quality", caseId, draftId],
        queryFn: () =>
            api.get<QualityBreakdown>(`/documents/drafts/${caseId}/${draftId}/quality`, { getToken }),
    });

    if (qualityQuery.isLoading) {
        return (
            <div className="space-y-2 p-4">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-2 w-full" />
                <Skeleton className="h-2 w-full" />
                <Skeleton className="h-2 w-3/4" />
            </div>
        );
    }

    if (qualityQuery.error || !qualityQuery.data) {
        return (
            <div className="p-4 text-xs text-muted-foreground">
                Quality scoring unavailable
            </div>
        );
    }

    const { score, grade, breakdown } = qualityQuery.data;

    return (
        <div className="space-y-3 p-4 border-t border-border/50">
            <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Quality Score</span>
                <div className="flex items-center gap-2">
                    <Badge variant="outline" className={scoreColor(score)}>
                        {score}/100
                    </Badge>
                    <Badge variant="outline" className={gradeColor(grade)}>
                        {grade}
                    </Badge>
                </div>
            </div>
            <div className="space-y-1.5">
                {Object.entries(breakdown).map(([label, passed]) => (
                    <QualityBar key={label} label={label} passed={passed} />
                ))}
            </div>
        </div>
    );
}

// ---- New Draft Wizard Dialog --------------------------------------------

function NewDraftWizard({
    open,
    onOpenChange,
    caseId,
    prepId,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    caseId: string;
    prepId: string | null;
}) {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    const [step, setStep] = useState<"config" | "outline" | "drafting">("config");
    const [docType, setDocType] = useState("motion");
    const [title, setTitle] = useState("");
    const [courtType, setCourtType] = useState("state");
    const [customInstructions, setCustomInstructions] = useState("");
    const [outline, setOutline] = useState<OutlineSection[]>([]);
    const [documentTitle, setDocumentTitle] = useState("");
    const [isGeneratingOutline, setIsGeneratingOutline] = useState(false);
    const [isDraftingSections, setIsDraftingSections] = useState(false);
    const [draftingProgress, setDraftingProgress] = useState("");

    const resetWizard = () => {
        setStep("config");
        setDocType("motion");
        setTitle("");
        setCourtType("state");
        setCustomInstructions("");
        setOutline([]);
        setDocumentTitle("");
        setIsGeneratingOutline(false);
        setIsDraftingSections(false);
        setDraftingProgress("");
    };

    const handleClose = (open: boolean) => {
        if (!open) resetWizard();
        onOpenChange(open);
    };

    const handleGenerateOutline = async () => {
        if (!prepId) {
            toast.error("Select a preparation first");
            return;
        }
        setIsGeneratingOutline(true);
        try {
            const result = await api.post<{ outline: OutlineSection[]; document_title: string }>(
                `/documents/outline/${caseId}/${prepId}`,
                {
                    doc_type: docType,
                    doc_subtype: docType,
                    court_type: courtType,
                    custom_instructions: customInstructions,
                },
                { getToken },
            );
            setOutline(result.outline || []);
            setDocumentTitle(result.document_title || title || `${docType} Draft`);
            if (!title) setTitle(result.document_title || `${docType} Draft`);
            setStep("outline");
            toast.success("Outline generated");
        } catch (err) {
            toast.error("Failed to generate outline", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        } finally {
            setIsGeneratingOutline(false);
        }
    };

    const handleDraftSections = async () => {
        if (!prepId) return;
        setIsDraftingSections(true);
        const sections: DraftSection[] = [];

        try {
            for (let i = 0; i < outline.length; i++) {
                const sec = outline[i];
                setDraftingProgress(`Drafting section ${i + 1} of ${outline.length}: ${sec.title}`);

                const result = await api.post<{ content: string; citations_used: Citation[] }>(
                    `/documents/draft-section/${caseId}/${prepId}`,
                    {
                        section_num: sec.section_num,
                        section_title: sec.title,
                        section_description: sec.description,
                        outline,
                        previous_sections: sections,
                        citation_library: [],
                        doc_type: docType,
                    },
                    { getToken },
                );

                sections.push({
                    section_num: sec.section_num,
                    title: sec.title,
                    content: result.content || "",
                    citations_used: result.citations_used || [],
                });
            }

            // Assemble full content
            const fullContent = sections
                .map((s) => `## ${s.section_num}. ${s.title}\n\n${s.content}`)
                .join("\n\n---\n\n");

            // Save draft
            await api.post(
                `/documents/drafts/${caseId}`,
                {
                    title: title || documentTitle,
                    type: docType,
                    court_type: courtType,
                    content: fullContent,
                },
                { getToken },
            );

            queryClient.invalidateQueries({ queryKey: ["documents", caseId] });
            toast.success("Draft created successfully");
            handleClose(false);
        } catch (err) {
            toast.error("Failed to draft sections", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        } finally {
            setIsDraftingSections(false);
            setDraftingProgress("");
        }
    };

    const handleSaveOutlineOnly = async () => {
        // Save just the outline as a draft
        const outlineContent = outline
            .map((s) => `${s.section_num}. ${s.title}\n   ${s.description}${s.estimated_pages ? ` (~${s.estimated_pages} pages)` : ""}`)
            .join("\n\n");

        try {
            await api.post(
                `/documents/drafts/${caseId}`,
                {
                    title: title || documentTitle || "Document Outline",
                    type: "outline",
                    court_type: courtType,
                    content: outlineContent,
                },
                { getToken },
            );
            queryClient.invalidateQueries({ queryKey: ["documents", caseId] });
            toast.success("Outline saved as draft");
            handleClose(false);
        } catch (err) {
            toast.error("Failed to save outline");
        }
    };

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>
                        {step === "config" && "New Document Draft"}
                        {step === "outline" && "Review Outline"}
                        {step === "drafting" && "Drafting Sections"}
                    </DialogTitle>
                    <DialogDescription>
                        {step === "config" && "Configure your document, then generate an AI outline."}
                        {step === "outline" && "Review and approve the outline before drafting sections."}
                        {step === "drafting" && "AI is drafting each section. This may take a few minutes."}
                    </DialogDescription>
                </DialogHeader>

                {step === "config" && (
                    <div className="space-y-4">
                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">Document Type <span className="text-destructive">*</span></label>
                            <select
                                value={docType}
                                onChange={(e) => setDocType(e.target.value)}
                                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            >
                                {DOC_TYPE_OPTIONS.map((opt) => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                            </select>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">Title</label>
                            <Input
                                value={title}
                                onChange={(e) => setTitle(e.target.value)}
                                placeholder="e.g. Motion to Suppress Evidence"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">Court Type</label>
                            <select
                                value={courtType}
                                onChange={(e) => setCourtType(e.target.value)}
                                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            >
                                {COURT_TYPE_OPTIONS.map((opt) => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                            </select>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">Custom Instructions (optional)</label>
                            <textarea
                                value={customInstructions}
                                onChange={(e) => setCustomInstructions(e.target.value)}
                                placeholder="Any specific instructions for the AI drafter..."
                                rows={3}
                                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
                            />
                        </div>
                    </div>
                )}

                {step === "outline" && (
                    <div className="space-y-3">
                        {documentTitle && (
                            <p className="text-sm font-medium text-muted-foreground">{documentTitle}</p>
                        )}
                        <div className="space-y-2 max-h-[50vh] overflow-y-auto">
                            {outline.map((sec, i) => (
                                <Card key={i} className="bg-muted/30">
                                    <CardContent className="py-3">
                                        <div className="flex items-start justify-between gap-2">
                                            <div>
                                                <p className="text-sm font-medium">
                                                    {sec.section_num}. {sec.title}
                                                </p>
                                                <p className="text-xs text-muted-foreground mt-1">
                                                    {sec.description}
                                                </p>
                                            </div>
                                            {sec.estimated_pages && (
                                                <Badge variant="secondary" className="text-[10px] shrink-0">
                                                    ~{sec.estimated_pages}p
                                                </Badge>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </div>
                )}

                {step === "drafting" && (
                    <div className="flex flex-col items-center justify-center py-8 space-y-4">
                        <LoadingSpinner className="h-8 w-8" />
                        <p className="text-sm text-muted-foreground text-center">
                            {draftingProgress || "Preparing to draft..."}
                        </p>
                    </div>
                )}

                <DialogFooter>
                    {step === "config" && (
                        <>
                            <Button variant="outline" onClick={() => handleClose(false)}>
                                Cancel
                            </Button>
                            <Button
                                onClick={handleGenerateOutline}
                                disabled={isGeneratingOutline || !prepId}
                            >
                                {isGeneratingOutline ? (
                                    <><LoadingSpinner className="h-3 w-3 mr-1.5" /> Generating...</>
                                ) : (
                                    "Generate Outline"
                                )}
                            </Button>
                        </>
                    )}

                    {step === "outline" && (
                        <>
                            <Button variant="outline" onClick={() => setStep("config")}>
                                Back
                            </Button>
                            <Button variant="secondary" onClick={handleSaveOutlineOnly}>
                                Save Outline Only
                            </Button>
                            <Button
                                onClick={handleDraftSections}
                                disabled={isDraftingSections}
                            >
                                {isDraftingSections ? (
                                    <><LoadingSpinner className="h-3 w-3 mr-1.5" /> Drafting...</>
                                ) : (
                                    "Draft All Sections"
                                )}
                            </Button>
                        </>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

// ---- Draft Detail View --------------------------------------------------

function DraftDetailView({
    draft,
    caseId,
    prepId,
    onClose,
    onDelete,
}: {
    draft: Draft;
    caseId: string;
    prepId: string | null;
    onClose: () => void;
    onDelete: () => void;
}) {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const { canEdit, canDelete } = useRole();
    const [isReviewing, setIsReviewing] = useState(false);
    const [reviewResult, setReviewResult] = useState<ReviewResult | null>(
        draft.review_results ?? null
    );
    const [showFullContent, setShowFullContent] = useState(false);

    const handleReview = async () => {
        if (!prepId) {
            toast.error("Select a preparation first");
            return;
        }
        setIsReviewing(true);
        try {
            const result = await api.post<ReviewResult>(
                `/documents/review/${caseId}/${prepId}/${draft.id}`,
                {},
                { getToken },
            );
            setReviewResult(result);
            toast.success("Review completed");
        } catch (err) {
            toast.error("Review failed", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        } finally {
            setIsReviewing(false);
        }
    };

    const handleExportWord = () => {
        if (!prepId) {
            toast.error("Select a preparation first");
            return;
        }
        const url = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/cases/${caseId}/export/word/${prepId}`;
        window.open(url, "_blank");
    };

    return (
        <Dialog open onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        {draft.title}
                        <Badge variant="outline" className={`text-xs ${TYPE_COLORS[draft.type] || TYPE_COLORS.other}`}>
                            {draft.type}
                        </Badge>
                        {draft.court_type && (
                            <Badge variant="secondary" className="text-[10px]">
                                {draft.court_type}
                            </Badge>
                        )}
                    </DialogTitle>
                    <DialogDescription>
                        Created {formatTimestamp(draft.created_at || draft.last_updated)}
                        {draft.content && ` \u00B7 ${draft.content.length.toLocaleString()} characters`}
                    </DialogDescription>
                </DialogHeader>

                {/* Quality Panel */}
                <QualityPanel caseId={caseId} draftId={draft.id} />

                {/* Content Preview */}
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">Content</span>
                        {draft.content && draft.content.length > 500 && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="text-xs h-6"
                                onClick={() => setShowFullContent(!showFullContent)}
                            >
                                {showFullContent ? "Collapse" : "Expand"}
                            </Button>
                        )}
                    </div>
                    <div className="border border-border rounded-md p-4 bg-muted/20 max-h-[40vh] overflow-y-auto">
                        <pre className="text-sm whitespace-pre-wrap font-sans">
                            {showFullContent
                                ? draft.content || "No content"
                                : previewContent(draft.content, 2000)}
                        </pre>
                    </div>
                </div>

                {/* Review Results */}
                {reviewResult && (
                    <div className="space-y-3 border-t border-border pt-3">
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-medium">AI Review</span>
                            <div className="flex items-center gap-2">
                                <Badge variant="outline" className={scoreColor(reviewResult.overall_score)}>
                                    {reviewResult.overall_score}/100
                                </Badge>
                                <Badge variant="outline" className={gradeColor(reviewResult.grade)}>
                                    {reviewResult.grade}
                                </Badge>
                            </div>
                        </div>

                        {/* Strengths */}
                        {reviewResult.strengths?.length > 0 && (
                            <div>
                                <p className="text-xs font-medium text-emerald-400 mb-1">Strengths</p>
                                <ul className="space-y-0.5">
                                    {reviewResult.strengths.map((s, i) => (
                                        <li key={i} className="text-xs text-muted-foreground pl-3 border-l-2 border-emerald-500/30">
                                            {s}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {/* Issues */}
                        {reviewResult.issues?.length > 0 && (
                            <div>
                                <p className="text-xs font-medium text-amber-400 mb-1">
                                    Issues ({reviewResult.issues.length})
                                </p>
                                <div className="space-y-1.5">
                                    {reviewResult.issues.map((issue, i) => (
                                        <div key={i} className="text-xs p-2 rounded border border-border bg-muted/20">
                                            <div className="flex items-center gap-2 mb-0.5">
                                                <Badge variant="outline" className={`text-[10px] ${severityColor(issue.severity)}`}>
                                                    {issue.severity}
                                                </Badge>
                                                <span className="text-muted-foreground">
                                                    {issue.category} {issue.section !== "global" ? `(Section ${issue.section})` : ""}
                                                </span>
                                            </div>
                                            <p>{issue.description}</p>
                                            {issue.fix && (
                                                <p className="text-emerald-400/80 mt-0.5">Fix: {issue.fix}</p>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Suggestions */}
                        {reviewResult.suggestions?.length > 0 && (
                            <div>
                                <p className="text-xs font-medium text-blue-400 mb-1">Suggestions</p>
                                <ul className="space-y-0.5">
                                    {reviewResult.suggestions.map((s, i) => (
                                        <li key={i} className="text-xs text-muted-foreground pl-3 border-l-2 border-blue-500/30">
                                            {s}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                )}

                <DialogFooter className="flex-wrap gap-2">
                    {canDelete && (
                        <Button variant="destructive" size="sm" onClick={onDelete}>
                            Delete
                        </Button>
                    )}
                    {canEdit && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleReview}
                            disabled={isReviewing || !prepId}
                        >
                            {isReviewing ? (
                                <><LoadingSpinner className="h-3 w-3 mr-1.5" /> Reviewing...</>
                            ) : (
                                "AI Review"
                            )}
                        </Button>
                    )}
                    <Button variant="outline" size="sm" onClick={handleExportWord}>
                        Export Word
                    </Button>
                    <Button variant="outline" onClick={onClose}>
                        Close
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

// ---- Main Page Component ------------------------------------------------

export default function DocumentsPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, isLoading: prepLoading } = usePrep();
    const { canEdit, canDelete } = useRole();
    const queryClient = useQueryClient();

    const [wizardOpen, setWizardOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<Draft | null>(null);
    const [selectedDraft, setSelectedDraft] = useState<Draft | null>(null);
    const [expandedResearch, setExpandedResearch] = useState<number | null>(null);
    const [activeTab, setActiveTab] = useState("drafts");
    const [search, setSearch] = useState("");

    // ---- Queries ----

    const draftsQuery = useQuery({
        queryKey: ["documents", caseId],
        queryFn: () => api.get<Draft[]>(`/documents/drafts/${caseId}`, { getToken }),
    });

    const researchQuery = useQuery({
        queryKey: ["research", caseId, activePrepId],
        queryFn: () =>
            api.get<ResearchItem[]>(
                `/documents/research/${caseId}/${activePrepId}`,
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    const drafts = draftsQuery.data ?? [];
    const research = researchQuery.data ?? [];

    // Filter drafts by search
    const filteredDrafts = useMemo(() => {
        if (!search) return drafts;
        const q = search.toLowerCase();
        return drafts.filter(
            (d) =>
                d.title?.toLowerCase().includes(q) ||
                d.type?.toLowerCase().includes(q) ||
                d.court_type?.toLowerCase().includes(q)
        );
    }, [drafts, search]);

    // ---- Mutations ----

    const deleteMutation = useMutationWithToast<string>({
        mutationFn: (draftId) =>
            api.delete(`/documents/drafts/${caseId}/${draftId}`, { getToken }),
        successMessage: "Draft deleted",
        invalidateKeys: [["documents", caseId]],
        onSuccess: () => {
            setDeleteTarget(null);
            setSelectedDraft(null);
        },
    });

    // ---- Render: Drafts List ----

    const renderDraftsList = () => {
        if (draftsQuery.isLoading) {
            return (
                <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-24 w-full rounded-lg" />
                    ))}
                </div>
            );
        }

        if (draftsQuery.error) {
            return (
                <Card className="border-destructive/50">
                    <CardContent className="py-8 text-center">
                        <p className="text-sm text-destructive">
                            Failed to load drafts: {draftsQuery.error.message}
                        </p>
                    </CardContent>
                </Card>
            );
        }

        if (filteredDrafts.length === 0) {
            return (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        {search
                            ? "No drafts match your search."
                            : "No document drafts yet. Use the AI Draft Wizard to create one."}
                    </CardContent>
                </Card>
            );
        }

        return (
            <div className="space-y-2">
                {filteredDrafts.map((draft, i) => (
                    <Card
                        key={draft.id || i}
                        className="hover:bg-accent/30 transition-colors cursor-pointer group"
                        onClick={() => setSelectedDraft(draft)}
                    >
                        <CardContent className="py-3">
                            <div className="flex items-center justify-between mb-1">
                                <div className="flex items-center gap-3 min-w-0">
                                    <div className="min-w-0">
                                        <p className="font-medium text-sm">{draft.title}</p>
                                        <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                                            {previewContent(draft.content, 120)}
                                        </p>
                                    </div>
                                </div>
                                <div className="flex items-center gap-2 shrink-0 ml-3">
                                    <Badge
                                        variant="outline"
                                        className={`text-xs ${TYPE_COLORS[draft.type] || TYPE_COLORS.other}`}
                                    >
                                        {draft.type || "brief"}
                                    </Badge>
                                    {draft.court_type && (
                                        <Badge variant="secondary" className="text-[10px]">
                                            {draft.court_type}
                                        </Badge>
                                    )}
                                    {draft.quality_score != null && (
                                        <Badge variant="outline" className={`text-[10px] ${scoreColor(draft.quality_score)}`}>
                                            {draft.quality_score}
                                        </Badge>
                                    )}
                                    {draft.last_updated && (
                                        <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                                            {formatTimestamp(draft.last_updated)}
                                        </span>
                                    )}
                                    {canDelete && (
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive"
                                            aria-label={`Delete ${draft.title}`}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setDeleteTarget(draft);
                                            }}
                                        >
                                            {"\u2715"}
                                        </Button>
                                    )}
                                </div>
                            </div>
                            {draft.content && (
                                <div className="flex items-center gap-3 mt-1">
                                    <span className="text-[10px] text-muted-foreground">
                                        {draft.content.length.toLocaleString()} chars
                                    </span>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                ))}
            </div>
        );
    };

    // ---- Render: Research Section ----

    const renderResearchSection = () => {
        if (!activePrepId) {
            return (
                <Card className="border-dashed">
                    <CardContent className="py-8 text-center text-muted-foreground">
                        Select a preparation to view research data.
                    </CardContent>
                </Card>
            );
        }

        if (researchQuery.isLoading) {
            return (
                <div className="space-y-3">
                    {Array.from({ length: 3 }).map((_, i) => (
                        <Skeleton key={i} className="h-24 w-full rounded-lg" />
                    ))}
                </div>
            );
        }

        if (researchQuery.error) {
            return (
                <Card className="border-destructive/50">
                    <CardContent className="py-8 text-center">
                        <p className="text-sm text-destructive">
                            Failed to load research: {researchQuery.error.message}
                        </p>
                    </CardContent>
                </Card>
            );
        }

        if (research.length === 0) {
            return (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        No research data yet. Run analysis to generate research insights.
                    </CardContent>
                </Card>
            );
        }

        return (
            <div className="space-y-2">
                {research.map((item, i) => {
                    const isExpanded = expandedResearch === i;
                    return (
                        <Card
                            key={i}
                            className="hover:bg-accent/20 transition-colors cursor-pointer"
                            onClick={() => setExpandedResearch(isExpanded ? null : i)}
                        >
                            <CardContent className="py-3">
                                <div className="flex items-center justify-between mb-1">
                                    <p className="font-medium text-sm">
                                        {item.topic || `Research Item ${i + 1}`}
                                    </p>
                                    <Badge variant="secondary" className="text-[10px]">
                                        {item.citations?.length || 0} citation{(item.citations?.length || 0) !== 1 ? "s" : ""}
                                    </Badge>
                                </div>
                                {!isExpanded && item.summary && (
                                    <p className="text-xs text-muted-foreground line-clamp-2">
                                        {item.summary}
                                    </p>
                                )}
                                {isExpanded && (
                                    <div className="mt-2 space-y-2">
                                        {item.summary && (
                                            <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                                                {item.summary}
                                            </p>
                                        )}
                                        {item.source && (
                                            <p className="text-xs text-muted-foreground">
                                                Source: {item.source}
                                            </p>
                                        )}
                                        {item.citations?.length > 0 && (
                                            <div className="pt-1 border-t border-border">
                                                <p className="text-xs font-medium text-muted-foreground mb-1">
                                                    Citations:
                                                </p>
                                                <div className="space-y-0.5">
                                                    {item.citations.map((cite, ci) => (
                                                        <p key={ci} className="text-xs text-muted-foreground pl-2 border-l-2 border-border">
                                                            {cite}
                                                        </p>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    );
                })}
            </div>
        );
    };

    // ---- Main Render ----

    return (
        <div className="space-y-5">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">Document Drafter</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        AI-powered document drafting with outline generation, quality scoring, and review
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {canEdit && (
                        <Button onClick={() => setWizardOpen(true)} size="sm" className="gap-1.5">
                            <span>+</span> AI Draft Wizard
                        </Button>
                    )}
                </div>
            </div>

            {/* Tabs: Drafts + Research */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList>
                    <TabsTrigger value="drafts">
                        Drafts
                        {drafts.length > 0 && (
                            <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5">
                                {drafts.length}
                            </Badge>
                        )}
                    </TabsTrigger>
                    <TabsTrigger value="research">
                        Research
                        {research.length > 0 && (
                            <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5">
                                {research.length}
                            </Badge>
                        )}
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="drafts" className="mt-4">
                    {/* Search */}
                    {drafts.length > 0 && (
                        <div className="flex items-center gap-3 mb-4">
                            <Input
                                placeholder="Search drafts..."
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                className="max-w-sm"
                            />
                            {search && filteredDrafts.length !== drafts.length && (
                                <span className="text-xs text-muted-foreground">
                                    {filteredDrafts.length} of {drafts.length}
                                </span>
                            )}
                        </div>
                    )}
                    {renderDraftsList()}
                </TabsContent>

                <TabsContent value="research" className="mt-4">
                    {renderResearchSection()}
                </TabsContent>
            </Tabs>

            {/* New Draft Wizard */}
            {canEdit && (
                <NewDraftWizard
                    open={wizardOpen}
                    onOpenChange={setWizardOpen}
                    caseId={caseId}
                    prepId={activePrepId}
                />
            )}

            {/* Delete Confirm */}
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
                title="Delete Draft"
                description={`Delete "${deleteTarget?.title}"? This cannot be undone.`}
                onConfirm={() => {
                    if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
                }}
                isLoading={deleteMutation.isPending}
            />

            {/* Draft Detail View */}
            {selectedDraft && (
                <DraftDetailView
                    draft={selectedDraft}
                    caseId={caseId}
                    prepId={activePrepId}
                    onClose={() => setSelectedDraft(null)}
                    onDelete={() => {
                        setDeleteTarget(selectedDraft);
                        setSelectedDraft(null);
                    }}
                />
            )}
        </div>
    );
}
