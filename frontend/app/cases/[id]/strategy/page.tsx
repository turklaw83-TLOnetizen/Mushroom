// ---- Strategy Tab (updated to use PrepProvider) -------------------------
"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { usePrep } from "@/hooks/use-prep";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface StrategyData {
    strategy_notes: string;
    devils_advocate_notes: string;
    voir_dire: Record<string, unknown>;
    mock_jury_feedback: Array<Record<string, unknown>>;
}

export default function StrategyPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, isLoading: prepLoading } = usePrep();

    const { data, isLoading } = useQuery({
        queryKey: ["strategy", caseId, activePrepId],
        queryFn: () =>
            api.get<StrategyData>(
                `/cases/${caseId}/preparations/${activePrepId}/strategy`,
                { getToken },
            ),
        enabled: !!activePrepId,
    });

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">Create a preparation first to manage strategy.</p>
            </div>
        );
    }

    if (isLoading) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-40 rounded-lg" />
                <Skeleton className="h-40 rounded-lg" />
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">🎯 Strategy Notes</CardTitle>
                </CardHeader>
                <CardContent>
                    {data?.strategy_notes ? (
                        <p className="text-sm whitespace-pre-wrap">{data.strategy_notes}</p>
                    ) : (
                        <p className="text-sm text-muted-foreground italic">
                            No strategy notes yet. Run analysis to generate strategy recommendations.
                        </p>
                    )}
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">😈 Devil&apos;s Advocate</CardTitle>
                </CardHeader>
                <CardContent>
                    {data?.devils_advocate_notes ? (
                        <p className="text-sm whitespace-pre-wrap">{data.devils_advocate_notes}</p>
                    ) : (
                        <p className="text-sm text-muted-foreground italic">No devil&apos;s advocate analysis yet.</p>
                    )}
                </CardContent>
            </Card>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base flex items-center gap-2">🗳️ Voir Dire</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {data?.voir_dire && Object.keys(data.voir_dire).length > 0 ? (
                            <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-60">
                                {JSON.stringify(data.voir_dire, null, 2)}
                            </pre>
                        ) : (
                            <p className="text-sm text-muted-foreground italic">No voir dire data.</p>
                        )}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="text-base flex items-center gap-2">
                            👥 Mock Jury ({data?.mock_jury_feedback?.length || 0})
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {data?.mock_jury_feedback?.length ? (
                            <div className="space-y-2">
                                {data.mock_jury_feedback.map((fb, i) => (
                                    <div key={i} className="text-sm p-2 bg-muted rounded">{JSON.stringify(fb)}</div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-sm text-muted-foreground italic">No mock jury feedback.</p>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
