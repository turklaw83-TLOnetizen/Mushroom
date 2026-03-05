// ---- Mock Exam Scorecard View -------------------------------------------
// Displays post-session scoring with category breakdowns.

"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

interface CategoryScore {
    score: number;
    notes: string;
    highlights?: string[];
    missed_opportunities?: Array<{
        description: string;
        suggested_question: string;
        source?: string;
    }>;
}

interface QuestionSequence {
    topic: string;
    questions: string[];
    rationale: string;
}

export interface Scorecard {
    overall_score: number;
    categories: Record<string, CategoryScore>;
    suggested_question_sequences?: QuestionSequence[];
    summary: string;
}

function getGrade(score: number): { letter: string; color: string } {
    if (score >= 90) return { letter: "A", color: "text-emerald-400" };
    if (score >= 80) return { letter: "B", color: "text-blue-400" };
    if (score >= 70) return { letter: "C", color: "text-yellow-400" };
    if (score >= 60) return { letter: "D", color: "text-orange-400" };
    return { letter: "F", color: "text-red-400" };
}

function getBarColor(score: number): string {
    if (score >= 80) return "bg-emerald-500";
    if (score >= 60) return "bg-yellow-500";
    return "bg-red-500";
}

const CATEGORY_LABELS: Record<string, string> = {
    question_technique: "Question Technique",
    impeachment_effectiveness: "Impeachment Effectiveness",
    evidence_usage: "Evidence Usage",
    objection_avoidance: "Objection Avoidance",
    narrative_control: "Narrative Control",
};

export function ScorecardView({
    scorecard,
    examType,
    witnessName,
}: {
    scorecard: Scorecard;
    examType: string;
    witnessName: string;
}) {
    const grade = getGrade(scorecard.overall_score);
    const categories = scorecard.categories || {};

    return (
        <div className="space-y-4">
            {/* Overall Score */}
            <Card className="border-brand-indigo/30">
                <CardContent className="pt-6">
                    <div className="flex items-center gap-6">
                        <div className="text-center">
                            <div className={`text-5xl font-bold ${grade.color}`}>
                                {scorecard.overall_score}
                            </div>
                            <div className={`text-2xl font-bold ${grade.color}`}>
                                {grade.letter}
                            </div>
                        </div>
                        <div className="flex-1">
                            <h3 className="text-lg font-semibold">
                                {examType === "cross" ? "Cross" : "Direct"}-Examination of{" "}
                                {witnessName}
                            </h3>
                            <p className="text-sm text-muted-foreground mt-1">
                                {scorecard.summary}
                            </p>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Category Scores */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {Object.entries(categories).map(([key, cat]) => (
                    <Card key={key}>
                        <CardContent className="pt-4 pb-4">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium">
                                    {CATEGORY_LABELS[key] || key}
                                </span>
                                <span className={`text-sm font-bold ${getGrade(cat.score).color}`}>
                                    {cat.score}
                                </span>
                            </div>
                            <div className="h-2 rounded-full bg-muted overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all ${getBarColor(cat.score)}`}
                                    style={{ width: `${cat.score}%` }}
                                />
                            </div>
                            <p className="text-xs text-muted-foreground mt-2">{cat.notes}</p>
                            {/* Highlights */}
                            {cat.highlights && cat.highlights.length > 0 && (
                                <div className="mt-2 space-y-1">
                                    {cat.highlights.map((h, i) => (
                                        <div
                                            key={i}
                                            className="text-xs bg-muted/50 px-2 py-1 rounded"
                                        >
                                            {h}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Missed Opportunities */}
            {categories.impeachment_effectiveness?.missed_opportunities?.length ? (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                            <span aria-hidden="true">🎯</span> Missed Opportunities
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        {categories.impeachment_effectiveness.missed_opportunities.map(
                            (opp, i) => (
                                <div key={i} className="border rounded-lg p-3 space-y-1">
                                    <p className="text-sm font-medium">{opp.description}</p>
                                    <p className="text-sm text-muted-foreground italic">
                                        &quot;{opp.suggested_question}&quot;
                                    </p>
                                    {opp.source && (
                                        <Badge variant="outline" className="text-xs">
                                            {opp.source}
                                        </Badge>
                                    )}
                                </div>
                            ),
                        )}
                    </CardContent>
                </Card>
            ) : null}

            {/* Suggested Question Sequences */}
            {scorecard.suggested_question_sequences?.length ? (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                            <span aria-hidden="true">💡</span> Suggested Question Sequences
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {scorecard.suggested_question_sequences.map((seq, i) => (
                            <div key={i} className="space-y-2">
                                <div className="flex items-center gap-2">
                                    <Badge variant="secondary" className="text-xs">
                                        {seq.topic}
                                    </Badge>
                                </div>
                                <ol className="list-decimal list-inside space-y-1 text-sm pl-2">
                                    {seq.questions.map((q, qi) => (
                                        <li key={qi} className="text-muted-foreground">
                                            &quot;{q}&quot;
                                        </li>
                                    ))}
                                </ol>
                                <p className="text-xs text-muted-foreground italic">
                                    {seq.rationale}
                                </p>
                            </div>
                        ))}
                    </CardContent>
                </Card>
            ) : null}
        </div>
    );
}
