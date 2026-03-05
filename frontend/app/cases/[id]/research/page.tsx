// ---- Research Tab (with sub-tabs for analysis results) -------------------
// Sub-tabs: Notes | Legal Research | Cheat Sheet
"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { usePrep } from "@/hooks/use-prep";
import { usePrepState } from "@/hooks/use-prep-state";
import { ResultSection } from "@/components/analysis/result-section";
import { MarkdownContent } from "@/components/analysis/markdown-content";
import { DataPage } from "@/components/shared/data-page";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { GenerateButton } from "@/components/analysis/generate-button";
import { ModuleNotes } from "@/components/shared/module-notes";

interface ResearchItem {
    topic: string;
    summary: string;
    source: string;
    citations: string[];
}

export default function ResearchPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, isLoading: prepLoading } = usePrep();

    // Research items from dedicated endpoint
    const query = useQuery({
        queryKey: ["research", caseId, activePrepId],
        queryFn: () =>
            api.get<ResearchItem[]>(`/documents/research/${caseId}/${activePrepId}`, { getToken }),
        enabled: !!activePrepId,
    });

    // Full prep state for legal research and cheat sheet
    const { sections, isLoading: stateLoading } = usePrepState(caseId, activePrepId);

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">Create a preparation first to view research.</p>
            </div>
        );
    }

    return (
        <Tabs defaultValue="notes" className="space-y-4">
            <TabsList variant="line">
                <TabsTrigger value="notes">
                    Notes {query.data?.length ? <span className="ml-1 text-emerald-400" aria-hidden="true">●</span> : null}
                </TabsTrigger>
                <TabsTrigger value="legal-research">
                    Legal Research {sections.legalResearch && <span className="ml-1 text-emerald-400" aria-hidden="true">●</span>}
                </TabsTrigger>
                <TabsTrigger value="cheat-sheet">
                    Cheat Sheet {sections.cheatSheet && <span className="ml-1 text-emerald-400" aria-hidden="true">●</span>}
                </TabsTrigger>
            </TabsList>

            {/* ---- Research Notes Tab ---- */}
            <TabsContent value="notes">
                <DataPage
                    title="Research Notes"
                    subtitle="Research data, case law, and citations"
                    query={query}
                    searchFilter={(r, s) =>
                        r.topic?.toLowerCase().includes(s) || r.summary?.toLowerCase().includes(s)
                    }
                    searchPlaceholder="Search research..."
                    createLabel={null}
                    renderItem={(item, i) => (
                        <Card key={i} className="hover:bg-accent/30 transition-colors">
                            <CardContent className="py-3">
                                <p className="font-medium text-sm">{item.topic || `Research Item ${i + 1}`}</p>
                                {item.summary && (
                                    <p className="text-xs text-muted-foreground mt-1 line-clamp-3">{item.summary}</p>
                                )}
                                {item.source && (
                                    <p className="text-xs text-muted-foreground mt-1">Source: {item.source}</p>
                                )}
                            </CardContent>
                        </Card>
                    )}
                />
            </TabsContent>

            {/* ---- Legal Research Tab ---- */}
            <TabsContent value="legal-research">
                <ResultSection
                    title="Legal Research"
                    icon="📚"
                    isEmpty={!sections.legalResearch}
                    isLoading={stateLoading}
                    emptyMessage="Run analysis to generate legal research with case law citations and statutory analysis."
                >
                    {sections.legalResearch && (
                        <MarkdownContent content={sections.legalResearch} />
                    )}
                </ResultSection>
                <ModuleNotes caseId={caseId} prepId={activePrepId} moduleKey="legal_research" />
            </TabsContent>

            {/* ---- Cheat Sheet Tab ---- */}
            <TabsContent value="cheat-sheet">
                {sections.cheatSheet ? (
                    <ResultSection
                        title="Cheat Sheet"
                        icon="📋"
                        isEmpty={false}
                        isLoading={stateLoading}
                    >
                        <MarkdownContent content={sections.cheatSheet} />
                    </ResultSection>
                ) : (
                    <GenerateButton
                        caseId={caseId}
                        prepId={activePrepId}
                        endpoint="cheat-sheet"
                        label="Cheat Sheet"
                        icon="📋"
                        resultKey="cheat_sheet"
                        emptyMessage="Generate a quick-reference cheat sheet with key facts, citations, and courtroom reminders."
                    />
                )}
                <ModuleNotes caseId={caseId} prepId={activePrepId} moduleKey="cheat_sheet" />
            </TabsContent>
        </Tabs>
    );
}
