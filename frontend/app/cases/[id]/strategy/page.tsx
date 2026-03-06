// ---- Strategy Tab (with sub-tabs for analysis results) -------------------
// Sub-tabs: Strategy | Devil's Advocate | Voir Dire | Mock Jury
"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { usePrep } from "@/hooks/use-prep";
import { usePrepState } from "@/hooks/use-prep-state";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { ResultSection } from "@/components/analysis/result-section";
import { MarkdownContent } from "@/components/analysis/markdown-content";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { GenerateButton, GenerateWithInput } from "@/components/analysis/generate-button";
import { ModuleNotes } from "@/components/shared/module-notes";
import { ArgumentForge } from "@/components/argument-forge";

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

// ---- Strength / Weakness Matrix -----------------------------------------

/**
 * Extract the first ~200 chars of relevant content from analysis text.
 * Searches for keyword matches and returns surrounding paragraph context.
 */
function extractSnippet(text: string | undefined | null, keywords: string[]): string {
    if (!text || typeof text !== "string") return "";
    const lower = text.toLowerCase();
    for (const kw of keywords) {
        const idx = lower.indexOf(kw.toLowerCase());
        if (idx !== -1) {
            // Find the start of the paragraph (previous double newline or start)
            const paraStart = Math.max(0, text.lastIndexOf("\n", Math.max(0, idx - 1)));
            return text.slice(paraStart, paraStart + 200).trim();
        }
    }
    return "";
}

function StrengthWeaknessMatrix({
    strategyNotes,
    devilsAdvocate,
}: {
    strategyNotes: string | undefined | null;
    devilsAdvocate: string | undefined | null;
}) {
    const stratText = typeof strategyNotes === "string" ? strategyNotes : "";
    const daText = typeof devilsAdvocate === "string" ? devilsAdvocate : "";

    // Auto-populate defaults from analysis text
    const defaultStrengths = extractSnippet(stratText, ["strength", "strong", "advantage", "favorable", "compelling"]);
    const defaultWeaknesses = extractSnippet(daText, ["vulnerab", "weakness", "weak point", "risk", "concern", "flaw"]);
    const defaultTheirStrengths = extractSnippet(daText, ["prosecution", "opponent", "their strength", "opposing", "government"]);
    const defaultTheirWeaknesses = extractSnippet(stratText, ["opponent weakness", "their weakness", "exploit", "undermine"]);

    const [ourStrengths, setOurStrengths] = useState(defaultStrengths);
    const [ourWeaknesses, setOurWeaknesses] = useState(defaultWeaknesses);
    const [theirStrengths, setTheirStrengths] = useState(defaultTheirStrengths);
    const [theirWeaknesses, setTheirWeaknesses] = useState(defaultTheirWeaknesses);

    // Re-initialize when analysis data changes (e.g., after first load)
    useEffect(() => {
        setOurStrengths(defaultStrengths);
        setOurWeaknesses(defaultWeaknesses);
        setTheirStrengths(defaultTheirStrengths);
        setTheirWeaknesses(defaultTheirWeaknesses);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [stratText, daText]);

    const quadrants = [
        { label: "Our Strengths", color: "border-emerald-500", value: ourStrengths, onChange: setOurStrengths },
        { label: "Our Weaknesses", color: "border-red-500", value: ourWeaknesses, onChange: setOurWeaknesses },
        { label: "Their Strengths", color: "border-amber-500", value: theirStrengths, onChange: setTheirStrengths },
        { label: "Their Weaknesses", color: "border-blue-500", value: theirWeaknesses, onChange: setTheirWeaknesses },
    ] as const;

    return (
        <Card className="mb-6">
            <CardHeader>
                <CardTitle className="text-base">Strength / Weakness Matrix</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-2 gap-4">
                    {quadrants.map((q) => (
                        <div key={q.label} className={`border-l-4 ${q.color} pl-3`}>
                            <h4 className="text-sm font-semibold mb-1.5">{q.label}</h4>
                            <textarea
                                className="w-full min-h-[100px] px-3 py-2 rounded-md border bg-background text-sm resize-y focus:outline-none focus:ring-2 focus:ring-ring"
                                value={q.value}
                                onChange={(e) => q.onChange(e.target.value)}
                                placeholder={`Enter ${q.label.toLowerCase()}...`}
                            />
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
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

    // On-demand generation mutations for Voir Dire and Mock Jury
    const generateVoirDire = useMutationWithToast<void>({
        mutationFn: () =>
            api.post(
                `/cases/${caseId}/preparations/${activePrepId}/generate/voir-dire`,
                {},
                { getToken },
            ),
        successMessage: "Voir dire analysis generated",
        invalidateKeys: [
            ["cases", caseId, "prep-state", activePrepId],
            ["strategy", caseId, activePrepId],
        ],
    });

    const generateMockJury = useMutationWithToast<void>({
        mutationFn: () =>
            api.post(
                `/cases/${caseId}/preparations/${activePrepId}/generate/mock-jury`,
                {},
                { getToken },
            ),
        successMessage: "Mock jury simulation generated",
        invalidateKeys: [
            ["cases", caseId, "prep-state", activePrepId],
            ["strategy", caseId, activePrepId],
        ],
    });

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
                <TabsTrigger value="argument-forge">
                    Argument Forge
                </TabsTrigger>
                <TabsTrigger value="statements">Statements</TabsTrigger>
            </TabsList>

            {/* ---- Strategy Notes Tab ---- */}
            <TabsContent value="strategy">
                {(strategyNotes || devilsAdvocate) && (
                    <StrengthWeaknessMatrix
                        strategyNotes={typeof strategyNotes === "string" ? strategyNotes : null}
                        devilsAdvocate={typeof devilsAdvocate === "string" ? devilsAdvocate : null}
                    />
                )}
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
                    emptyMessage="No voir dire data yet. Click Generate to create jury selection strategy."
                >
                    {voirDire && renderVoirDireContent(voirDire as string | Record<string, unknown>)}
                </ResultSection>

                <div className="flex items-center gap-3 mt-4">
                    <Button
                        size="sm"
                        onClick={() => generateVoirDire.mutate()}
                        disabled={generateVoirDire.isPending || !activePrepId}
                        variant={hasVoirDire ? "outline" : "default"}
                    >
                        {generateVoirDire.isPending ? (
                            <span className="flex items-center gap-2">
                                <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                Generating...
                            </span>
                        ) : hasVoirDire ? (
                            "Regenerate"
                        ) : (
                            "Generate Voir Dire"
                        )}
                    </Button>
                    {generateVoirDire.isError && (
                        <p className="text-xs text-red-400">Generation failed. Please try again.</p>
                    )}
                </div>
                <ModuleNotes caseId={caseId} prepId={activePrepId} moduleKey="voir_dire" />
            </TabsContent>

            {/* ---- Mock Jury Tab ---- */}
            <TabsContent value="mock-jury">
                <ResultSection
                    title="Mock Jury Feedback"
                    icon="👥"
                    isEmpty={!hasMockJury}
                    isLoading={stateLoading}
                    emptyMessage="No mock jury feedback yet. Click Run Mock Jury to simulate jury deliberation."
                >
                    {mockJury && renderMockJuryContent(mockJury as string | Record<string, unknown> | Array<Record<string, unknown>>)}
                </ResultSection>

                <div className="flex items-center gap-3 mt-4">
                    <Button
                        size="sm"
                        onClick={() => generateMockJury.mutate()}
                        disabled={generateMockJury.isPending || !activePrepId}
                        variant={hasMockJury ? "outline" : "default"}
                    >
                        {generateMockJury.isPending ? (
                            <span className="flex items-center gap-2">
                                <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                Running...
                            </span>
                        ) : hasMockJury ? (
                            "Regenerate"
                        ) : (
                            "Run Mock Jury"
                        )}
                    </Button>
                    {generateMockJury.isError && (
                        <p className="text-xs text-red-400">Simulation failed. Please try again.</p>
                    )}
                </div>
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

            {/* ---- Argument Forge Tab ---- */}
            <TabsContent value="argument-forge">
                <ArgumentForge caseId={caseId} prepId={activePrepId} />
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
