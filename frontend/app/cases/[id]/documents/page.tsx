// ---- Major Document Drafter ------------------------------------------------
// Full drafting workspace: Outline → Draft → Assemble → Export
"use client";

import { useState, useMemo, useCallback } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { usePrep } from "@/hooks/use-prep";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type {
    DocOutlineSection, DocOutline, DraftedSection, DocCitation,
    BriefReview, OpponentAnalysis, CitationVerification, MajorDraft,
} from "@/types/api";

// ---- Constants -----------------------------------------------------------

const DOC_TYPES: Record<string, string[]> = {
    "Appellate Brief": ["Opening Brief", "Reply Brief", "Amicus Brief"],
    "Post-Conviction Relief": ["PCR Petition", "Habeas Corpus", "Coram Nobis"],
    "Civil Complaint": ["Initial Complaint", "Amended Complaint", "Counterclaim", "Third-Party Complaint"],
    "Appellate Motion": ["Motion for Extension", "Motion to Stay", "Motion for Rehearing"],
    "Major Motion": ["Motion for Summary Judgment", "Motion to Dismiss", "Motion for New Trial"],
    "Custom Document": [],
};

const TONES = ["Formal/Persuasive", "Aggressive", "Measured", "Empathetic"];
const LENGTHS = ["Brief (~5-10 pages)", "Standard (~15-25 pages)", "Comprehensive (~30-50 pages)"];
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV"];

const GRADE_COLORS: Record<string, string> = {
    "A+": "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    "A": "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    "B": "bg-blue-500/15 text-blue-400 border-blue-500/30",
    "C": "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
    "D": "bg-orange-500/15 text-orange-400 border-orange-500/30",
    "F": "bg-red-500/15 text-red-400 border-red-500/30",
};

type Phase = "list" | "outline" | "draft" | "assemble";

// ---- Draft list item (index metadata) ------------------------------------

interface DraftIndex {
    id: string;
    title: string;
    doc_type?: string;
    doc_subtype?: string;
    type?: string;
    created_at: string;
    updated_at?: string;
    last_updated?: string;
    section_count?: number;
    outline_count?: number;
}

// ---- Main page component -------------------------------------------------

export default function DocumentsPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId } = usePrep();
    const { canEdit } = useRole();
    const qc = useQueryClient();

    // ---- Phase state machine ----
    const [phase, setPhase] = useState<Phase>("list");
    const [activeDraftId, setActiveDraftId] = useState<string | null>(null);

    // ---- Outline phase state ----
    const [docType, setDocType] = useState("Appellate Brief");
    const [docSubtype, setDocSubtype] = useState("Opening Brief");
    const [tone, setTone] = useState("Formal/Persuasive");
    const [targetLength, setTargetLength] = useState("Standard (~15-25 pages)");
    const [customInstructions, setCustomInstructions] = useState("");
    const [documentTitle, setDocumentTitle] = useState("");
    const [outline, setOutline] = useState<DocOutlineSection[]>([]);

    // ---- Draft phase state ----
    const [sections, setSections] = useState<DraftedSection[]>([]);
    const [citationLibrary, setCitationLibrary] = useState<DocCitation[]>([]);
    const [draftingIndex, setDraftingIndex] = useState<number | null>(null);

    // ---- Assemble phase state ----
    const [reviewResults, setReviewResults] = useState<BriefReview | null>(null);
    const [opponentText, setOpponentText] = useState("");
    const [opponentAnalysis, setOpponentAnalysis] = useState<OpponentAnalysis | null>(null);
    const [citationVerification, setCitationVerification] = useState<CitationVerification | null>(null);

    // ---- Attorney settings ----
    const [jurisdiction, setJurisdiction] = useState("tennessee_state");
    const [attorneyName, setAttorneyName] = useState("");
    const [barNumber, setBarNumber] = useState("");

    // ---- Data queries ----
    const draftsQuery = useQuery({
        queryKey: ["documents", caseId],
        queryFn: () => api.get<DraftIndex[]>(`/documents/drafts/${caseId}`, { getToken }),
    });

    const prepId = activePrepId || "";

    // ---- Invalidation ----
    const invalidateDrafts = () => qc.invalidateQueries({ queryKey: ["documents", caseId] });

    // ---- Auto-save helper ----
    const autoSave = useCallback(async (opts?: { showToast?: boolean }) => {
        if (!documentTitle) return;
        try {
            const payload = {
                title: documentTitle,
                doc_type: docType,
                doc_subtype: docSubtype,
                outline,
                sections,
                citation_library: citationLibrary,
                review_results: reviewResults || {},
                attorney_info: { name: attorneyName, bar_number: barNumber },
                config: { jurisdiction, tone, target_length: targetLength },
                content: sections.map(s => s.content || "").join("\n\n---\n\n"),
            };
            if (activeDraftId) {
                await api.put(`/documents/drafts/${caseId}/${activeDraftId}`, {
                    title: documentTitle, type: docType, content: JSON.stringify(payload),
                }, { getToken });
            } else {
                const res = await api.post<{ id: string }>(`/documents/drafts/${caseId}/full`, payload, { getToken });
                setActiveDraftId(res.id);
            }
            if (opts?.showToast) toast.success("Draft saved");
            invalidateDrafts();
        } catch { /* silent save */ }
    }, [documentTitle, docType, docSubtype, outline, sections, citationLibrary, reviewResults,
        attorneyName, barNumber, jurisdiction, tone, targetLength, activeDraftId, caseId, getToken]);

    // ---- Load a saved draft ----
    const loadDraft = async (draftId: string) => {
        try {
            const draft = await api.get<MajorDraft>(`/documents/drafts/${caseId}/${draftId}/full`, { getToken });
            setActiveDraftId(draftId);
            setDocumentTitle(draft.title || "");
            setDocType(draft.doc_type || "Appellate Brief");
            setDocSubtype(draft.doc_subtype || "");
            setOutline(draft.outline || []);
            setSections((draft.sections || []) as DraftedSection[]);
            setCitationLibrary(draft.citation_library || []);
            setReviewResults(draft.review_results || null);
            if (draft.attorney_info) {
                setAttorneyName(draft.attorney_info.name || "");
                setBarNumber(draft.attorney_info.bar_number || "");
            }
            if (draft.config) {
                setJurisdiction(draft.config.jurisdiction || "tennessee_state");
                setTone(draft.config.tone || "Formal/Persuasive");
                setTargetLength(draft.config.target_length || "Standard (~15-25 pages)");
            }
            // Determine phase from data
            if ((draft.sections || []).length > 0) setPhase("assemble");
            else if ((draft.outline || []).length > 0) setPhase("draft");
            else setPhase("outline");
        } catch {
            toast.error("Failed to load draft");
        }
    };

    // ---- Delete draft ----
    const deleteMutation = useMutationWithToast<string>({
        mutationFn: (draftId) => api.delete(`/documents/drafts/${caseId}/${draftId}`, { getToken }),
        successMessage: "Draft deleted",
        invalidateKeys: [["documents", caseId]],
    });

    // ---- Reset to new document ----
    const resetWorkspace = () => {
        setPhase("list");
        setActiveDraftId(null);
        setDocumentTitle("");
        setOutline([]);
        setSections([]);
        setCitationLibrary([]);
        setReviewResults(null);
        setOpponentAnalysis(null);
        setCitationVerification(null);
        setOpponentText("");
        setDraftingIndex(null);
    };

    // ---- AI Mutations ----

    const generateOutlineMutation = useMutationWithToast<void, DocOutline>({
        mutationFn: () => api.post<DocOutline>(`/documents/${caseId}/outline`, {
            prep_id: prepId, doc_type: docType, doc_subtype: docSubtype,
            custom_instructions: customInstructions, target_length: targetLength, tone,
        }, { getToken }),
        successMessage: "Outline generated",
        onSuccess: (result) => {
            setOutline(result.outline || []);
            setDocumentTitle(result.document_title || `${docType} - ${docSubtype}`);
        },
    });

    const buildCitationsMutation = useMutationWithToast<void, DocCitation[]>({
        mutationFn: () => api.post<DocCitation[]>(`/documents/${caseId}/citations/build`, {
            prep_id: prepId, additional_citations: citationLibrary,
        }, { getToken }),
        successMessage: "Citation library built",
        onSuccess: (result) => {
            setCitationLibrary(Array.isArray(result) ? result : []);
        },
    });

    const draftSectionMutation = useMutationWithToast<number, { content: string; citations_used: DocCitation[] }>({
        mutationFn: async (sectionIdx) => {
            setDraftingIndex(sectionIdx);
            const section = outline[sectionIdx];
            const prevSections = sections.filter(s => s.content).slice(-3);
            return api.post(`/documents/${caseId}/sections/draft`, {
                prep_id: prepId, section, outline, previous_sections: prevSections,
                citation_library: citationLibrary, doc_type: docType, tone,
                specific_instructions: section.instructions || "",
            }, { getToken });
        },
        successMessage: "Section drafted",
        onSuccess: (result, sectionIdx) => {
            setSections(prev => {
                const updated = [...prev];
                const outlineSection = outline[sectionIdx];
                updated[sectionIdx] = {
                    ...outlineSection,
                    content: result.content || "",
                    citations_used: result.citations_used || [],
                };
                return updated;
            });
            setDraftingIndex(null);
        },
        onError: () => setDraftingIndex(null),
    });

    const reviewMutation = useMutationWithToast<void, BriefReview>({
        mutationFn: () => api.post<BriefReview>(`/documents/${caseId}/review`, {
            prep_id: prepId, sections, outline, citation_library: citationLibrary, doc_type: docType,
        }, { getToken }),
        successMessage: "Review complete",
        onSuccess: (result) => setReviewResults(result),
    });

    const opponentMutation = useMutationWithToast<void, OpponentAnalysis>({
        mutationFn: () => api.post<OpponentAnalysis>(`/documents/${caseId}/opponent-analysis`, {
            prep_id: prepId, opposing_text: opponentText, citation_library: citationLibrary,
        }, { getToken }),
        successMessage: "Opponent analysis complete",
        onSuccess: (result) => setOpponentAnalysis(result),
    });

    const verifyMutation = useMutationWithToast<void, CitationVerification>({
        mutationFn: () => api.post<CitationVerification>(`/documents/${caseId}/verify-citations`, {
            prep_id: prepId, sections, citation_library: citationLibrary,
        }, { getToken }),
        successMessage: "Citation verification complete",
        onSuccess: (result) => setCitationVerification(result),
    });

    // ---- Draft All helper ----
    const draftAllRemaining = async () => {
        for (let i = 0; i < outline.length; i++) {
            if (!sections[i]?.content) {
                await draftSectionMutation.mutateAsync(i);
            }
        }
        toast.success("All sections drafted");
    };

    // ---- Derived values ----
    const draftedCount = sections.filter(s => s?.content).length;
    const totalSections = outline.length;
    const subtypes = useMemo(() => DOC_TYPES[docType] || [], [docType]);

    // ---- Render by phase ----

    if (phase === "list") {
        return (
            <div className="space-y-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-xl font-bold tracking-tight">Major Document Drafter</h2>
                        <p className="text-muted-foreground text-sm mt-1">
                            Briefs, motions, petitions, and complaints — AI-powered section-by-section drafting
                        </p>
                    </div>
                    {canEdit && (
                        <Button onClick={() => { resetWorkspace(); setPhase("outline"); }}>
                            New Document
                        </Button>
                    )}
                </div>

                {draftsQuery.isLoading ? (
                    <div className="space-y-3">
                        {[1, 2, 3].map(i => <Skeleton key={i} className="h-20" />)}
                    </div>
                ) : !draftsQuery.data?.length ? (
                    <EmptyState
                        icon="\uD83D\uDCC4"
                        title="No document drafts yet"
                        description="Click &quot;New Document&quot; to start drafting a major legal document."
                    />
                ) : (
                    <div className="space-y-2">
                        {draftsQuery.data.map((draft) => (
                            <Card
                                key={draft.id}
                                className="glass-card hover:bg-accent/30 transition-colors cursor-pointer group"
                                onClick={() => loadDraft(draft.id)}
                            >
                                <CardContent className="flex items-center justify-between py-3 px-4">
                                    <div className="flex items-center gap-3">
                                        <span aria-hidden>📄</span>
                                        <div>
                                            <p className="font-medium text-sm">{draft.title}</p>
                                            <p className="text-xs text-muted-foreground">
                                                {draft.doc_type || draft.type || "Document"}
                                                {draft.doc_subtype ? ` — ${draft.doc_subtype}` : ""}
                                                {" · "}
                                                {draft.section_count ? `${draft.section_count} sections` : ""}
                                                {draft.updated_at || draft.last_updated
                                                    ? ` · Updated ${(draft.updated_at || draft.last_updated || "").slice(0, 10)}`
                                                    : ""}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Badge variant="secondary" className="text-xs">
                                            {draft.doc_type || draft.type || "draft"}
                                        </Badge>
                                        {canEdit && (
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-7 w-7 opacity-0 group-hover:opacity-100 text-destructive"
                                                onClick={(e) => { e.stopPropagation(); deleteMutation.mutate(draft.id); }}
                                            >
                                                ✕
                                            </Button>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )}
            </div>
        );
    }

    // ---- Shared header for all workspace phases ----
    const workspaceHeader = (
        <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
                <Button variant="ghost" size="sm" onClick={resetWorkspace}>← Back</Button>
                <h2 className="text-lg font-bold">{documentTitle || "New Document"}</h2>
                <Badge variant="outline" className="text-xs capitalize">{phase}</Badge>
            </div>
            <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => autoSave({ showToast: true })}>
                    Save Draft
                </Button>
                {phase === "outline" && outline.length > 0 && (
                    <Button size="sm" onClick={() => {
                        setSections(outline.map(o => ({ ...o, content: "", citations_used: [] })));
                        setPhase("draft");
                    }}>
                        Approve &amp; Begin Drafting →
                    </Button>
                )}
                {phase === "draft" && draftedCount === totalSections && totalSections > 0 && (
                    <Button size="sm" onClick={() => setPhase("assemble")}>
                        Review &amp; Assemble →
                    </Button>
                )}
            </div>
        </div>
    );

    // ---- OUTLINE PHASE ----
    if (phase === "outline") {
        return (
            <div className="space-y-6">
                {workspaceHeader}

                {/* Config Panel */}
                <Card className="glass-card">
                    <CardHeader><CardTitle className="text-base">Document Configuration</CardTitle></CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Document Type</Label>
                                <Select value={docType} onValueChange={(v) => {
                                    setDocType(v);
                                    const subs = DOC_TYPES[v] || [];
                                    setDocSubtype(subs[0] || "");
                                }}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        {Object.keys(DOC_TYPES).map(t => (
                                            <SelectItem key={t} value={t}>{t}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            {subtypes.length > 0 && (
                                <div className="space-y-2">
                                    <Label>Subtype</Label>
                                    <Select value={docSubtype} onValueChange={setDocSubtype}>
                                        <SelectTrigger><SelectValue /></SelectTrigger>
                                        <SelectContent>
                                            {subtypes.map(s => (
                                                <SelectItem key={s} value={s}>{s}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            )}
                            <div className="space-y-2">
                                <Label>Tone</Label>
                                <Select value={tone} onValueChange={setTone}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        {TONES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label>Target Length</Label>
                                <Select value={targetLength} onValueChange={setTargetLength}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        {LENGTHS.map(l => <SelectItem key={l} value={l}>{l}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label>Custom Instructions (optional)</Label>
                            <Textarea
                                value={customInstructions}
                                onChange={e => setCustomInstructions(e.target.value)}
                                placeholder="E.g., Focus on Fourth Amendment issues, emphasize Miranda violations..."
                                rows={3}
                            />
                        </div>
                        {!prepId && (
                            <p className="text-sm text-yellow-400">
                                Select a preparation in the case header for AI-powered outline generation.
                            </p>
                        )}
                        <Button
                            onClick={() => generateOutlineMutation.mutate()}
                            disabled={generateOutlineMutation.isPending || !prepId}
                        >
                            {generateOutlineMutation.isPending ? "Generating Outline..." : "Generate Outline"}
                        </Button>
                    </CardContent>
                </Card>

                {/* Generated Outline */}
                {outline.length > 0 && (
                    <Card className="glass-card">
                        <CardHeader>
                            <CardTitle className="text-base">
                                Document Outline ({outline.length} sections)
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <div className="space-y-2">
                                <Label>Document Title</Label>
                                <Input
                                    value={documentTitle}
                                    onChange={e => setDocumentTitle(e.target.value)}
                                />
                            </div>
                            {outline.map((section, idx) => (
                                <Card key={idx} className="border border-border/50">
                                    <CardContent className="py-3 px-4 space-y-2">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <Badge variant="outline" className="text-xs">
                                                    {section.section_num}
                                                </Badge>
                                                <Input
                                                    value={section.title}
                                                    className="h-7 text-sm font-medium"
                                                    onChange={e => {
                                                        const updated = [...outline];
                                                        updated[idx] = { ...updated[idx], title: e.target.value };
                                                        setOutline(updated);
                                                    }}
                                                />
                                            </div>
                                            <Button
                                                variant="ghost" size="icon"
                                                className="h-6 w-6 text-destructive"
                                                onClick={() => setOutline(outline.filter((_, i) => i !== idx))}
                                            >
                                                ✕
                                            </Button>
                                        </div>
                                        <Textarea
                                            value={section.description}
                                            rows={2}
                                            className="text-xs"
                                            onChange={e => {
                                                const updated = [...outline];
                                                updated[idx] = { ...updated[idx], description: e.target.value };
                                                setOutline(updated);
                                            }}
                                        />
                                        <Input
                                            placeholder="Special instructions for this section..."
                                            value={section.instructions || ""}
                                            className="text-xs h-7"
                                            onChange={e => {
                                                const updated = [...outline];
                                                updated[idx] = { ...updated[idx], instructions: e.target.value };
                                                setOutline(updated);
                                            }}
                                        />
                                    </CardContent>
                                </Card>
                            ))}
                            <Button
                                variant="outline" size="sm"
                                onClick={() => setOutline([...outline, {
                                    section_num: ROMAN[outline.length] || `${outline.length + 1}`,
                                    title: "New Section",
                                    description: "",
                                    estimated_pages: 2,
                                }])}
                            >
                                + Add Section
                            </Button>
                        </CardContent>
                    </Card>
                )}
            </div>
        );
    }

    // ---- DRAFT PHASE ----
    if (phase === "draft") {
        return (
            <div className="space-y-6">
                {workspaceHeader}

                {/* Progress */}
                <div className="flex items-center gap-4">
                    <div className="flex-1 bg-muted rounded-full h-2">
                        <div
                            className="bg-brand-indigo h-2 rounded-full transition-all"
                            style={{ width: `${totalSections ? (draftedCount / totalSections) * 100 : 0}%` }}
                        />
                    </div>
                    <span className="text-sm text-muted-foreground">
                        {draftedCount}/{totalSections} sections drafted
                    </span>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Citation Library Panel */}
                    <Card className="glass-card lg:col-span-1">
                        <CardHeader>
                            <CardTitle className="text-sm">
                                Citation Library ({citationLibrary.length})
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <Button
                                size="sm" variant="outline" className="w-full"
                                onClick={() => buildCitationsMutation.mutate()}
                                disabled={buildCitationsMutation.isPending || !prepId}
                            >
                                {buildCitationsMutation.isPending ? "Building..." : "Build from Case"}
                            </Button>
                            {citationLibrary.length === 0 ? (
                                <p className="text-xs text-muted-foreground text-center py-4">
                                    No citations yet. Build from case data or add manually.
                                </p>
                            ) : (
                                <div className="space-y-2 max-h-96 overflow-y-auto">
                                    {citationLibrary.map((cite, i) => (
                                        <div key={i} className="border border-border/50 rounded p-2 text-xs space-y-1">
                                            <p className="font-medium">{cite.case_name}</p>
                                            <p className="text-muted-foreground">{cite.citation}</p>
                                            <p className="text-muted-foreground italic">{cite.holding?.slice(0, 120)}...</p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Sections Panel */}
                    <div className="lg:col-span-2 space-y-3">
                        <div className="flex items-center justify-between">
                            <h3 className="text-sm font-semibold">Document Sections</h3>
                            <Button
                                size="sm" variant="outline"
                                onClick={draftAllRemaining}
                                disabled={draftSectionMutation.isPending || draftedCount === totalSections}
                            >
                                Draft All Remaining
                            </Button>
                        </div>
                        {outline.map((section, idx) => {
                            const drafted = sections[idx]?.content;
                            const isDrafting = draftingIndex === idx;
                            return (
                                <Card key={idx} className={`border ${drafted ? "border-emerald-500/30" : "border-border/50"}`}>
                                    <CardContent className="py-3 px-4">
                                        <div className="flex items-center justify-between mb-2">
                                            <div className="flex items-center gap-2">
                                                <Badge variant={drafted ? "default" : "outline"} className="text-xs">
                                                    {section.section_num}
                                                </Badge>
                                                <span className="text-sm font-medium">{section.title}</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {drafted && (
                                                    <Badge variant="outline" className="text-xs bg-emerald-500/15 text-emerald-400">
                                                        ✓ Drafted
                                                    </Badge>
                                                )}
                                                <Button
                                                    size="sm" variant={drafted ? "outline" : "default"}
                                                    onClick={() => draftSectionMutation.mutate(idx)}
                                                    disabled={isDrafting || draftSectionMutation.isPending}
                                                >
                                                    {isDrafting ? "Drafting..." : drafted ? "Regenerate" : "Draft"}
                                                </Button>
                                            </div>
                                        </div>
                                        {drafted && (
                                            <div className="mt-2">
                                                <Textarea
                                                    value={drafted}
                                                    rows={6}
                                                    className="text-xs font-mono"
                                                    onChange={e => {
                                                        const updated = [...sections];
                                                        updated[idx] = { ...updated[idx], content: e.target.value };
                                                        setSections(updated);
                                                    }}
                                                />
                                                {sections[idx]?.citations_used?.length > 0 && (
                                                    <p className="text-xs text-muted-foreground mt-1">
                                                        Citations used: {sections[idx].citations_used.map(c => c.case_name).join(", ")}
                                                    </p>
                                                )}
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            );
                        })}
                    </div>
                </div>
            </div>
        );
    }

    // ---- ASSEMBLE PHASE ----
    return (
        <div className="space-y-6">
            {workspaceHeader}

            <Tabs defaultValue="preview">
                <TabsList>
                    <TabsTrigger value="preview">Document Preview</TabsTrigger>
                    <TabsTrigger value="review">AI Review</TabsTrigger>
                    <TabsTrigger value="opponent">Opponent Analysis</TabsTrigger>
                    <TabsTrigger value="citations">Citation Verification</TabsTrigger>
                    <TabsTrigger value="export">Export</TabsTrigger>
                </TabsList>

                {/* Preview Tab */}
                <TabsContent value="preview" className="space-y-4">
                    <Card className="glass-card">
                        <CardContent className="py-6 prose prose-sm dark:prose-invert max-w-none">
                            <h1 className="text-center">{documentTitle}</h1>
                            {sections.filter(s => s?.content).map((section, i) => (
                                <div key={i} className="mb-6">
                                    <h2>{section.section_num}. {section.title}</h2>
                                    <div className="whitespace-pre-wrap">{section.content}</div>
                                </div>
                            ))}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* AI Review Tab */}
                <TabsContent value="review" className="space-y-4">
                    <Button
                        onClick={() => reviewMutation.mutate()}
                        disabled={reviewMutation.isPending || !prepId}
                    >
                        {reviewMutation.isPending ? "Reviewing..." : "Run AI Review"}
                    </Button>

                    {reviewResults && (
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <Card className="glass-card">
                                    <CardContent className="pt-4 pb-3 px-4 text-center">
                                        <p className="text-3xl font-bold">{reviewResults.overall_score}</p>
                                        <p className="text-xs text-muted-foreground">Score</p>
                                    </CardContent>
                                </Card>
                                <Card className="glass-card">
                                    <CardContent className="pt-4 pb-3 px-4 text-center">
                                        <Badge variant="outline" className={`text-lg ${GRADE_COLORS[reviewResults.grade] || ""}`}>
                                            {reviewResults.grade}
                                        </Badge>
                                        <p className="text-xs text-muted-foreground mt-1">Grade</p>
                                    </CardContent>
                                </Card>
                                <Card className="glass-card">
                                    <CardContent className="pt-4 pb-3 px-4 text-center">
                                        <p className="text-3xl font-bold">{reviewResults.issues?.length || 0}</p>
                                        <p className="text-xs text-muted-foreground">Issues</p>
                                    </CardContent>
                                </Card>
                                <Card className="glass-card">
                                    <CardContent className="pt-4 pb-3 px-4 text-center">
                                        <p className="text-3xl font-bold">{reviewResults.strengths?.length || 0}</p>
                                        <p className="text-xs text-muted-foreground">Strengths</p>
                                    </CardContent>
                                </Card>
                            </div>

                            {reviewResults.issues?.length > 0 && (
                                <Card className="glass-card">
                                    <CardHeader><CardTitle className="text-sm">Issues Found</CardTitle></CardHeader>
                                    <CardContent>
                                        <div className="space-y-2">
                                            {reviewResults.issues.map((issue, i) => (
                                                <div key={i} className="border border-border/50 rounded p-3">
                                                    <div className="flex items-center gap-2 mb-1">
                                                        <Badge variant="outline" className={`text-xs ${
                                                            issue.severity === "high" ? "bg-red-500/15 text-red-400" :
                                                            issue.severity === "medium" ? "bg-yellow-500/15 text-yellow-400" :
                                                            "bg-zinc-500/15 text-zinc-400"
                                                        }`}>
                                                            {issue.severity}
                                                        </Badge>
                                                        <Badge variant="secondary" className="text-xs">{issue.category}</Badge>
                                                        {issue.section && (
                                                            <span className="text-xs text-muted-foreground">Section {issue.section}</span>
                                                        )}
                                                    </div>
                                                    <p className="text-sm">{issue.description}</p>
                                                    {issue.fix && (
                                                        <p className="text-xs text-muted-foreground mt-1">
                                                            <span className="font-medium">Fix:</span> {issue.fix}
                                                        </p>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            )}

                            {reviewResults.strengths?.length > 0 && (
                                <Card className="glass-card">
                                    <CardHeader><CardTitle className="text-sm">Strengths</CardTitle></CardHeader>
                                    <CardContent>
                                        <ul className="list-disc list-inside text-sm space-y-1">
                                            {reviewResults.strengths.map((s, i) => <li key={i}>{s}</li>)}
                                        </ul>
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                    )}
                </TabsContent>

                {/* Opponent Analysis Tab */}
                <TabsContent value="opponent" className="space-y-4">
                    <Card className="glass-card">
                        <CardHeader><CardTitle className="text-sm">Paste Opposing Brief</CardTitle></CardHeader>
                        <CardContent className="space-y-3">
                            <Textarea
                                value={opponentText}
                                onChange={e => setOpponentText(e.target.value)}
                                placeholder="Paste the opposing party's brief text here..."
                                rows={8}
                            />
                            <Button
                                onClick={() => opponentMutation.mutate()}
                                disabled={opponentMutation.isPending || !opponentText.trim() || !prepId}
                            >
                                {opponentMutation.isPending ? "Analyzing..." : "Analyze Opposing Brief"}
                            </Button>
                        </CardContent>
                    </Card>

                    {opponentAnalysis && (
                        <div className="space-y-4">
                            {opponentAnalysis.opponent_arguments?.length > 0 && (
                                <Card className="glass-card">
                                    <CardHeader><CardTitle className="text-sm">Opponent Arguments</CardTitle></CardHeader>
                                    <CardContent className="space-y-2">
                                        {opponentAnalysis.opponent_arguments.map((arg, i) => (
                                            <div key={i} className="border border-border/50 rounded p-3">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <Badge variant="outline" className="text-xs">{arg.strength}</Badge>
                                                    <span className="text-xs text-muted-foreground">{arg.section_ref}</span>
                                                </div>
                                                <p className="text-sm">{arg.argument}</p>
                                            </div>
                                        ))}
                                    </CardContent>
                                </Card>
                            )}
                            {opponentAnalysis.counter_arguments?.length > 0 && (
                                <Card className="glass-card">
                                    <CardHeader><CardTitle className="text-sm">Counter-Arguments</CardTitle></CardHeader>
                                    <CardContent className="space-y-2">
                                        {opponentAnalysis.counter_arguments.map((ca, i) => (
                                            <div key={i} className="border border-border/50 rounded p-3">
                                                <p className="text-sm font-medium">Responding to argument #{ca.opposing_arg_number}</p>
                                                <p className="text-sm mt-1">{ca.counter}</p>
                                                {ca.supporting_law && (
                                                    <p className="text-xs text-muted-foreground mt-1">
                                                        <span className="font-medium">Law:</span> {ca.supporting_law}
                                                    </p>
                                                )}
                                            </div>
                                        ))}
                                    </CardContent>
                                </Card>
                            )}
                            {opponentAnalysis.response_strategy && (
                                <Card className="glass-card">
                                    <CardHeader><CardTitle className="text-sm">Response Strategy</CardTitle></CardHeader>
                                    <CardContent>
                                        <p className="text-sm whitespace-pre-wrap">{opponentAnalysis.response_strategy}</p>
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                    )}
                </TabsContent>

                {/* Citation Verification Tab */}
                <TabsContent value="citations" className="space-y-4">
                    <Button
                        onClick={() => verifyMutation.mutate()}
                        disabled={verifyMutation.isPending || !prepId || citationLibrary.length === 0}
                    >
                        {verifyMutation.isPending ? "Verifying..." : "Verify Citations (Cross-Model)"}
                    </Button>

                    {citationVerification && (
                        <div className="space-y-4">
                            <p className="text-sm text-muted-foreground">{citationVerification.summary}</p>

                            {citationVerification.flagged?.length > 0 && (
                                <Card className="glass-card border-red-500/30">
                                    <CardHeader><CardTitle className="text-sm text-red-400">Flagged Citations</CardTitle></CardHeader>
                                    <CardContent className="space-y-2">
                                        {citationVerification.flagged.map((f, i) => (
                                            <div key={i} className="border border-red-500/30 rounded p-3">
                                                <p className="text-sm font-medium">{f.case_name}</p>
                                                <p className="text-xs text-muted-foreground">{f.citation}</p>
                                                <p className="text-xs mt-1">{f.notes}</p>
                                                <div className="flex gap-2 mt-1">
                                                    {!f.exists && <Badge variant="outline" className="text-xs bg-red-500/15 text-red-400">Not Found</Badge>}
                                                    {!f.citation_correct && <Badge variant="outline" className="text-xs bg-yellow-500/15 text-yellow-400">Citation Error</Badge>}
                                                    {!f.holding_accurate && <Badge variant="outline" className="text-xs bg-yellow-500/15 text-yellow-400">Holding Inaccurate</Badge>}
                                                    {!f.still_good_law && <Badge variant="outline" className="text-xs bg-red-500/15 text-red-400">Bad Law</Badge>}
                                                </div>
                                            </div>
                                        ))}
                                    </CardContent>
                                </Card>
                            )}

                            {citationVerification.verified?.length > 0 && (
                                <Card className="glass-card border-emerald-500/30">
                                    <CardHeader><CardTitle className="text-sm text-emerald-400">Verified Citations</CardTitle></CardHeader>
                                    <CardContent className="space-y-2">
                                        {citationVerification.verified.map((v, i) => (
                                            <div key={i} className="border border-emerald-500/30 rounded p-2 flex items-center justify-between">
                                                <div>
                                                    <p className="text-sm font-medium">{v.case_name}</p>
                                                    <p className="text-xs text-muted-foreground">{v.citation}</p>
                                                </div>
                                                <Badge variant="outline" className="text-xs bg-emerald-500/15 text-emerald-400">
                                                    {v.confidence}% confident
                                                </Badge>
                                            </div>
                                        ))}
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                    )}
                </TabsContent>

                {/* Export Tab */}
                <TabsContent value="export" className="space-y-4">
                    <Card className="glass-card">
                        <CardHeader><CardTitle className="text-sm">Export Settings</CardTitle></CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Jurisdiction</Label>
                                    <Select value={jurisdiction} onValueChange={setJurisdiction}>
                                        <SelectTrigger><SelectValue /></SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="tennessee_state">Tennessee State Court</SelectItem>
                                            <SelectItem value="federal">Federal Court</SelectItem>
                                            <SelectItem value="texas_state">Texas State Court</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label>Attorney Name</Label>
                                    <Input value={attorneyName} onChange={e => setAttorneyName(e.target.value)} placeholder="Your name" />
                                </div>
                                <div className="space-y-2">
                                    <Label>Bar Number</Label>
                                    <Input value={barNumber} onChange={e => setBarNumber(e.target.value)} placeholder="Bar #" />
                                </div>
                            </div>
                            <Button
                                onClick={async () => {
                                    if (!activeDraftId) {
                                        toast.error("Save the draft first");
                                        return;
                                    }
                                    try {
                                        const token = await getToken();
                                        const csrfMatch = document.cookie.match(/(?:^|;\s*)mc-csrf=([^;]*)/);
                                        const csrfToken = csrfMatch ? decodeURIComponent(csrfMatch[1]) : "";
                                        const docHeaders: Record<string, string> = { "Content-Type": "application/json" };
                                        if (token) docHeaders["Authorization"] = `Bearer ${token}`;
                                        if (csrfToken) docHeaders["X-CSRF-Token"] = csrfToken;
                                        const response = await fetch(
                                            `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/documents/${caseId}/export-word`,
                                            {
                                                method: "POST",
                                                headers: docHeaders,
                                                credentials: "include",
                                                body: JSON.stringify({
                                                    draft_id: activeDraftId,
                                                    jurisdiction,
                                                    attorney_info: { name: attorneyName, bar_number: barNumber },
                                                }),
                                            }
                                        );
                                        if (!response.ok) throw new Error("Export failed");
                                        const blob = await response.blob();
                                        const url = URL.createObjectURL(blob);
                                        const a = document.createElement("a");
                                        a.href = url;
                                        a.download = `${documentTitle.replace(/\s+/g, "_")}.docx`;
                                        a.click();
                                        URL.revokeObjectURL(url);
                                        toast.success("Word document exported");
                                    } catch {
                                        toast.error("Export failed");
                                    }
                                }}
                                disabled={!activeDraftId}
                            >
                                Export to Word (.docx)
                            </Button>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}
