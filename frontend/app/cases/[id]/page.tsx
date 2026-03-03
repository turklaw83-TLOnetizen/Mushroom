// ---- Case Overview Page -------------------------------------------------
// Shows case metadata, phase management, attorney directives, and exports.
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { useCase, type CaseItem } from "@/hooks/use-cases";
import { api } from "@/lib/api-client";
import { ExportPanel } from "@/components/export-panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

// ---- Sub-phase config per case type (matches data/phase_config.json) ----
const SUB_PHASES: Record<string, string[]> = {
    criminal: [
        "Intake", "Arraignment/Bond", "Discovery", "Pre-Trial Motions",
        "Plea Negotiation", "Trial Prep", "Trial", "Sentencing", "Appeal",
    ],
    "criminal-juvenile": [
        "Intake", "Detention Hearing", "Discovery", "Pre-Adjudication Motions",
        "Diversion/Plea", "Adjudication", "Disposition", "Post-Disposition",
    ],
    "civil-plaintiff": [
        "Intake", "Pre-Litigation/Demand", "Filing/Pleadings", "Discovery",
        "Mediation/ADR", "Pre-Trial Motions", "Trial Prep", "Trial", "Post-Trial/Collection",
    ],
    "civil-defendant": [
        "Intake", "Answer/Responsive Pleadings", "Discovery", "Mediation/ADR",
        "Pre-Trial Motions", "Trial Prep", "Trial", "Post-Trial",
    ],
    "civil-juvenile": [
        "Intake", "Petition Filed", "Discovery/Investigation", "Mediation",
        "Hearing Prep", "Hearing", "Post-Hearing",
    ],
};

const PHASES = ["active", "closed", "archived"] as const;

const phaseColors: Record<string, string> = {
    active: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    closed: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    archived: "bg-amber-500/15 text-amber-400 border-amber-500/30",
};

// ---- Phase Management Component ----------------------------------------

function PhaseManager({ caseData, caseId }: { caseData: CaseItem; caseId: string }) {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [isUpdating, setIsUpdating] = useState(false);

    const caseType = caseData.case_type || "criminal";
    // Match the sub-phases key: criminal, civil-plaintiff, etc.
    const subPhaseKey =
        SUB_PHASES[caseType]
            ? caseType
            : SUB_PHASES[`${caseData.case_category}`]
                ? caseData.case_category
                : Object.keys(SUB_PHASES).find((k) => caseType.toLowerCase().includes(k.split("-")[0]))
                    || "criminal";
    const availableSubPhases = SUB_PHASES[subPhaseKey] || [];

    const setPhase = async (phase: string, subPhase: string = "") => {
        setIsUpdating(true);
        try {
            await api.post(`/cases/${caseId}/phase`, { phase, sub_phase: subPhase }, { getToken });
            queryClient.invalidateQueries({ queryKey: ["cases", caseId] });
            toast.success(`Phase updated to ${phase}${subPhase ? ` / ${subPhase}` : ""}`);
        } catch (err) {
            toast.error("Failed to update phase", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        } finally {
            setIsUpdating(false);
        }
    };

    const currentPhase = caseData.phase || "active";
    const currentSubPhase = caseData.sub_phase || "";

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                    Phase Management
                    <Badge variant="outline" className={phaseColors[currentPhase] || phaseColors.active}>
                        {currentPhase}
                        {currentSubPhase && ` / ${currentSubPhase}`}
                    </Badge>
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Phase Transition Buttons */}
                <div className="flex flex-wrap gap-2">
                    {PHASES.map((phase) => (
                        <Button
                            key={phase}
                            size="sm"
                            variant={currentPhase === phase ? "default" : "outline"}
                            disabled={isUpdating || currentPhase === phase}
                            onClick={() => setPhase(phase, phase === "active" ? currentSubPhase : "")}
                            className="capitalize"
                        >
                            {phase === "active" && currentPhase !== "active" ? "Reopen" : phase}
                        </Button>
                    ))}
                </div>

                {/* Sub-phase Selector (only when active) */}
                {currentPhase === "active" && availableSubPhases.length > 0 && (
                    <div>
                        <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">
                            Sub-Phase
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                            {availableSubPhases.map((sp) => (
                                <Button
                                    key={sp}
                                    size="sm"
                                    variant={currentSubPhase === sp ? "default" : "outline"}
                                    className="h-7 text-xs"
                                    disabled={isUpdating}
                                    onClick={() => setPhase("active", sp)}
                                >
                                    {sp}
                                </Button>
                            ))}
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

// ---- Main Page ----------------------------------------------------------

export default function CaseOverviewPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { data: caseData, isLoading } = useCase(caseId);

    if (isLoading) {
        return (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-32 rounded-lg" />
                ))}
            </div>
        );
    }

    if (!caseData) {
        return (
            <div className="text-center py-16 text-muted-foreground">
                Case not found.
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Metadata Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <MetricCard label="Type" value={caseData.case_type || "—"} />
                <MetricCard label="Category" value={caseData.case_category || "—"} />
                <MetricCard label="Client" value={caseData.client_name || "—"} />
                <MetricCard label="Jurisdiction" value={caseData.jurisdiction || "—"} />
                <MetricCard label="Status" value={caseData.status || "active"} />
                <MetricCard
                    label="Last Updated"
                    value={caseData.last_updated
                        ? new Date(caseData.last_updated).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
                        : "—"
                    }
                />
            </div>

            {/* Description */}
            {caseData.description && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Description</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                            {caseData.description}
                        </p>
                    </CardContent>
                </Card>
            )}

            {/* Phase Management */}
            <PhaseManager caseData={caseData} caseId={caseId} />

            {/* Export Panel */}
            <ExportPanel caseId={caseId} />
        </div>
    );
}

function MetricCard({ label, value }: { label: string; value: string }) {
    return (
        <Card>
            <CardContent className="pt-4 pb-3">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    {label}
                </p>
                <p className="text-lg font-semibold mt-1 truncate">{value}</p>
            </CardContent>
        </Card>
    );
}
