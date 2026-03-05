// ---- Prep State Hook -----------------------------------------------------
// Central hook for accessing AI analysis results from the prep state.
// All analysis result tabs share this cached query.
"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";

// ---- Types for analysis results ------------------------------------------

export interface ConsistencyItem {
    fact: string;
    source_a: string;
    source_b: string;
    statement_a: string;
    statement_b: string;
    severity?: string;
    _ai_suggests_remove?: boolean;
}

export interface InvestigationItem {
    action: string;
    priority: string;
    rationale: string;
    assigned_to?: string;
    status?: string;
    _ai_suggests_remove?: boolean;
}

export interface EntityItem {
    name: string;
    type: string;
    role?: string;
    mentions?: number;
    context?: string;
}

export interface ElementItem {
    element: string;
    charge?: string;
    statute?: string;
    evidence_for?: string[];
    evidence_against?: string[];
    strength?: string;
    notes?: string;
}

export interface EvidenceFoundation {
    item: string;
    foundation: string;
    admissibility: string;
    objections?: string[];
    notes?: string;
    _ai_suggests_remove?: boolean;
}

export interface TimelineEvent {
    date: string;
    description: string;
    source?: string;
    significance?: string;
    _ai_suggests_remove?: boolean;
}

export interface WitnessExamPlan {
    [witnessName: string]: string | Record<string, unknown>;
}

export interface ReadinessScore {
    overall_score?: number;
    grade?: string;
    categories?: Record<string, { score: number; notes: string }>;
}

// The full prep state shape (partial — only the keys we need)
export interface PrepState {
    case_summary?: string;
    devils_advocate_notes?: string;
    strategy_notes?: string;
    investigation_plan?: InvestigationItem[];
    consistency_check?: ConsistencyItem[];
    elements_map?: ElementItem[];
    entities?: EntityItem[];
    evidence_foundations?: EvidenceFoundation[];
    timeline?: TimelineEvent[];
    cross_examination_plan?: WitnessExamPlan;
    direct_examination_plan?: WitnessExamPlan;
    voir_dire?: string | Record<string, unknown>;
    mock_jury?: string | Record<string, unknown>;
    legal_research?: string;
    cheat_sheet?: string;
    readiness_score?: number | ReadinessScore;
    witnesses?: Array<Record<string, unknown>>;
    [key: string]: unknown;
}

// ---- Hook ----------------------------------------------------------------

export function usePrepState(caseId: string, prepId: string | null, opts?: { refetchInterval?: number | false }) {
    const { getToken } = useAuth();

    const query = useQuery({
        queryKey: ["cases", caseId, "prep-state", prepId],
        queryFn: () =>
            api.get<PrepState>(
                `/cases/${caseId}/preparations/${prepId}`,
                { getToken },
            ),
        enabled: !!prepId,
        refetchInterval: opts?.refetchInterval,
    });

    const state = query.data ?? ({} as PrepState);

    const sections = useMemo(() => ({
        caseSummary: state.case_summary ?? null,
        devilsAdvocate: state.devils_advocate_notes ?? null,
        strategyNotes: state.strategy_notes ?? null,
        investigationPlan: (state.investigation_plan ?? []) as InvestigationItem[],
        consistencyCheck: (state.consistency_check ?? []) as ConsistencyItem[],
        elementsMap: (state.elements_map ?? []) as ElementItem[],
        entities: (state.entities ?? []) as EntityItem[],
        evidenceFoundations: (state.evidence_foundations ?? []) as EvidenceFoundation[],
        timelineEvents: (state.timeline ?? []) as TimelineEvent[],
        crossExamPlan: (state.cross_examination_plan ?? {}) as WitnessExamPlan,
        directExamPlan: (state.direct_examination_plan ?? {}) as WitnessExamPlan,
        voirDire: state.voir_dire ?? null,
        mockJury: state.mock_jury ?? null,
        legalResearch: state.legal_research ?? null,
        cheatSheet: state.cheat_sheet ?? null,
        readinessScore: state.readiness_score ?? null,
    }), [state]);

    return {
        state,
        sections,
        isLoading: query.isLoading,
        isError: query.isError,
        refetch: query.refetch,
    };
}
