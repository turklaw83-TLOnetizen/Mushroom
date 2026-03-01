// ---- Opponent Playbook Tab -----------------------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { usePrep } from "@/hooks/use-prep";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

interface StrategyData {
    strategy_notes: string;
    devils_advocate_notes: string;
    mock_jury_feedback: Array<Record<string, unknown>>;
    opponent_playbook_notes?: string;
}

function extractSection(text: string, heading: string): string {
    if (!text) return "";
    const regex = new RegExp(`(?:^|\\n)#+\\s*${heading}[^\\n]*\\n([\\s\\S]*?)(?=\\n#+\\s|$)`, "i");
    const match = text.match(regex);
    return match ? match[1].trim() : "";
}

export default function PlaybookPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, isLoading: prepLoading } = usePrep();
    const { canEdit } = useRole();
    const [isEditing, setIsEditing] = useState(false);
    const [notes, setNotes] = useState("");

    const { data, isLoading } = useQuery({
        queryKey: ["strategy", caseId, activePrepId],
        queryFn: () =>
            api.get<StrategyData>(
                `/cases/${caseId}/preparations/${activePrepId}/strategy`,
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    const saveNotes = useMutationWithToast<string>({
        mutationFn: (updatedNotes) =>
            api.put(
                `/cases/${caseId}/preparations/${activePrepId}/strategy`,
                { opponent_playbook_notes: updatedNotes },
                { getToken },
            ),
        successMessage: "Playbook notes saved",
        invalidateKeys: [["strategy", caseId, activePrepId]],
        onSuccess: () => setIsEditing(false),
    });

    const handleEditStart = () => {
        setNotes(data?.opponent_playbook_notes || "");
        setIsEditing(true);
    };

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">
                    Create a preparation first to view the opponent playbook.
                </p>
            </div>
        );
    }

    if (isLoading) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-8 w-64 rounded-lg" />
                <Skeleton className="h-40 rounded-lg" />
                <Skeleton className="h-40 rounded-lg" />
                <Skeleton className="h-40 rounded-lg" />
                <Skeleton className="h-40 rounded-lg" />
            </div>
        );
    }

    // Extract sections from devil's advocate notes for structured display
    const devilNotes = data?.devils_advocate_notes || "";
    const opponentStrategy = extractSection(devilNotes, "Opponent.*Strategy|Prosecution.*Strategy|State.*Strategy") || devilNotes;
    const expectedArguments = extractSection(devilNotes, "Expected.*Argument|Likely.*Argument|Anticipated.*Argument");
    const weaknesses = extractSection(devilNotes, "Weakness|Vulnerabilit");
    const counters = extractSection(devilNotes, "Counter|Rebuttal|Response");

    // Extract relevant mock jury insights
    const juryInsights = data?.mock_jury_feedback
        ?.map((fb) => {
            const fbStr = typeof fb === "string" ? fb : JSON.stringify(fb);
            return fbStr;
        })
        .filter(Boolean) ?? [];

    return (
        <div className="space-y-5">
            <div>
                <h2 className="text-xl font-bold tracking-tight">Opponent Playbook</h2>
                <p className="text-sm text-muted-foreground mt-0.5">
                    Opponent strategy analysis, anticipated arguments, and recommended counters
                </p>
            </div>

            {/* Opponent Strategy */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        Opponent Strategy
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {opponentStrategy ? (
                        <p className="text-sm whitespace-pre-wrap">{opponentStrategy}</p>
                    ) : (
                        <p className="text-sm text-muted-foreground italic">
                            No opponent strategy analysis yet. Run the Devil&apos;s Advocate analysis to generate strategy insights.
                        </p>
                    )}
                </CardContent>
            </Card>

            {/* Expected Arguments */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        Expected Arguments
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {expectedArguments ? (
                        <p className="text-sm whitespace-pre-wrap">{expectedArguments}</p>
                    ) : (
                        <p className="text-sm text-muted-foreground italic">
                            No expected arguments identified yet. Run analysis to populate this section.
                        </p>
                    )}
                </CardContent>
            </Card>

            {/* Weaknesses to Exploit */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        Weaknesses to Exploit
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {weaknesses ? (
                        <p className="text-sm whitespace-pre-wrap">{weaknesses}</p>
                    ) : (
                        <p className="text-sm text-muted-foreground italic">
                            No weaknesses identified yet. Run analysis to identify exploitable gaps.
                        </p>
                    )}
                </CardContent>
            </Card>

            {/* Recommended Counters */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                        Recommended Counters
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {counters ? (
                        <p className="text-sm whitespace-pre-wrap">{counters}</p>
                    ) : data?.strategy_notes ? (
                        <p className="text-sm whitespace-pre-wrap">{data.strategy_notes}</p>
                    ) : (
                        <p className="text-sm text-muted-foreground italic">
                            No counter-strategies generated yet.
                        </p>
                    )}
                </CardContent>
            </Card>

            {/* Mock Jury Insights */}
            {juryInsights.length > 0 && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base flex items-center gap-2">
                            Mock Jury Insights ({juryInsights.length})
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-2">
                            {juryInsights.map((insight, i) => (
                                <div key={i} className="text-sm p-2 bg-muted rounded">
                                    {insight}
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Manual Notes */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center justify-between">
                        <span>Attorney Notes &amp; Observations</span>
                        {canEdit && !isEditing && (
                            <Button variant="outline" size="sm" onClick={handleEditStart}>
                                Edit
                            </Button>
                        )}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {isEditing ? (
                        <div className="space-y-3">
                            <textarea
                                className="flex min-h-[120px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                placeholder="Add your own notes about the opponent's strategy, tendencies, known patterns, or courtroom behavior..."
                                value={notes}
                                onChange={(e) => setNotes(e.target.value)}
                            />
                            <div className="flex gap-2 justify-end">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setIsEditing(false)}
                                >
                                    Cancel
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={() => saveNotes.mutate(notes)}
                                    disabled={saveNotes.isPending}
                                >
                                    {saveNotes.isPending ? "Saving..." : "Save Notes"}
                                </Button>
                            </div>
                        </div>
                    ) : data?.opponent_playbook_notes ? (
                        <p className="text-sm whitespace-pre-wrap">{data.opponent_playbook_notes}</p>
                    ) : (
                        <p className="text-sm text-muted-foreground italic">
                            No manual notes yet.{canEdit ? " Click Edit to add your own observations." : ""}
                        </p>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
