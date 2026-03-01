// ---- Quick Cards Page ----------------------------------------------------
// Courtroom reference cards: witnesses, evidence, objections.
// Printable, exportable as PDF via backend.
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { usePrep } from "@/hooks/use-prep";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// ---- Types --------------------------------------------------------------

interface WitnessCard {
    name: string;
    type: string;
    alignment: string;
    summary: string;
    impeachment_points: string[];
    cross_questions: CrossTopic[];
}

interface CrossTopic {
    topic?: string;
    questions?: CrossQuestion[];
    [key: string]: unknown;
}

interface CrossQuestion {
    question?: string;
    [key: string]: unknown;
}

interface EvidenceCard {
    exhibit: string;
    type: string;
    foundation: string;
    objections: string[] | string;
    value: string;
}

interface ObjectionCard {
    name: string;
    rule: string;
    basis: string;
    response: string;
}

interface QuickCardsData {
    witnesses: WitnessCard[];
    evidence: EvidenceCard[];
    objections: ObjectionCard[];
}

// ---- Helpers ------------------------------------------------------------

const ALIGNMENT_COLORS: Record<string, { bg: string; text: string; border: string }> = {
    friendly: { bg: "bg-emerald-500", text: "text-white", border: "border-emerald-500/30" },
    hostile: { bg: "bg-red-500", text: "text-white", border: "border-red-500/30" },
    neutral: { bg: "bg-amber-500", text: "text-white", border: "border-amber-500/30" },
};

function getAlignmentStyle(alignment: string) {
    return ALIGNMENT_COLORS[alignment?.toLowerCase()] || {
        bg: "bg-slate-500",
        text: "text-white",
        border: "border-slate-500/30",
    };
}

const TYPE_BADGE_COLORS: Record<string, string> = {
    State: "text-amber-400 border-amber-500/30",
    Defense: "text-blue-400 border-blue-500/30",
    Swing: "text-cyan-400 border-cyan-500/30",
    Expert: "text-violet-400 border-violet-500/30",
    Character: "text-emerald-400 border-emerald-500/30",
};

// ---- Witness Card Component ---------------------------------------------

function WitnessCardView({ witness }: { witness: WitnessCard }) {
    const alignStyle = getAlignmentStyle(witness.alignment);
    const [expanded, setExpanded] = useState(false);

    return (
        <Card className="quick-card break-inside-avoid border-2 hover:shadow-md transition-shadow">
            {/* Header bar */}
            <div className={`${alignStyle.bg} ${alignStyle.text} px-4 py-2 rounded-t-lg`}>
                <div className="flex items-center justify-between">
                    <span className="font-bold text-sm">{witness.name}</span>
                    <div className="flex items-center gap-1.5">
                        <Badge variant="outline" className={`text-[10px] bg-black/20 border-white/30 text-white ${TYPE_BADGE_COLORS[witness.type] || ""}`}>
                            {witness.type || "Unknown"}
                        </Badge>
                        {witness.alignment && (
                            <Badge variant="outline" className="text-[10px] bg-black/20 border-white/30 text-white">
                                {witness.alignment}
                            </Badge>
                        )}
                    </div>
                </div>
            </div>

            <CardContent className="py-3 space-y-2">
                {/* Summary */}
                {witness.summary && (
                    <p className="text-xs text-muted-foreground italic">
                        {witness.summary.length > 200 ? witness.summary.slice(0, 200) + "..." : witness.summary}
                    </p>
                )}

                {/* Cross Questions */}
                {witness.cross_questions && witness.cross_questions.length > 0 && (
                    <div>
                        <button
                            type="button"
                            className="text-xs font-semibold text-foreground mb-1 flex items-center gap-1 hover:text-primary transition-colors"
                            onClick={() => setExpanded(!expanded)}
                        >
                            <span className={`transition-transform text-[10px] ${expanded ? "rotate-90" : ""}`}>
                                {"\u25B6"}
                            </span>
                            KEY CROSS QUESTIONS
                        </button>
                        {expanded && (
                            <ol className="text-xs text-muted-foreground list-decimal pl-4 space-y-0.5">
                                {witness.cross_questions.flatMap((topic, ti) => {
                                    const questions = topic.questions || [];
                                    return questions.slice(0, 3).map((q, qi) => {
                                        const qText = typeof q === "string" ? q : (q as CrossQuestion).question || String(q);
                                        return (
                                            <li key={`${ti}-${qi}`}>
                                                {qText.length > 120 ? qText.slice(0, 120) + "..." : qText}
                                            </li>
                                        );
                                    });
                                }).slice(0, 8)}
                            </ol>
                        )}
                    </div>
                )}

                {/* Impeachment Points */}
                {witness.impeachment_points && witness.impeachment_points.length > 0 && (
                    <div>
                        <p className="text-xs font-semibold text-foreground mb-0.5">IMPEACHMENT</p>
                        <ul className="text-xs text-muted-foreground space-y-0.5">
                            {witness.impeachment_points.slice(0, 5).map((point, i) => (
                                <li key={i} className="pl-2 border-l-2 border-red-500/30">
                                    {typeof point === "string"
                                        ? (point.length > 120 ? point.slice(0, 120) + "..." : point)
                                        : String(point)}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

// ---- Evidence Card Component --------------------------------------------

function EvidenceCardView({ evidence }: { evidence: EvidenceCard }) {
    const [expanded, setExpanded] = useState(false);

    return (
        <Card className="quick-card break-inside-avoid border-2 hover:shadow-md transition-shadow">
            {/* Header */}
            <div className="bg-blue-500 text-white px-4 py-2 rounded-t-lg">
                <div className="flex items-center justify-between">
                    <span className="font-bold text-sm truncate">{evidence.exhibit}</span>
                    {evidence.type && (
                        <Badge variant="outline" className="text-[10px] bg-black/20 border-white/30 text-white shrink-0">
                            {evidence.type}
                        </Badge>
                    )}
                </div>
            </div>

            <CardContent className="py-3 space-y-2">
                {/* Foundation / Authentication */}
                {evidence.foundation && (
                    <div>
                        <p className="text-xs font-semibold text-foreground mb-0.5">AUTHENTICATION</p>
                        <p className="text-xs text-muted-foreground">
                            {typeof evidence.foundation === "string"
                                ? (evidence.foundation.length > 300
                                    ? evidence.foundation.slice(0, 300) + "..."
                                    : evidence.foundation)
                                : String(evidence.foundation)}
                        </p>
                    </div>
                )}

                {/* Objections */}
                {evidence.objections && (
                    <div>
                        <button
                            type="button"
                            className="text-xs font-semibold text-foreground mb-0.5 flex items-center gap-1 hover:text-primary transition-colors"
                            onClick={() => setExpanded(!expanded)}
                        >
                            <span className={`transition-transform text-[10px] ${expanded ? "rotate-90" : ""}`}>
                                {"\u25B6"}
                            </span>
                            ANTICIPATED OBJECTIONS
                        </button>
                        {expanded && (
                            Array.isArray(evidence.objections) ? (
                                <ul className="text-xs text-muted-foreground space-y-0.5">
                                    {evidence.objections.slice(0, 5).map((obj, i) => (
                                        <li key={i} className="pl-2 border-l-2 border-amber-500/30">
                                            {typeof obj === "string"
                                                ? (obj.length > 120 ? obj.slice(0, 120) + "..." : obj)
                                                : String(obj)}
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="text-xs text-muted-foreground">
                                    {String(evidence.objections).slice(0, 300)}
                                </p>
                            )
                        )}
                    </div>
                )}

                {/* Value */}
                {evidence.value && (
                    <div>
                        <p className="text-xs font-semibold text-foreground mb-0.5">VALUE</p>
                        <p className="text-xs text-muted-foreground">
                            {typeof evidence.value === "string"
                                ? (evidence.value.length > 200
                                    ? evidence.value.slice(0, 200) + "..."
                                    : evidence.value)
                                : String(evidence.value)}
                        </p>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

// ---- Objection Card Component -------------------------------------------

function ObjectionCardView({ objection }: { objection: ObjectionCard }) {
    return (
        <Card className="quick-card break-inside-avoid border-2 hover:shadow-md transition-shadow">
            {/* Header */}
            <div className="bg-red-500 text-white px-4 py-1.5 rounded-t-lg">
                <span className="font-bold text-sm">
                    {objection.name} <span className="font-normal text-xs opacity-80">({objection.rule})</span>
                </span>
            </div>

            <CardContent className="py-2 space-y-1.5">
                <div>
                    <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Basis</p>
                    <p className="text-xs text-muted-foreground italic">{objection.basis}</p>
                </div>
                <div>
                    <p className="text-[10px] font-medium text-emerald-500 uppercase tracking-wider">Response</p>
                    <p className="text-xs text-emerald-400/80">{objection.response}</p>
                </div>
            </CardContent>
        </Card>
    );
}

// ---- Main Page Component ------------------------------------------------

export default function QuickCardsPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, isLoading: prepLoading } = usePrep();
    const [activeTab, setActiveTab] = useState("witnesses");
    const [isExporting, setIsExporting] = useState(false);

    // ---- Query ----

    const cardsQuery = useQuery({
        queryKey: ["quick-cards", caseId, activePrepId],
        queryFn: () =>
            api.get<QuickCardsData>(
                `/documents/quick-cards-data/${caseId}/${activePrepId}`,
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    const data = cardsQuery.data;

    // ---- Handlers ----

    const handlePrint = () => {
        window.print();
    };

    const handleExportPdf = async (cardType: string) => {
        if (!activePrepId) {
            toast.error("Select a preparation first");
            return;
        }
        setIsExporting(true);
        try {
            const url = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/documents/quick-cards/${caseId}/${activePrepId}?card_type=${cardType}`;
            window.open(url, "_blank");
            toast.success("PDF export started");
        } catch {
            toast.error("Export failed");
        } finally {
            setIsExporting(false);
        }
    };

    // ---- Loading / Empty ----

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">Create a preparation first to view quick cards.</p>
            </div>
        );
    }

    if (cardsQuery.isLoading) {
        return (
            <div className="space-y-5">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">Quick Cards</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">Loading courtroom reference cards...</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {Array.from({ length: 6 }).map((_, i) => (
                        <Skeleton key={i} className="h-40 rounded-lg" />
                    ))}
                </div>
            </div>
        );
    }

    if (cardsQuery.error) {
        return (
            <div className="space-y-5">
                <h2 className="text-xl font-bold tracking-tight">Quick Cards</h2>
                <Card className="border-destructive/50">
                    <CardContent className="py-8 text-center">
                        <p className="text-sm text-destructive">
                            Failed to load cards: {cardsQuery.error.message}
                        </p>
                    </CardContent>
                </Card>
            </div>
        );
    }

    const witnesses = data?.witnesses ?? [];
    const evidence = data?.evidence ?? [];
    const objections = data?.objections ?? [];

    return (
        <div className="space-y-5">
            {/* Print-only styles */}
            <style>{`
                @media print {
                    /* Hide everything except cards */
                    body * { visibility: hidden; }
                    .quick-cards-content, .quick-cards-content * { visibility: visible; }
                    .quick-cards-content { position: absolute; left: 0; top: 0; width: 100%; }
                    .quick-card { break-inside: avoid; page-break-inside: avoid; margin-bottom: 12px; }
                    .no-print { display: none !important; }
                }
            `}</style>

            {/* Header */}
            <div className="flex items-center justify-between no-print">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">Quick Cards</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Printable courtroom reference cards for witnesses, evidence, and objections
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={handlePrint}>
                        Print
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleExportPdf(activeTab === "witnesses" ? "witness" : activeTab)}
                        disabled={isExporting}
                    >
                        Export PDF
                    </Button>
                </div>
            </div>

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="no-print">
                    <TabsTrigger value="witnesses">
                        Witnesses
                        {witnesses.length > 0 && (
                            <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5">
                                {witnesses.length}
                            </Badge>
                        )}
                    </TabsTrigger>
                    <TabsTrigger value="evidence">
                        Evidence
                        {evidence.length > 0 && (
                            <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5">
                                {evidence.length}
                            </Badge>
                        )}
                    </TabsTrigger>
                    <TabsTrigger value="objections">
                        Objections
                        <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5">
                            {objections.length}
                        </Badge>
                    </TabsTrigger>
                </TabsList>

                {/* Witnesses Tab */}
                <TabsContent value="witnesses" className="mt-4 quick-cards-content">
                    {witnesses.length === 0 ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No witnesses identified. Run the Strategist analysis module first.
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {witnesses.map((w, i) => (
                                <WitnessCardView key={i} witness={w} />
                            ))}
                        </div>
                    )}
                </TabsContent>

                {/* Evidence Tab */}
                <TabsContent value="evidence" className="mt-4 quick-cards-content">
                    {evidence.length === 0 ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No evidence analysis available. Run the Evidence Foundations module first.
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {evidence.map((ev, i) => (
                                <EvidenceCardView key={i} evidence={ev} />
                            ))}
                        </div>
                    )}
                </TabsContent>

                {/* Objections Tab */}
                <TabsContent value="objections" className="mt-4 quick-cards-content">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {objections.map((obj, i) => (
                            <ObjectionCardView key={i} objection={obj} />
                        ))}
                    </div>
                </TabsContent>
            </Tabs>
        </div>
    );
}
