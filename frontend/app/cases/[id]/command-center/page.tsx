// ---- Case Command Center ------------------------------------------------
// Single-screen war room: case health, deadlines, witnesses, evidence,
// vulnerabilities, and AI-recommended next actions.
"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { useCase } from "@/hooks/use-cases";
import { usePrep } from "@/hooks/use-prep";
import { api } from "@/lib/api-client";
import { routes } from "@/lib/api-routes";
import { queryKeys } from "@/lib/query-keys";
import { formatDate, formatRelativeTime } from "@/lib/constants";
import { StatusBadge } from "@/components/shared/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

// ---- Data Fetching Hooks ------------------------------------------------

/* eslint-disable @typescript-eslint/no-explicit-any */

type TokenFn = () => Promise<string | null>;

function usePredictiveScore(caseId: string, prepId: string | undefined, getToken: TokenFn) {
    return useQuery<any>({
        queryKey: [...queryKeys.predictiveScore.score(caseId, prepId || "")],
        queryFn: () => api.get(routes.predictiveScore.score(caseId, prepId!), { getToken }),
        enabled: !!prepId,
    });
}

function useDeadlines(caseId: string, getToken: TokenFn) {
    return useQuery<any>({
        queryKey: [...queryKeys.calendar.deadlines(caseId)],
        queryFn: () => api.get(routes.calendar.deadlines(caseId), { getToken }),
    });
}

function useActivity(caseId: string, getToken: TokenFn) {
    return useQuery<any>({
        queryKey: [...queryKeys.activity.feed(caseId)],
        queryFn: () => api.get(`${routes.activity.feed(caseId)}?limit=10`, { getToken }),
    });
}

function useWitnesses(caseId: string, prepId: string | undefined, getToken: TokenFn) {
    return useQuery<any>({
        queryKey: [...queryKeys.witnesses.list(caseId, prepId || "")],
        queryFn: () => api.get(routes.witnesses.list(caseId, prepId!), { getToken }),
        enabled: !!prepId,
    });
}

function useEvidence(caseId: string, prepId: string | undefined, getToken: TokenFn) {
    return useQuery<any>({
        queryKey: [...queryKeys.evidence.list(caseId, prepId || "")],
        queryFn: () => api.get(routes.evidence.list(caseId, prepId!), { getToken }),
        enabled: !!prepId,
    });
}

function useWarGameSessions(caseId: string, prepId: string | undefined, getToken: TokenFn) {
    return useQuery<any>({
        queryKey: [...queryKeys.warGame.sessions(caseId, prepId || "")],
        queryFn: () => api.get(routes.warGame.sessions(caseId, prepId!), { getToken }),
        enabled: !!prepId,
    });
}

// ---- Helper Components --------------------------------------------------

function MetricCard({
    label,
    value,
    sub,
    color = "text-white",
}: {
    label: string;
    value: string | number;
    sub?: string;
    color?: string;
}) {
    return (
        <Card className="border-white/5">
            <CardContent className="pt-4 pb-3">
                <p className="text-xs text-muted-foreground uppercase tracking-wider">{label}</p>
                <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
                {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
            </CardContent>
        </Card>
    );
}

function ScoreRing({ score, grade, label }: { score: number; grade: string; label: string }) {
    const circumference = 2 * Math.PI * 40;
    const progress = (score / 100) * circumference;
    const color =
        score >= 80 ? "text-green-400 stroke-green-400" :
        score >= 60 ? "text-amber-400 stroke-amber-400" :
        "text-red-400 stroke-red-400";

    return (
        <div className="flex flex-col items-center">
            <div className="relative w-24 h-24">
                <svg className="w-24 h-24 -rotate-90" viewBox="0 0 100 100">
                    <circle cx="50" cy="50" r="40" fill="none" stroke="currentColor"
                        className="text-white/5" strokeWidth="6" />
                    <circle cx="50" cy="50" r="40" fill="none"
                        className={color} strokeWidth="6" strokeLinecap="round"
                        strokeDasharray={circumference} strokeDashoffset={circumference - progress} />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className={`text-lg font-bold ${color.split(" ")[0]}`}>{grade}</span>
                    <span className="text-xs text-muted-foreground">{score}</span>
                </div>
            </div>
            <p className="text-xs text-muted-foreground mt-2">{label}</p>
        </div>
    );
}

function LoadingSkeleton() {
    return (
        <div className="space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
        </div>
    );
}

// ---- Main Page ----------------------------------------------------------

export default function CommandCenterPage() {
    const { id: caseId } = useParams<{ id: string }>();
    const { getToken } = useAuth();
    const { data: caseData } = useCase(caseId);
    const { activePrep: prep } = usePrep();
    const prepId = prep?.id;

    const { data: scoreData, isLoading: scoreLoading } = usePredictiveScore(caseId, prepId, getToken);
    const { data: deadlines, isLoading: deadlinesLoading } = useDeadlines(caseId, getToken);
    const { data: activity, isLoading: activityLoading } = useActivity(caseId, getToken);
    const { data: witnesses, isLoading: witnessesLoading } = useWitnesses(caseId, prepId, getToken);
    const { data: evidence, isLoading: evidenceLoading } = useEvidence(caseId, prepId, getToken);
    const { data: warGames } = useWarGameSessions(caseId, prepId, getToken);

    const score = scoreData?.score;
    const dims = score?.dimensions || {};

    // Parse witness types
    const witnessList = Array.isArray(witnesses?.items || witnesses) ? (witnesses?.items || witnesses) : [];
    const defenseWitnesses = witnessList.filter((w: any) => w.type === "defense" || w.type === "Defense");
    const stateWitnesses = witnessList.filter((w: any) => w.type === "state" || w.type === "State" || w.type === "prosecution");
    const swingWitnesses = witnessList.filter((w: any) => w.type === "swing" || w.type === "Swing");

    // Parse evidence
    const evidenceList = Array.isArray(evidence?.items || evidence) ? (evidence?.items || evidence) : [];

    // Parse deadlines
    const deadlineList = Array.isArray(deadlines?.items || deadlines) ? (deadlines?.items || deadlines) : [];
    const upcomingDeadlines = deadlineList
        .filter((d: any) => new Date(d.due_date || d.date) >= new Date())
        .sort((a: any, b: any) => new Date(a.due_date || a.date).getTime() - new Date(b.due_date || b.date).getTime())
        .slice(0, 5);
    const overdueDeadlines = deadlineList.filter(
        (d: any) => new Date(d.due_date || d.date) < new Date() && d.status !== "completed"
    );

    // Parse activity
    const activityList = Array.isArray(activity?.items || activity) ? (activity?.items || activity) : [];

    // War game latest
    const warGameList = Array.isArray(warGames?.items || warGames) ? (warGames?.items || warGames) : [];
    const latestWarGame = warGameList[0];

    if (!prep) {
        return (
            <div className="p-6">
                <p className="text-muted-foreground">Select a preparation to view the Command Center.</p>
            </div>
        );
    }

    return (
        <div className="p-6 space-y-6 max-w-7xl">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold">Command Center</h1>
                    <p className="text-sm text-muted-foreground">
                        {caseData?.name || "Case"} — {prep.name || prep.type}
                    </p>
                </div>
                {score && (
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">Case Readiness</span>
                        <Badge
                            className={
                                score.overall >= 80 ? "bg-green-500/15 text-green-400 border-green-500/30" :
                                score.overall >= 60 ? "bg-amber-500/15 text-amber-400 border-amber-500/30" :
                                "bg-red-500/15 text-red-400 border-red-500/30"
                            }
                        >
                            {score.grade} ({score.overall}/100)
                        </Badge>
                    </div>
                )}
            </div>

            {/* Row 1: Score Dimensions */}
            {scoreLoading ? (
                <div className="grid grid-cols-6 gap-4">
                    {Array.from({ length: 6 }).map((_, i) => (
                        <Card key={i} className="border-white/5">
                            <CardContent className="pt-4 flex justify-center">
                                <Skeleton className="w-24 h-24 rounded-full" />
                            </CardContent>
                        </Card>
                    ))}
                </div>
            ) : score ? (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                    {Object.entries(dims).map(([key, dim]: [string, any]) => (
                        <Card key={key} className="border-white/5">
                            <CardContent className="pt-4 flex justify-center">
                                <ScoreRing
                                    score={dim.score || 0}
                                    grade={dim.grade || "?"}
                                    label={key.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase())}
                                />
                            </CardContent>
                        </Card>
                    ))}
                </div>
            ) : (
                <Card className="border-white/5">
                    <CardContent className="py-8 text-center text-muted-foreground text-sm">
                        Run analysis to generate case scores
                    </CardContent>
                </Card>
            )}

            {/* Row 2: Quick Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard
                    label="Witnesses"
                    value={witnessesLoading ? "..." : witnessList.length}
                    sub={`${defenseWitnesses.length} defense, ${stateWitnesses.length} state, ${swingWitnesses.length} swing`}
                    color="text-blue-400"
                />
                <MetricCard
                    label="Evidence Items"
                    value={evidenceLoading ? "..." : evidenceList.length}
                    sub="foundations analyzed"
                    color="text-emerald-400"
                />
                <MetricCard
                    label="Deadlines"
                    value={deadlinesLoading ? "..." : upcomingDeadlines.length}
                    sub={overdueDeadlines.length > 0 ? `${overdueDeadlines.length} overdue!` : "upcoming"}
                    color={overdueDeadlines.length > 0 ? "text-red-400" : "text-amber-400"}
                />
                <MetricCard
                    label="War Games"
                    value={warGameList.length}
                    sub={latestWarGame ? `Latest: ${latestWarGame.difficulty || "standard"}` : "none played"}
                    color="text-violet-400"
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Upcoming Deadlines */}
                <Card className="border-white/5">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-sm font-medium">Upcoming Deadlines</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {deadlinesLoading ? (
                            <LoadingSkeleton />
                        ) : upcomingDeadlines.length === 0 ? (
                            <p className="text-sm text-muted-foreground">No upcoming deadlines</p>
                        ) : (
                            <div className="space-y-3">
                                {overdueDeadlines.map((d: any, i: number) => (
                                    <div key={`overdue-${i}`} className="flex items-center justify-between p-2 rounded bg-red-500/10 border border-red-500/20">
                                        <div>
                                            <p className="text-sm font-medium text-red-400">{d.title || d.description}</p>
                                            <p className="text-xs text-red-400/70">OVERDUE — {formatDate(d.due_date || d.date)}</p>
                                        </div>
                                        <Badge className="bg-red-500/15 text-red-400 border-red-500/30">Overdue</Badge>
                                    </div>
                                ))}
                                {upcomingDeadlines.map((d: any, i: number) => (
                                    <div key={i} className="flex items-center justify-between p-2 rounded bg-white/[0.02]">
                                        <div>
                                            <p className="text-sm font-medium text-zinc-300">{d.title || d.description}</p>
                                            <p className="text-xs text-muted-foreground">{formatDate(d.due_date || d.date)}</p>
                                        </div>
                                        <span className="text-xs text-muted-foreground">
                                            {formatRelativeTime(d.due_date || d.date)}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Strengths & Vulnerabilities */}
                <Card className="border-white/5">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-sm font-medium">Strengths & Vulnerabilities</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {scoreLoading ? (
                            <LoadingSkeleton />
                        ) : score ? (
                            <div className="space-y-4">
                                {score.strengths?.length > 0 && (
                                    <div>
                                        <p className="text-xs font-medium text-green-400 mb-2">STRENGTHS</p>
                                        {score.strengths.slice(0, 4).map((s: string, i: number) => (
                                            <p key={i} className="text-sm text-zinc-400 mb-1">+ {s}</p>
                                        ))}
                                    </div>
                                )}
                                {score.vulnerabilities?.length > 0 && (
                                    <div>
                                        <p className="text-xs font-medium text-red-400 mb-2">VULNERABILITIES</p>
                                        {score.vulnerabilities.slice(0, 4).map((v: string, i: number) => (
                                            <p key={i} className="text-sm text-zinc-400 mb-1">- {v}</p>
                                        ))}
                                    </div>
                                )}
                                {!score.strengths?.length && !score.vulnerabilities?.length && (
                                    <p className="text-sm text-muted-foreground">No strength/vulnerability data yet</p>
                                )}
                            </div>
                        ) : (
                            <p className="text-sm text-muted-foreground">Run analysis to see strengths and vulnerabilities</p>
                        )}
                    </CardContent>
                </Card>

                {/* Witness Overview */}
                <Card className="border-white/5">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-sm font-medium">Witness Roster</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {witnessesLoading ? (
                            <LoadingSkeleton />
                        ) : witnessList.length === 0 ? (
                            <p className="text-sm text-muted-foreground">No witnesses identified yet</p>
                        ) : (
                            <div className="space-y-2">
                                {witnessList.slice(0, 8).map((w: any, i: number) => (
                                    <div key={i} className="flex items-center justify-between p-2 rounded bg-white/[0.02]">
                                        <div className="flex items-center gap-2">
                                            <div className="w-7 h-7 rounded-full bg-indigo-500/20 flex items-center justify-center text-xs font-medium text-indigo-400">
                                                {(w.name || "?")[0]}
                                            </div>
                                            <p className="text-sm text-zinc-300">{w.name}</p>
                                        </div>
                                        <StatusBadge
                                            status={w.type || "unknown"}
                                            domain="witness"
                                        />
                                    </div>
                                ))}
                                {witnessList.length > 8 && (
                                    <p className="text-xs text-muted-foreground text-center">
                                        +{witnessList.length - 8} more witnesses
                                    </p>
                                )}
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Recent Activity */}
                <Card className="border-white/5">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-sm font-medium">Recent Activity</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {activityLoading ? (
                            <LoadingSkeleton />
                        ) : activityList.length === 0 ? (
                            <p className="text-sm text-muted-foreground">No recent activity</p>
                        ) : (
                            <div className="space-y-2">
                                {activityList.slice(0, 8).map((a: any, i: number) => (
                                    <div key={i} className="flex items-start gap-2 p-2 rounded bg-white/[0.02]">
                                        <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1.5 flex-shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm text-zinc-300 truncate">
                                                {a.description || a.action || a.event}
                                            </p>
                                            <p className="text-xs text-muted-foreground">
                                                {formatRelativeTime(a.timestamp || a.created_at)}
                                            </p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
