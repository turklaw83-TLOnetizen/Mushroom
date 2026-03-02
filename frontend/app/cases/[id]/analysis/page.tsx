// ---- Analysis Tab (Full AI Pipeline Integration) ------------------------
// Connects to real backend analysis endpoints:
// - POST /cases/{id}/analysis/start -> starts bg_analysis
// - POST /cases/{id}/analysis/stop -> stops running analysis
// - GET  /cases/{id}/analysis/status -> progress polling (fallback)
// - POST /cases/{id}/analysis/ingestion/start -> document ingestion
//
// Features ported from Streamlit:
// - Prep selector with create/clone/rename/delete
// - Model selector + Max Context toggle
// - Node grid with per-node status badges
// - Attorney directives quick access
// - Module notes per tab
// - Re-analyze with module selection
//
// Primary progress source: WebSocket (500ms updates via use-worker-status).
// Falls back to HTTP polling only when WebSocket is disconnected.
"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { usePrep, type Preparation } from "@/hooks/use-prep";
import { useRole } from "@/hooks/use-role";
import { useWorkerStatus } from "@/hooks/use-worker-status";
import { useAnalysisProgress } from "@/hooks/use-analysis-progress";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { useKeyboardShortcuts } from "@/hooks/use-keyboard-shortcuts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// ---- Constants ----------------------------------------------------------

const MODEL_OPTIONS = [
    { value: "claude-opus-4.6", label: "Claude Opus 4.6", provider: "anthropic" },
    { value: "claude-sonnet-4.6", label: "Claude Sonnet 4.6", provider: "anthropic" },
    { value: "claude-sonnet-4.5", label: "Claude Sonnet 4.5", provider: "anthropic" },
    { value: "xai", label: "Grok (xAI)", provider: "xai" },
    { value: "gemini", label: "Gemini Pro", provider: "google" },
] as const;

const PREP_TYPES = [
    { value: "trial", label: "Trial Preparation", modules: 14 },
    { value: "prelim_hearing", label: "Preliminary Hearing", modules: 12 },
    { value: "motion_hearing", label: "Motion Hearing", modules: 7 },
] as const;

const analysisModules = [
    { key: "case_summary", label: "Case Summary", icon: "\u{1F4CB}", description: "Overall case narrative and key findings" },
    { key: "charges", label: "Charges Analysis", icon: "\u2696\uFE0F", description: "Charge elements, statutes, and defenses" },
    { key: "timeline", label: "Timeline", icon: "\u{1F4C5}", description: "Chronological sequence of events" },
    { key: "witnesses", label: "Witness Analysis", icon: "\u{1F464}", description: "Witness profiles, goals, and credibility" },
    { key: "evidence_foundations", label: "Evidence", icon: "\u{1F50D}", description: "Admissibility analysis and foundations" },
    { key: "legal_elements", label: "Legal Elements", icon: "\u{1F4DC}", description: "Elements of each charge and element-by-element analysis" },
    { key: "consistency_check", label: "Consistency Check", icon: "\u2713", description: "Cross-reference witness statements and evidence" },
    { key: "investigation_plan", label: "Investigation Plan", icon: "\u{1F52C}", description: "Action items for further investigation" },
    { key: "cross_examination_plan", label: "Cross Examination", icon: "\u2753", description: "Question strategies for opposing witnesses" },
    { key: "direct_examination_plan", label: "Direct Examination", icon: "\u{1F4AC}", description: "Question outlines for friendly witnesses" },
    { key: "strategy_notes", label: "Strategy", icon: "\u{1F3AF}", description: "Defense strategy recommendations" },
    { key: "devils_advocate_notes", label: "Devil's Advocate", icon: "\u{1F608}", description: "Prosecution's strongest arguments" },
    { key: "entities", label: "Entities", icon: "\u{1F3F7}\uFE0F", description: "People, places, and organizations mentioned" },
    { key: "voir_dire", label: "Voir Dire", icon: "\u{1F5F3}\uFE0F", description: "Jury selection strategy and questions" },
];

// ---- Helpers ------------------------------------------------------------

function statusColor(status: string): string {
    switch (status) {
        case "complete": return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
        case "running": return "bg-blue-500/15 text-blue-400 border-blue-500/30 animate-pulse";
        case "error": return "bg-red-500/15 text-red-400 border-red-500/30";
        default: return "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";
    }
}

function ProgressBar({ percent, label }: { percent: number; label?: string }) {
    return (
        <div className="space-y-1">
            {label && <p className="text-xs text-muted-foreground">{label}</p>}
            <div className="h-2 rounded-full bg-accent overflow-hidden">
                <div
                    className="h-full bg-gradient-to-r from-blue-500 to-emerald-500 transition-all duration-500 ease-out rounded-full"
                    style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
                />
            </div>
            <p className="text-xs text-muted-foreground text-right">{Math.round(percent)}%</p>
        </div>
    );
}

function ConnectionDot({ connected }: { connected: boolean }) {
    return (
        <span
            className={`inline-block w-2 h-2 rounded-full ${
                connected ? "bg-emerald-400" : "bg-zinc-500"
            }`}
            title={connected ? "WebSocket connected" : "WebSocket disconnected"}
        />
    );
}

// ---- Prep Management Dialog ---------------------------------------------

function PrepDialog({
    mode,
    caseId,
    sourcePrep,
    onClose,
}: {
    mode: "create" | "clone" | "rename";
    caseId: string;
    sourcePrep?: Preparation | null;
    onClose: () => void;
}) {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [name, setName] = useState(mode === "rename" && sourcePrep ? sourcePrep.name : "");
    const [prepType, setPrepType] = useState("trial");
    const [saving, setSaving] = useState(false);

    const handleSubmit = async () => {
        setSaving(true);
        try {
            if (mode === "create") {
                await api.post(`/cases/${caseId}/preparations`, {
                    prep_type: prepType,
                    name: name || PREP_TYPES.find(t => t.value === prepType)?.label || "New Preparation",
                }, { getToken });
                toast.success("Preparation created");
            } else if (mode === "clone" && sourcePrep) {
                await api.post(`/cases/${caseId}/preparations/${sourcePrep.id}/clone`, {
                    name: name || `${sourcePrep.name} (copy)`,
                }, { getToken });
                toast.success("Preparation cloned");
            } else if (mode === "rename" && sourcePrep) {
                await api.patch(`/cases/${caseId}/preparations/${sourcePrep.id}`, {
                    name,
                }, { getToken });
                toast.success("Preparation renamed");
            }
            queryClient.invalidateQueries({ queryKey: ["cases", caseId, "preparations"] });
            onClose();
        } catch (err) {
            toast.error(`Failed to ${mode} preparation`, {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
            <Card className="w-full max-w-md shadow-2xl" onClick={e => e.stopPropagation()}>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base">
                        {mode === "create" ? "New Preparation" : mode === "clone" ? "Clone Preparation" : "Rename Preparation"}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    {mode === "create" && (
                        <div className="space-y-1">
                            <label className="text-xs font-medium text-muted-foreground">Prep Type</label>
                            <select
                                value={prepType}
                                onChange={e => setPrepType(e.target.value)}
                                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            >
                                {PREP_TYPES.map(t => (
                                    <option key={t.value} value={t.value}>
                                        {t.label} ({t.modules} modules)
                                    </option>
                                ))}
                            </select>
                        </div>
                    )}
                    <div className="space-y-1">
                        <label className="text-xs font-medium text-muted-foreground">Name</label>
                        <input
                            type="text"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            placeholder={mode === "clone" ? `${sourcePrep?.name} (copy)` : "e.g. Trial Preparation"}
                            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                            autoFocus
                            onKeyDown={e => e.key === "Enter" && handleSubmit()}
                        />
                    </div>
                    <div className="flex gap-2 justify-end">
                        <Button size="sm" variant="ghost" onClick={onClose}>Cancel</Button>
                        <Button size="sm" onClick={handleSubmit} disabled={saving || (mode === "rename" && !name.trim())}>
                            {saving ? "Saving..." : mode === "create" ? "Create" : mode === "clone" ? "Clone" : "Rename"}
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

// ---- Attorney Directives Inline -----------------------------------------

function DirectivesPanel({ caseId }: { caseId: string }) {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [isEditing, setIsEditing] = useState(false);
    const [draft, setDraft] = useState("");

    const { data: directives } = useQuery({
        queryKey: ["cases", caseId, "directives"],
        queryFn: () => api.get<Array<{ id: string; text: string; category: string }>>(
            `/cases/${caseId}/directives`, { getToken }
        ),
    });

    const directivesList = Array.isArray(directives) ? directives : [];
    const combinedText = directivesList.map(d => d.text).join("\n\n");

    const handleSave = async () => {
        try {
            // Delete existing directives and create new one from combined text
            for (const d of directivesList) {
                await api.delete(`/cases/${caseId}/directives/${d.id}`, { getToken });
            }
            if (draft.trim()) {
                await api.post(`/cases/${caseId}/directives`, {
                    text: draft.trim(),
                    category: "instruction",
                }, { getToken });
            }
            queryClient.invalidateQueries({ queryKey: ["cases", caseId, "directives"] });
            toast.success("Directives saved");
            setIsEditing(false);
        } catch (err) {
            toast.error("Failed to save directives", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        }
    };

    return (
        <Card>
            <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center justify-between">
                    <span className="flex items-center gap-2">
                        Attorney Directives
                        <span className="text-xs font-normal text-muted-foreground">(injected into 13/14 analysis nodes)</span>
                    </span>
                    {!isEditing && (
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs"
                            onClick={() => { setDraft(combinedText); setIsEditing(true); }}
                        >
                            {combinedText ? "Edit" : "+ Add"}
                        </Button>
                    )}
                </CardTitle>
            </CardHeader>
            <CardContent>
                {isEditing ? (
                    <div className="space-y-2">
                        <textarea
                            value={draft}
                            onChange={e => setDraft(e.target.value)}
                            placeholder="Guide the AI's analysis: focus areas, case theory, specific witnesses to scrutinize, legal strategies to explore..."
                            className="w-full min-h-[100px] text-sm bg-muted border border-border rounded-md p-3 resize-y focus:outline-none focus:ring-1 focus:ring-primary"
                            autoFocus
                        />
                        <div className="flex gap-2">
                            <Button size="sm" onClick={handleSave}>Save</Button>
                            <Button size="sm" variant="ghost" onClick={() => setIsEditing(false)}>Cancel</Button>
                        </div>
                    </div>
                ) : combinedText ? (
                    <div className="text-sm bg-amber-500/10 border border-amber-500/20 rounded-md p-3 whitespace-pre-wrap max-h-32 overflow-auto">
                        {combinedText}
                    </div>
                ) : (
                    <p className="text-xs text-muted-foreground italic">
                        No directives set. Add strategic guidance to shape how the AI analyzes this case.
                    </p>
                )}
            </CardContent>
        </Card>
    );
}

// ---- Module Notes (persistent through re-analysis) ----------------------

function ModuleNotes({
    caseId,
    prepId,
    moduleKey,
}: {
    caseId: string;
    prepId: string;
    moduleKey: string;
}) {
    const { getToken } = useAuth();
    const [isEditing, setIsEditing] = useState(false);
    const [draft, setDraft] = useState("");

    const { data: noteData } = useQuery({
        queryKey: ["module-notes", caseId, prepId, moduleKey],
        queryFn: () =>
            api.get<{ module_name: string; content: string }>(
                `/cases/${caseId}/preparations/${prepId}/notes/${moduleKey}`,
                { getToken },
            ),
        enabled: !!prepId,
    });

    const saveNote = useMutationWithToast({
        mutationFn: () =>
            api.put(
                `/cases/${caseId}/preparations/${prepId}/notes/${moduleKey}`,
                { content: draft },
                { getToken },
            ),
        successMessage: "Note saved \u2014 will be used in next analysis",
        errorMessage: "Failed to save note",
        invalidateKeys: [["module-notes", caseId, prepId, moduleKey]],
        onSuccess: () => setIsEditing(false),
    });

    const noteContent = noteData?.content || "";

    return (
        <div className="border-t border-border mt-4 pt-4">
            <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-semibold text-muted-foreground">
                    Attorney Notes
                    <span className="text-xs font-normal ml-2">(persists through re-analysis, visible to AI)</span>
                </h4>
                {!isEditing && (
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => {
                            setDraft(noteContent);
                            setIsEditing(true);
                        }}
                    >
                        {noteContent ? "Edit" : "+ Add Note"}
                    </Button>
                )}
            </div>
            {isEditing ? (
                <div className="space-y-2">
                    <textarea
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        placeholder="Add corrections, context, or strategic guidance for this module. These notes will be injected into the AI context on the next analysis run."
                        className="w-full min-h-[100px] text-sm bg-muted border border-border rounded-md p-3 resize-y focus:outline-none focus:ring-1 focus:ring-primary"
                        autoFocus
                    />
                    <div className="flex gap-2">
                        <Button
                            size="sm"
                            onClick={() => saveNote.mutate({})}
                            disabled={saveNote.isPending}
                        >
                            {saveNote.isPending ? "Saving..." : "Save Note"}
                        </Button>
                        <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setIsEditing(false)}
                        >
                            Cancel
                        </Button>
                    </div>
                </div>
            ) : noteContent ? (
                <div className="text-sm bg-amber-500/10 border border-amber-500/20 rounded-md p-3 whitespace-pre-wrap">
                    {noteContent}
                </div>
            ) : (
                <p className="text-xs text-muted-foreground italic">
                    No notes. Add notes to guide AI analysis for this module.
                </p>
            )}
        </div>
    );
}

// ---- Module Detail Modal ------------------------------------------------

interface ModuleDetailProps {
    moduleKey: string;
    label: string;
    icon: string;
    description: string;
    data: unknown;
    caseId: string;
    prepId: string;
    onClose: () => void;
}

function ModuleDetail({ moduleKey, label, icon, description, data, caseId, prepId, onClose }: ModuleDetailProps) {
    const renderValue = (val: unknown): React.ReactNode => {
        if (val === null || val === undefined || val === "")
            return <p className="text-sm text-muted-foreground italic">Analysis not yet run for this module.</p>;

        if (typeof val === "string") {
            if (val.length === 0) return <p className="text-sm text-muted-foreground italic">Empty</p>;
            return <div className="text-sm leading-relaxed whitespace-pre-wrap">{val}</div>;
        }

        if (Array.isArray(val)) {
            if (val.length === 0) return <p className="text-sm text-muted-foreground italic">No items</p>;
            return (
                <div className="space-y-2">
                    {val.map((item, i) => (
                        <Card key={i} className="bg-accent/20 border-dashed">
                            <CardContent className="py-3">
                                {typeof item === "object" && item !== null ? (
                                    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
                                        {Object.entries(item as Record<string, unknown>).map(([k, v]) => (
                                            <div key={k} className="contents">
                                                <dt className="font-medium text-muted-foreground capitalize">{k.replace(/_/g, " ")}</dt>
                                                <dd>{String(v)}</dd>
                                            </div>
                                        ))}
                                    </dl>
                                ) : (
                                    <span className="text-sm">{String(item)}</span>
                                )}
                            </CardContent>
                        </Card>
                    ))}
                </div>
            );
        }

        if (typeof val === "object" && val !== null) {
            const obj = val as Record<string, unknown>;
            return (
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
                    {Object.entries(obj).map(([k, v]) => (
                        <div key={k} className="contents">
                            <dt className="font-medium text-muted-foreground capitalize">{k.replace(/_/g, " ")}</dt>
                            <dd className="whitespace-pre-wrap">{typeof v === "object" ? JSON.stringify(v, null, 2) : String(v)}</dd>
                        </div>
                    ))}
                </dl>
            );
        }

        return <p className="text-sm">{String(val)}</p>;
    };

    return (
        <div
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={onClose}
        >
            <Card
                className="w-full max-w-3xl max-h-[85vh] overflow-auto shadow-2xl"
                onClick={(e) => e.stopPropagation()}
            >
                <CardHeader className="flex flex-row items-start justify-between sticky top-0 bg-card z-10 border-b">
                    <div>
                        <CardTitle className="flex items-center gap-2 text-lg">
                            <span>{icon}</span> {label}
                        </CardTitle>
                        <p className="text-sm text-muted-foreground mt-1">{description}</p>
                    </div>
                    <Button variant="ghost" size="icon" onClick={onClose} className="shrink-0">{"\u2715"}</Button>
                </CardHeader>
                <CardContent className="pt-4">
                    {renderValue(data)}
                    {prepId && (
                        <ModuleNotes caseId={caseId} prepId={prepId} moduleKey={moduleKey} />
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

// ---- Main Page ----------------------------------------------------------

export default function AnalysisPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const { activePrepId, activePrep, preparations, setActivePrepId, isLoading: prepLoading } = usePrep();
    const { canEdit } = useRole();
    const { status: workerStatus, connected: wsConnected, reconnect, reconnectAttempts } = useWorkerStatus(caseId);
    const [selectedModule, setSelectedModule] = useState<string | null>(null);
    const [reanalyzeOpen, setReanalyzeOpen] = useState(false);
    const [selectedModules, setSelectedModules] = useState<Set<string>>(new Set());
    const [optionsOpen, setOptionsOpen] = useState(false);
    const [prepDialogMode, setPrepDialogMode] = useState<"create" | "clone" | "rename" | null>(null);
    const [prepMenuOpen, setPrepMenuOpen] = useState<string | null>(null);

    // ---- Model Selection & Max Context State (persisted in localStorage) ----
    const storageKey = `mc-analysis-opts-${caseId}`;
    const [selectedModel, setSelectedModel] = useState<string>(() => {
        if (typeof window === "undefined") return "claude-opus-4.6";
        try {
            const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
            return saved.model || "claude-opus-4.6";
        } catch { return "claude-opus-4.6"; }
    });
    const [maxContextMode, setMaxContextMode] = useState<boolean>(() => {
        if (typeof window === "undefined") return true;
        try {
            const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
            return saved.maxContext !== undefined ? saved.maxContext : true;
        } catch { return true; }
    });

    // Persist to localStorage when changed
    useEffect(() => {
        try {
            localStorage.setItem(storageKey, JSON.stringify({
                model: selectedModel,
                maxContext: maxContextMode,
            }));
        } catch { /* ignore */ }
    }, [selectedModel, maxContextMode, storageKey]);

    // Fetch API key configuration status
    const { data: apiKeyStatus } = useQuery({
        queryKey: ["config", "api-keys"],
        queryFn: () =>
            api.get<{ providers: Record<string, { configured: boolean }> }>(
                "/config/api-keys",
                { getToken },
            ),
        staleTime: 60_000,
    });

    // Determine which providers have API keys configured
    const configuredProviders = useMemo(() => {
        const providers = apiKeyStatus?.providers || {};
        return new Set(
            Object.entries(providers)
                .filter(([, v]) => v.configured)
                .map(([k]) => k),
        );
    }, [apiKeyStatus]);

    const isAnalysisRunning = workerStatus.analysis.status === "running";
    const isIngestionRunning = workerStatus.ingestion.status === "running";

    // Use WebSocket data as primary progress source.
    // Fall back to HTTP polling only when the WebSocket is disconnected.
    const usePollingFallback = isAnalysisRunning && !wsConnected;
    const { progress: polledProgress } = useAnalysisProgress(caseId, activePrepId, usePollingFallback);

    // Derive the progress data: prefer WebSocket, fall back to polling
    const progress = useMemo(() => {
        if (wsConnected && isAnalysisRunning) {
            const ws = workerStatus.analysis;
            return {
                status: ws.status as "idle" | "running" | "complete" | "error" | "stopping",
                progress: ws.progress ?? 0,
                current_module: ws.current_module ?? "",
                module_description: ws.module_description,
                error: ws.error ?? "",
                elapsed_seconds: ws.elapsed_seconds,
                completed_modules: ws.completed_modules,
                total_modules: ws.total_modules,
                tokens_used: ws.tokens_used,
            };
        }
        return polledProgress;
    }, [wsConnected, isAnalysisRunning, workerStatus.analysis, polledProgress]);

    // Load analysis state (the actual results)
    const stateQuery = useQuery({
        queryKey: ["cases", caseId, "prep-state", activePrepId],
        queryFn: () =>
            api.get<Record<string, unknown>>(
                `/cases/${caseId}/preparations/${activePrepId}`,
                { getToken },
            ),
        enabled: !!activePrepId,
        // Refetch when analysis completes
        refetchInterval: isAnalysisRunning ? 5000 : false,
    });

    const analysisState = stateQuery.data || {};

    // Count completed modules
    const completedCount = useMemo(() => {
        return analysisModules.filter((mod) => {
            const data = analysisState[mod.key];
            return data !== undefined && data !== null && data !== "" &&
                (Array.isArray(data) ? data.length > 0 : true);
        }).length;
    }, [analysisState]);

    // Build set of completed module keys from progress data
    const completedModuleKeys = useMemo(() => {
        return new Set(progress.completed_modules || []);
    }, [progress.completed_modules]);

    // Start Analysis mutation
    const startAnalysis = useMutationWithToast({
        mutationFn: () =>
            api.post(`/cases/${caseId}/analysis/start`, {
                prep_id: activePrepId,
                force_rerun: false,
                model: selectedModel,
                max_context_mode: maxContextMode,
            }, { getToken }),
        successMessage: "Analysis started \u2014 modules will update as they complete",
        errorMessage: "Failed to start analysis",
        onSuccess: () => reconnect(),
    });

    // Stop Analysis mutation
    const stopAnalysis = useMutationWithToast({
        mutationFn: () =>
            api.post(`/cases/${caseId}/analysis/stop?prep_id=${activePrepId}`, {}, { getToken }),
        successMessage: "Analysis stopping...",
        errorMessage: "Failed to stop analysis",
    });

    // Re-analyze (selected modules) mutation
    const startReanalyze = useMutationWithToast({
        mutationFn: () =>
            api.post(`/cases/${caseId}/analysis/start`, {
                prep_id: activePrepId,
                active_modules: [...selectedModules],
                force_rerun: true,
                model: selectedModel,
                max_context_mode: maxContextMode,
            }, { getToken }),
        successMessage: `Re-analysis started for ${selectedModules.size} module(s)`,
        errorMessage: "Failed to start re-analysis",
        onSuccess: () => {
            setReanalyzeOpen(false);
            reconnect();
        },
    });

    // Re-analyze panel helpers
    const openReanalyzePanel = useCallback(() => {
        const preChecked = new Set<string>();
        analysisModules.forEach((mod) => {
            const data = analysisState[mod.key];
            const hasData = data !== undefined && data !== null && data !== "" &&
                (Array.isArray(data) ? data.length > 0 : true);
            if (hasData) preChecked.add(mod.key);
        });
        setSelectedModules(preChecked);
        setReanalyzeOpen(true);
    }, [analysisState]);

    const toggleModule = useCallback((key: string) => {
        setSelectedModules((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
        });
    }, []);

    // Start Ingestion mutation
    const startIngestion = useMutationWithToast({
        mutationFn: () =>
            api.post(`/cases/${caseId}/analysis/ingestion/start`, {
                force_ocr: false,
            }, { getToken }),
        successMessage: "Document ingestion started",
        errorMessage: "Failed to start ingestion",
        onSuccess: () => reconnect(),
    });

    // Delete prep handler
    const handleDeletePrep = async (prepId: string) => {
        if (!confirm("Delete this preparation and all its analysis results? This cannot be undone.")) return;
        try {
            await api.delete(`/cases/${caseId}/preparations/${prepId}`, { getToken });
            queryClient.invalidateQueries({ queryKey: ["cases", caseId, "preparations"] });
            toast.success("Preparation deleted");
        } catch (err) {
            toast.error("Failed to delete preparation", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        }
    };

    // Keyboard shortcuts
    useKeyboardShortcuts({
        onEscape: () => {
            if (selectedModule) setSelectedModule(null);
            else if (prepDialogMode) setPrepDialogMode(null);
        },
    });

    const selectedMod = analysisModules.find((m) => m.key === selectedModule);

    // Sort preps newest first
    const sortedPreps = useMemo(() => {
        return [...preparations].sort((a, b) =>
            (b.created_at || "").localeCompare(a.created_at || "")
        );
    }, [preparations]);

    return (
        <div className="space-y-6">
            {/* ---- Preparation Selector ---- */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-base flex items-center justify-between">
                        <span>Preparation</span>
                        {canEdit && (
                            <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setPrepDialogMode("create")}>
                                + New Prep
                            </Button>
                        )}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {prepLoading ? (
                        <p className="text-sm text-muted-foreground">Loading preparations...</p>
                    ) : sortedPreps.length === 0 ? (
                        <p className="text-sm text-muted-foreground">
                            No preparations yet. Create one to start analysis.
                        </p>
                    ) : (
                        <div className="space-y-2">
                            <div className="flex items-center gap-3">
                                <select
                                    value={activePrepId || ""}
                                    onChange={e => setActivePrepId(e.target.value)}
                                    className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
                                >
                                    {sortedPreps.map(p => (
                                        <option key={p.id} value={p.id}>
                                            {p.name || p.id} ({PREP_TYPES.find(t => t.value === p.type)?.label || p.type})
                                        </option>
                                    ))}
                                </select>
                                {activePrep && canEdit && (
                                    <div className="relative">
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            className="h-8 w-8 p-0"
                                            onClick={() => setPrepMenuOpen(prepMenuOpen ? null : activePrep.id)}
                                        >
                                            {"\u22EE"}
                                        </Button>
                                        {prepMenuOpen === activePrep.id && (
                                            <div className="absolute right-0 top-full mt-1 z-10 w-36 rounded-md border border-border bg-popover shadow-md py-1">
                                                <button
                                                    className="w-full text-left px-3 py-1.5 text-sm hover:bg-accent transition-colors"
                                                    onClick={() => { setPrepMenuOpen(null); setPrepDialogMode("rename"); }}
                                                >
                                                    Rename
                                                </button>
                                                <button
                                                    className="w-full text-left px-3 py-1.5 text-sm hover:bg-accent transition-colors"
                                                    onClick={() => { setPrepMenuOpen(null); setPrepDialogMode("clone"); }}
                                                >
                                                    Clone
                                                </button>
                                                <button
                                                    className="w-full text-left px-3 py-1.5 text-sm text-red-400 hover:bg-accent transition-colors"
                                                    onClick={() => { setPrepMenuOpen(null); handleDeletePrep(activePrep.id); }}
                                                >
                                                    Delete
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                            {activePrep && (
                                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                    <Badge variant="outline" className="text-xs">
                                        {PREP_TYPES.find(t => t.value === activePrep.type)?.label || activePrep.type}
                                    </Badge>
                                    {activePrep.created_at && (
                                        <span>Created {new Date(activePrep.created_at).toLocaleDateString()}</span>
                                    )}
                                    {activePrep.last_updated && (
                                        <span>Updated {new Date(activePrep.last_updated).toLocaleDateString()}</span>
                                    )}
                                </div>
                            )}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* ---- Attorney Directives ---- */}
            <DirectivesPanel caseId={caseId} />

            {/* ---- AI Analysis Engine ---- */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center justify-between">
                        <span>AI Analysis Engine</span>
                        <div className="flex items-center gap-2">
                            <ConnectionDot connected={wsConnected} />
                            <Badge variant="outline" className={statusColor(workerStatus.analysis.status)}>
                                {workerStatus.analysis.status}
                            </Badge>
                            {!wsConnected && isAnalysisRunning && (
                                <span className="text-xs text-amber-400" title="Using HTTP polling as fallback">
                                    polling
                                </span>
                            )}
                            {reconnectAttempts > 0 && !wsConnected && (
                                <span className="text-xs text-zinc-500">
                                    retry {reconnectAttempts}/5
                                </span>
                            )}
                        </div>
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Progress Bar (visible while running) */}
                    {isAnalysisRunning && (
                        <div className="space-y-2">
                            <ProgressBar
                                percent={progress.progress * 100}
                                label={progress.current_module
                                    ? `${progress.module_description || progress.current_module}`
                                    : "Initializing..."
                                }
                            />
                            {progress.completed_modules && (
                                <p className="text-xs text-muted-foreground">
                                    {progress.completed_modules.length}/{progress.total_modules || "?"} modules complete
                                    {progress.tokens_used ? ` \u00B7 ${progress.tokens_used.toLocaleString()} tokens` : ""}
                                    {progress.elapsed_seconds != null ? ` \u00B7 ${Math.round(progress.elapsed_seconds)}s elapsed` : ""}
                                </p>
                            )}
                        </div>
                    )}

                    {/* Worker Status Row */}
                    <div className="flex gap-4 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1.5">
                            Ingestion: <Badge variant="outline" className={statusColor(workerStatus.ingestion.status)}>{workerStatus.ingestion.status}</Badge>
                        </span>
                        <span className="flex items-center gap-1.5">
                            OCR: <Badge variant="outline" className={statusColor(workerStatus.ocr.status)}>{workerStatus.ocr.status}</Badge>
                        </span>
                        <span className="text-xs ml-auto">
                            {completedCount}/{analysisModules.length} modules populated
                        </span>
                    </div>

                    {/* Analysis Options (Model + Max Context) */}
                    {canEdit && !isAnalysisRunning && (
                        <div className="space-y-2">
                            <button
                                onClick={() => setOptionsOpen(!optionsOpen)}
                                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                            >
                                <span className="text-[10px]">{optionsOpen ? "\u25BC" : "\u25B6"}</span>
                                Analysis Options
                            </button>
                            {optionsOpen && (
                                <div className="flex items-center gap-4 p-3 rounded-lg border border-border bg-accent/10">
                                    {/* Model Selector */}
                                    <div className="space-y-1">
                                        <label className="text-xs font-medium text-muted-foreground">AI Model</label>
                                        <select
                                            value={selectedModel}
                                            onChange={(e) => setSelectedModel(e.target.value)}
                                            className="w-48 rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                                        >
                                            {MODEL_OPTIONS.map((opt) => {
                                                const isConfigured = configuredProviders.has(opt.provider);
                                                return (
                                                    <option
                                                        key={opt.value}
                                                        value={opt.value}
                                                        disabled={!isConfigured}
                                                    >
                                                        {opt.label}{!isConfigured ? " (no API key)" : ""}
                                                    </option>
                                                );
                                            })}
                                        </select>
                                    </div>

                                    {/* Max Context Toggle */}
                                    <div className="space-y-1">
                                        <label className="text-xs font-medium text-muted-foreground">Context Window</label>
                                        <label
                                            className="flex items-center gap-2 cursor-pointer"
                                            title="Send ALL document text without truncation. Enables 1M token context for Opus/Sonnet 4.6."
                                        >
                                            <button
                                                type="button"
                                                role="switch"
                                                aria-checked={maxContextMode}
                                                onClick={() => setMaxContextMode(!maxContextMode)}
                                                className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border-2 border-transparent transition-colors ${
                                                    maxContextMode ? "bg-primary" : "bg-zinc-600"
                                                }`}
                                            >
                                                <span
                                                    className={`pointer-events-none inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform ${
                                                        maxContextMode ? "translate-x-4" : "translate-x-0.5"
                                                    }`}
                                                />
                                            </button>
                                            <span className="text-sm">
                                                Max Context
                                                {maxContextMode ? " (1M tokens)" : " (off)"}
                                            </span>
                                        </label>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Action Buttons */}
                    {canEdit && (
                        <div className="flex gap-2 pt-1">
                            {!activePrepId && !prepLoading ? (
                                <p className="text-sm text-muted-foreground">
                                    No preparations found. Create one to run analysis.
                                </p>
                            ) : (
                                <>
                                    {!isAnalysisRunning ? (
                                        <>
                                            <Button
                                                size="sm"
                                                onClick={() => startAnalysis.mutate({})}
                                                disabled={startAnalysis.isPending || !activePrepId}
                                            >
                                                {startAnalysis.isPending ? "Starting..." : "\u25B6 Run Analysis"}
                                            </Button>
                                            {activePrepId && (
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={openReanalyzePanel}
                                                    disabled={startReanalyze.isPending}
                                                >
                                                    {reanalyzeOpen ? "\u25BC Re-analyze" : "\u25B6 Re-analyze"}
                                                </Button>
                                            )}
                                        </>
                                    ) : (
                                        <Button
                                            size="sm"
                                            variant="destructive"
                                            onClick={() => stopAnalysis.mutate({})}
                                            disabled={stopAnalysis.isPending}
                                        >
                                            {stopAnalysis.isPending ? "Stopping..." : "\u23F9 Stop"}
                                        </Button>
                                    )}

                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => startIngestion.mutate({})}
                                        disabled={isIngestionRunning || startIngestion.isPending}
                                    >
                                        {isIngestionRunning ? "Ingesting..." : startIngestion.isPending ? "Starting..." : "\u{1F4E5} Ingest Documents"}
                                    </Button>
                                </>
                            )}
                        </div>
                    )}

                    {/* Re-analyze Module Selector Panel */}
                    {reanalyzeOpen && canEdit && (
                        <div className="border border-border rounded-lg p-4 bg-accent/10 space-y-3">
                            <div className="flex items-center justify-between">
                                <h4 className="text-sm font-semibold">Select modules to re-analyze</h4>
                                <div className="flex items-center gap-2">
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-7 text-xs"
                                        onClick={() =>
                                            setSelectedModules(new Set(analysisModules.map((m) => m.key)))
                                        }
                                    >
                                        Select All
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="h-7 text-xs"
                                        onClick={() => setSelectedModules(new Set())}
                                    >
                                        Deselect All
                                    </Button>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                                {analysisModules.map((mod) => {
                                    const data = analysisState[mod.key];
                                    const hasData = data !== undefined && data !== null && data !== "" &&
                                        (Array.isArray(data) ? data.length > 0 : true);
                                    return (
                                        <label
                                            key={mod.key}
                                            className={`flex items-center gap-2 text-sm p-2 rounded-md cursor-pointer transition-colors ${
                                                selectedModules.has(mod.key)
                                                    ? "bg-primary/10 border border-primary/30"
                                                    : "bg-accent/20 border border-transparent hover:bg-accent/40"
                                            }`}
                                        >
                                            <input
                                                type="checkbox"
                                                checked={selectedModules.has(mod.key)}
                                                onChange={() => toggleModule(mod.key)}
                                                className="rounded border-border accent-primary"
                                            />
                                            <span>{mod.icon}</span>
                                            <span className="truncate">{mod.label}</span>
                                            {hasData && (
                                                <span className="ml-auto text-xs text-emerald-400 shrink-0">
                                                    {"\u2713"}
                                                </span>
                                            )}
                                        </label>
                                    );
                                })}
                            </div>
                            <div className="flex items-center gap-2 pt-1">
                                <Button
                                    size="sm"
                                    onClick={() => startReanalyze.mutate({})}
                                    disabled={selectedModules.size === 0 || startReanalyze.isPending}
                                >
                                    {startReanalyze.isPending
                                        ? "Starting..."
                                        : `\u25B6 Run Selected (${selectedModules.size})`}
                                </Button>
                                <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => setReanalyzeOpen(false)}
                                >
                                    Cancel
                                </Button>
                                <span className="text-xs text-muted-foreground ml-auto">
                                    {selectedModules.size} of {analysisModules.length} selected
                                </span>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* ---- Module Grid ---- */}
            <div>
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                    Analysis Modules ({completedCount}/{analysisModules.length})
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                    {analysisModules.map((mod) => {
                        const data = analysisState[mod.key];
                        const hasData = data !== undefined && data !== null && data !== "" &&
                            (Array.isArray(data) ? data.length > 0 : true);
                        const isCurrentlyProcessing = isAnalysisRunning && progress.current_module === mod.key;
                        const wasCompletedThisRun = completedModuleKeys.has(mod.key);

                        return (
                            <Card
                                key={mod.key}
                                className={`transition-all cursor-pointer hover:bg-accent/30 hover:shadow-md ${isCurrentlyProcessing
                                        ? "border-blue-500/50 shadow-blue-500/10 shadow-md animate-pulse"
                                        : hasData
                                            ? "border-emerald-500/20"
                                            : "border-dashed opacity-60 hover:opacity-100"
                                    }`}
                                onClick={() => setSelectedModule(mod.key)}
                            >
                                <CardContent className="py-4">
                                    <div className="flex items-center gap-2 mb-1">
                                        <span>{mod.icon}</span>
                                        <span className="text-sm font-medium">{mod.label}</span>
                                        {isCurrentlyProcessing && (
                                            <Badge variant="outline" className="ml-auto text-[10px] bg-blue-500/15 text-blue-400 border-blue-500/30 animate-pulse">
                                                running
                                            </Badge>
                                        )}
                                        {!isCurrentlyProcessing && wasCompletedThisRun && isAnalysisRunning && (
                                            <Badge variant="outline" className="ml-auto text-[10px] bg-emerald-500/15 text-emerald-400 border-emerald-500/30">
                                                done
                                            </Badge>
                                        )}
                                        {hasData && !isCurrentlyProcessing && !isAnalysisRunning && (
                                            <span className="ml-auto text-xs text-emerald-400">{"\u2713"}</span>
                                        )}
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        {isCurrentlyProcessing
                                            ? progress.module_description || "Processing..."
                                            : hasData
                                                ? Array.isArray(data)
                                                    ? `${(data as unknown[]).length} items`
                                                    : typeof data === "string"
                                                        ? `${data.length.toLocaleString()} chars`
                                                        : "Data available"
                                                : mod.description}
                                    </p>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            </div>

            {/* ---- Module Detail Modal ---- */}
            {selectedMod && (
                <ModuleDetail
                    moduleKey={selectedMod.key}
                    label={selectedMod.label}
                    icon={selectedMod.icon}
                    description={selectedMod.description}
                    data={analysisState[selectedMod.key]}
                    caseId={caseId}
                    prepId={activePrepId || ""}
                    onClose={() => setSelectedModule(null)}
                />
            )}

            {/* ---- Prep Management Dialog ---- */}
            {prepDialogMode && (
                <PrepDialog
                    mode={prepDialogMode}
                    caseId={caseId}
                    sourcePrep={activePrep}
                    onClose={() => setPrepDialogMode(null)}
                />
            )}
        </div>
    );
}
