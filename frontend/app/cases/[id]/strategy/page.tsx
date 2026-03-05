// ---- Strategy Tab (with sub-tabs for analysis results) -------------------
// Sub-tabs: Strategy | Devil's Advocate | Voir Dire | Mock Jury
"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { usePrep } from "@/hooks/use-prep";
import { usePrepState } from "@/hooks/use-prep-state";
import { ResultSection } from "@/components/analysis/result-section";
import { MarkdownContent } from "@/components/analysis/markdown-content";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { GenerateButton, GenerateWithInput } from "@/components/analysis/generate-button";
import { ModuleNotes } from "@/components/shared/module-notes";

interface StrategyData {
    strategy_notes: string;
    devils_advocate_notes: string;
    voir_dire: Record<string, unknown>;
    mock_jury_feedback: Array<Record<string, unknown>>;
}

// ---- Helpers for rendering complex data ----------------------------------

function renderVoirDireContent(data: string | Record<string, unknown>) {
    if (typeof data === "string") {
        return <MarkdownContent content={data} />;
    }

    // Structured voir dire data
    return (
        <div className="space-y-4">
            {Object.entries(data).map(([key, value]) => (
                <div key={key}>
                    <h4 className="text-sm font-semibold capitalize mb-2">{key.replace(/_/g, " ")}</h4>
                    {typeof value === "string" ? (
                        <p className="text-sm text-muted-foreground whitespace-pre-wrap">{value}</p>
                    ) : Array.isArray(value) ? (
                        <ul className="space-y-1">
                            {value.map((item, i) => (
                                <li key={i} className="text-sm text-muted-foreground">
                                    {typeof item === "string" ? `• ${item}` : `• ${JSON.stringify(item)}`}
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <pre className="text-xs bg-muted p-2 rounded overflow-auto">
                            {JSON.stringify(value, null, 2)}
                        </pre>
                    )}
                </div>
            ))}
        </div>
    );
}

function renderMockJuryContent(data: string | Record<string, unknown> | Array<Record<string, unknown>>) {
    if (typeof data === "string") {
        return <MarkdownContent content={data} />;
    }

    if (Array.isArray(data)) {
        if (data.length === 0) return null;
        return (
            <div className="space-y-3">
                {data.map((juror, i) => (
                    <Card key={i} className="bg-accent/20">
                        <CardContent className="py-3">
                            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
                                {Object.entries(juror).map(([key, value]) => (
                                    <div key={key} className="contents">
                                        <dt className="font-medium text-muted-foreground capitalize text-xs">
                                            {key.replace(/_/g, " ")}
                                        </dt>
                                        <dd className="whitespace-pre-wrap">
                                            {typeof value === "object" ? JSON.stringify(value) : String(value)}
                                        </dd>
                                    </div>
                                ))}
                            </dl>
                        </CardContent>
                    </Card>
                ))}
            </div>
        );
    }

    // Single object
    return (
        <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-96">
            {JSON.stringify(data, null, 2)}
        </pre>
    );
}

// ---- Main Page ----------------------------------------------------------

export default function StrategyPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, isLoading: prepLoading } = usePrep();

    // Strategy-specific endpoint data
    const { data, isLoading } = useQuery({
        queryKey: ["strategy", caseId, activePrepId],
        queryFn: () =>
            api.get<StrategyData>(
                `/cases/${caseId}/preparations/${activePrepId}/strategy`,
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    // Full prep state for additional analysis results
    const { state: analysisState, sections, isLoading: stateLoading } = usePrepState(caseId, activePrepId);

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">Create a preparation first to manage strategy.</p>
            </div>
        );
    }

    if (isLoading && stateLoading) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-10 w-80" />
                <Skeleton className="h-40 rounded-lg" />
                <Skeleton className="h-40 rounded-lg" />
            </div>
        );
    }

    // On-demand generated content from prep state
    const opponentPlaybook = (analysisState.opponent_playbook as string) ?? null;
    const clientReport = (analysisState.client_report as string) ?? null;

    // Merge data sources — strategy endpoint and prep state
    const strategyNotes = data?.strategy_notes || sections.strategyNotes;
    const devilsAdvocate = data?.devils_advocate_notes || sections.devilsAdvocate;
    const voirDire = data?.voir_dire || sections.voirDire;
    const mockJury = data?.mock_jury_feedback || sections.mockJury;

    const hasVoirDire = voirDire && (
        typeof voirDire === "string" ? voirDire.length > 0 : Object.keys(voirDire).length > 0
    );
    const hasMockJury = mockJury && (
        typeof mockJury === "string" ? (mockJury as string).length > 0
            : Array.isArray(mockJury) ? mockJury.length > 0
                : Object.keys(mockJury).length > 0
    );

    return (
        <Tabs defaultValue="strategy" className="space-y-4">
            <TabsList variant="line">
                <TabsTrigger value="strategy">
                    Strategy {strategyNotes && <span className="ml-1 text-emerald-400" aria-hidden="true">●</span>}
                </TabsTrigger>
                <TabsTrigger value="devils-advocate">
                    Devil&apos;s Advocate {devilsAdvocate && <span className="ml-1 text-emerald-400" aria-hidden="true">●</span>}
                </TabsTrigger>
                <TabsTrigger value="voir-dire">
                    Voir Dire {hasVoirDire && <span className="ml-1 text-emerald-400" aria-hidden="true">●</span>}
                </TabsTrigger>
                <TabsTrigger value="mock-jury">
                    Mock Jury {hasMockJury && <span className="ml-1 text-emerald-400" aria-hidden="true">●</span>}
                </TabsTrigger>
                <TabsTrigger value="opponent">
                    Opponent {opponentPlaybook && <span className="ml-1 text-emerald-400" aria-hidden="true">●</span>}
                </TabsTrigger>
                <TabsTrigger value="client-report">
                    Client Report {clientReport && <span className="ml-1 text-emerald-400" aria-hidden="true">●</span>}
                </TabsTrigger>
                <TabsTrigger value="statements">Statements</TabsTrigger>
            </TabsList>

            {/* ---- Strategy Notes Tab ---- */}
            <TabsContent value="strategy">
                <ResultSection
                    title="Strategy Notes"
                    icon="🎯"
                    isEmpty={!strategyNotes}
                    isLoading={isLoading}
                    emptyMessage="No strategy notes yet. Run analysis to generate strategy recommendations."
                >
                    {typeof strategyNotes === "string" && (
                        <MarkdownContent content={strategyNotes} />
                    )}
                </ResultSection>
                <ModuleNotes caseId={caseId} prepId={activePrepId} moduleKey="strategy" />
            </TabsContent>

            {/* ---- Devil's Advocate Tab ---- */}
            <TabsContent value="devils-advocate">
                <ResultSection
                    title="Devil's Advocate"
                    icon="😈"
                    isEmpty={!devilsAdvocate}
                    isLoading={isLoading}
                    emptyMessage="No devil's advocate analysis yet. Run analysis to see the prosecution's strongest arguments."
                >
                    {typeof devilsAdvocate === "string" && (
                        <MarkdownContent content={devilsAdvocate} />
                    )}
                </ResultSection>
                <ModuleNotes caseId={caseId} prepId={activePrepId} moduleKey="devils_advocate" />
            </TabsContent>

            {/* ---- Voir Dire Tab ---- */}
            <TabsContent value="voir-dire">
                <ResultSection
                    title="Voir Dire"
                    icon="🗳️"
                    isEmpty={!hasVoirDire}
                    isLoading={stateLoading}
                    emptyMessage="No voir dire data yet. Run analysis to generate jury selection strategy."
                >
                    {voirDire && renderVoirDireContent(voirDire as string | Record<string, unknown>)}
                </ResultSection>
            </TabsContent>

            {/* ---- Mock Jury Tab ---- */}
            <TabsContent value="mock-jury">
                <ResultSection
                    title="Mock Jury Feedback"
                    icon="👥"
                    isEmpty={!hasMockJury}
                    isLoading={stateLoading}
                    emptyMessage="No mock jury feedback yet. Run analysis to simulate jury deliberation."
                >
                    {mockJury && renderMockJuryContent(mockJury as string | Record<string, unknown> | Array<Record<string, unknown>>)}
                </ResultSection>
                <ModuleNotes caseId={caseId} prepId={activePrepId} moduleKey="mock_jury" />
            </TabsContent>

            {/* ---- Opponent Playbook Tab ---- */}
            <TabsContent value="opponent">
                <GenerateButton
                    caseId={caseId}
                    prepId={activePrepId}
                    endpoint="opponent-playbook"
                    label="Opponent Playbook"
                    icon="🎭"
                    existingContent={opponentPlaybook}
                    resultKey="opponent_playbook"
                    emptyMessage="Generate a prediction of opposing counsel's likely strategy, arguments, and tactics."
                />
                <ModuleNotes caseId={caseId} prepId={activePrepId} moduleKey="opponent_playbook" />
            </TabsContent>

            {/* ---- Client Report Tab ---- */}
            <TabsContent value="client-report">
                <GenerateButton
                    caseId={caseId}
                    prepId={activePrepId}
                    endpoint="client-report"
                    label="Client Report"
                    icon="📄"
                    existingContent={clientReport}
                    resultKey="client_report"
                    emptyMessage="Generate a plain-language case report suitable for sharing with your client."
                />
                <ModuleNotes caseId={caseId} prepId={activePrepId} moduleKey="client_report" />
            </TabsContent>

            {/* ---- Statements Tab ---- */}
            <TabsContent value="statements">
                <GenerateWithInput
                    caseId={caseId}
                    prepId={activePrepId}
                    endpoint="statements"
                    label="Statement"
                    icon="🎤"
                    resultKey="statement"
                    emptyMessage="Generate a draft opening or closing statement tailored to your case."
                    fields={[
                        {
                            key: "statement_type",
                            label: "Statement Type",
                            type: "select",
                            options: [
                                { value: "opening", label: "Opening Statement" },
                                { value: "closing", label: "Closing Statement" },
                            ],
                        },
                        {
                            key: "tone",
                            label: "Tone",
                            type: "select",
                            options: [
                                { value: "measured", label: "Measured" },
                                { value: "aggressive", label: "Aggressive" },
                                { value: "empathetic", label: "Empathetic" },
                            ],
                        },
                        {
                            key: "audience",
                            label: "Audience",
                            type: "select",
                            options: [
                                { value: "jury", label: "Jury" },
                                { value: "bench", label: "Bench (Judge)" },
                            ],
                        },
                    ]}
                />
                <ModuleNotes caseId={caseId} prepId={activePrepId} moduleKey="statements" />
            </TabsContent>
        </Tabs>
    );
}
