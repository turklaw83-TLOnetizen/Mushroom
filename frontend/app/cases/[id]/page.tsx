// ---- Case Overview Page -------------------------------------------------
// The first thing attorneys see when opening a case. Shows case vitals,
// readiness at a glance, upcoming deadlines, and quick-access actions.
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useCase } from "@/hooks/use-cases";
import { usePrep } from "@/hooks/use-prep";
import { api } from "@/lib/api-client";
import { routes } from "@/lib/api-routes";
import { queryKeys } from "@/lib/query-keys";
import { formatDate, formatRelativeTime } from "@/lib/constants";
import { ExportPanel } from "@/components/export-panel";
import { StatusBadge } from "@/components/shared/status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

/* eslint-disable @typescript-eslint/no-explicit-any */

// ---- Data Hooks ---------------------------------------------------------

function useCaseScore(caseId: string, prepId: string | undefined) {
    return useQuery<any>({
        queryKey: [...queryKeys.predictiveScore.score(caseId, prepId || "")],
        queryFn: () => api.get(routes.predictiveScore.score(caseId, prepId!)),
        enabled: !!prepId,
        retry: false,
    });
}

function useCaseDeadlines(caseId: string) {
    return useQuery<any>({
        queryKey: [...queryKeys.calendar.deadlines(caseId)],
        queryFn: () => api.get(routes.calendar.deadlines(caseId)),
        retry: false,
    });
}

function useCaseWitnesses(caseId: string, prepId: string | undefined) {
    return useQuery<any>({
        queryKey: [...queryKeys.witnesses.list(caseId, prepId || "")],
        queryFn: () => api.get(routes.witnesses.list(caseId, prepId!)),
        enabled: !!prepId,
        retry: false,
    });
}

function useCaseEvidence(caseId: string, prepId: string | undefined) {
    return useQuery<any>({
        queryKey: [...queryKeys.evidence.list(caseId, prepId || "")],
        queryFn: () => api.get(routes.evidence.list(caseId, prepId!)),
        enabled: !!prepId,
        retry: false,
    });
}

function useCaseActivity(caseId: string) {
    return useQuery<any>({
        queryKey: [...queryKeys.activity.feed(caseId)],
        queryFn: () => api.get(`${routes.activity.feed(caseId)}?limit=5`),
        retry: false,
    });
}

// ---- Components ---------------------------------------------------------

function ReadinessGauge({ score, grade }: { score: number; grade: string }) {
    const circumference = 2 * Math.PI * 52;
    const progress = (score / 100) * circumference;
    const color =
        score >= 80
            ? "stroke-green-400 text-green-400"
            : score >= 60
              ? "stroke-amber-400 text-amber-400"
              : "stroke-red-400 text-red-400";

    return (
        <div className="relative w-32 h-32">
            <svg className="w-32 h-32 -rotate-90" viewBox="0 0 120 120">
                <circle
                    cx="60" cy="60" r="52" fill="none"
                    stroke="currentColor" className="text-white/5" strokeWidth="8"
                />
                <circle
                    cx="60" cy="60" r="52" fill="none"
                    className={color} strokeWidth="8" strokeLinecap="round"
                    strokeDasharray={circumference}
                    strokeDashoffset={circumference - progress}
                    style={{ transition: "stroke-dashoffset 0.8s ease-out" }}
                />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className={`text-2xl font-bold ${color.split(" ")[1]}`}>{grade}</span>
                <span className="text-sm text-muted-foreground">{score}/100</span>
            </div>
        </div>
    );
}

function StatCard({
    label,
    value,
    sub,
    icon,
    color = "text-white",
    delay = 0,
}: {
    label: string;
    value: string | number;
    sub?: string;
    icon: string;
    color?: string;
    delay?: number;
}) {
    return (
        <div className="glass-card px-5 py-4" style={{ animationDelay: `${delay}s` }}>
            <div className="flex items-center gap-2 mb-1">
                <span className="text-base">{icon}</span>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    {label}
                </p>
            </div>
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
            {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
        </div>
    );
}

function QuickAction({
    href,
    icon,
    label,
    description,
}: {
    href: string;
    icon: string;
    label: string;
    description: string;
}) {
    return (
        <Link
            href={href}
            className="flex items-start gap-3 p-4 rounded-lg border border-white/10 bg-white/[0.02] hover:bg-white/[0.05] hover:border-indigo-500/30 transition-all group"
        >
            <span className="text-xl mt-0.5">{icon}</span>
            <div>
                <p className="text-sm font-medium text-zinc-200 group-hover:text-white transition-colors">
                    {label}
                </p>
                <p className="text-xs text-muted-foreground">{description}</p>
            </div>
        </Link>
    );
}

// ---- Main Page ----------------------------------------------------------

export default function CaseOverviewPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { data: caseData, isLoading } = useCase(caseId);
    const { activePrep: prep } = usePrep();
    const prepId = prep?.id;

    const { data: scoreData, isLoading: scoreLoading } = useCaseScore(caseId, prepId);
    const { data: deadlines, isLoading: deadlinesLoading } = useCaseDeadlines(caseId);
    const { data: witnesses, isLoading: witnessesLoading } = useCaseWitnesses(caseId, prepId);
    const { data: evidence, isLoading: evidenceLoading } = useCaseEvidence(caseId, prepId);
    const { data: activity, isLoading: activityLoading } = useCaseActivity(caseId);

    const score = scoreData?.score;

    // Parse lists safely
    const witnessList: any[] = Array.isArray(witnesses?.items || witnesses)
        ? (witnesses?.items || witnesses) : [];
    const evidenceList: any[] = Array.isArray(evidence?.items || evidence)
        ? (evidence?.items || evidence) : [];
    const deadlineList: any[] = Array.isArray(deadlines?.items || deadlines)
        ? (deadlines?.items || deadlines) : [];
    const activityList: any[] = Array.isArray(activity?.items || activity)
        ? (activity?.items || activity) : [];

    const now = new Date();
    const upcomingDeadlines = deadlineList
        .filter((d) => new Date(d.due_date || d.date) >= now)
        .sort((a, b) => new Date(a.due_date || a.date).getTime() - new Date(b.due_date || b.date).getTime())
        .slice(0, 3);
    const overdueCount = deadlineList.filter(
        (d) => new Date(d.due_date || d.date) < now && d.status !== "completed"
    ).length;

    const defenseCount = witnessList.filter((w) => /^defense$/i.test(w.type)).length;
    const stateCount = witnessList.filter((w) => /^(state|prosecution)$/i.test(w.type)).length;

    if (isLoading) {
        return (
            <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-24 rounded-lg" />
                    ))}
                </div>
                <Skeleton className="h-48 rounded-lg" />
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

    const basePath = `/cases/${caseId}`;

    return (
        <div className="space-y-6 max-w-7xl">
            {/* Row 1: Readiness + Case Vitals */}
            <div className="flex flex-col lg:flex-row gap-6">
                {/* Readiness Score */}
                <Card className="border-white/5 lg:w-56 flex-shrink-0">
                    <CardContent className="pt-5 pb-4 flex flex-col items-center">
                        {scoreLoading ? (
                            <Skeleton className="w-32 h-32 rounded-full" />
                        ) : score ? (
                            <>
                                <ReadinessGauge score={score.overall} grade={score.grade} />
                                <p className="text-xs text-muted-foreground mt-2">Case Readiness</p>
                            </>
                        ) : (
                            <div className="w-32 h-32 rounded-full border-4 border-dashed border-white/10 flex items-center justify-center">
                                <p className="text-xs text-muted-foreground text-center px-2">
                                    Run analysis to score
                                </p>
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Case Info Cards */}
                <div className="flex-1 grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <StatCard
                        icon="👥" label="Witnesses" delay={0}
                        value={witnessesLoading ? "..." : witnessList.length}
                        sub={witnessList.length > 0 ? `${defenseCount} defense, ${stateCount} state` : "none yet"}
                        color="text-blue-400"
                    />
                    <StatCard
                        icon="📋" label="Evidence" delay={0.06}
                        value={evidenceLoading ? "..." : evidenceList.length}
                        sub={evidenceList.length === 1 ? "item" : "items"}
                        color="text-emerald-400"
                    />
                    <StatCard
                        icon="📅" label="Deadlines" delay={0.12}
                        value={deadlinesLoading ? "..." : upcomingDeadlines.length}
                        sub={overdueCount > 0 ? `${overdueCount} overdue!` : "upcoming"}
                        color={overdueCount > 0 ? "text-red-400" : "text-amber-400"}
                    />
                    <StatCard
                        icon="⚖️" label="Type" delay={0.18}
                        value={caseData.case_type || "—"}
                        sub={caseData.jurisdiction || "no jurisdiction set"}
                        color="text-violet-400"
                    />
                </div>
            </div>

            {/* Row 2: Description (if exists) + Upcoming Deadlines */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Description / Case Notes */}
                <Card className="border-white/5">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">Case Summary</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {caseData.description ? (
                            <p className="text-sm text-muted-foreground whitespace-pre-wrap line-clamp-6">
                                {caseData.description}
                            </p>
                        ) : (
                            <p className="text-sm text-muted-foreground italic">
                                No case description yet. Add one from case settings.
                            </p>
                        )}
                        {/* Key metadata below description */}
                        <div className="flex flex-wrap gap-2 mt-4">
                            {caseData.client_name && (
                                <Badge variant="outline" className="text-xs">
                                    Client: {caseData.client_name}
                                </Badge>
                            )}
                            {caseData.case_category && (
                                <Badge variant="outline" className="text-xs">
                                    {caseData.case_category}
                                </Badge>
                            )}
                            {caseData.sub_phase && (
                                <Badge variant="outline" className="text-xs bg-indigo-500/10 text-indigo-400 border-indigo-500/30">
                                    {caseData.sub_phase}
                                </Badge>
                            )}
                        </div>
                    </CardContent>
                </Card>

                {/* Upcoming Deadlines */}
                <Card className="border-white/5">
                    <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-sm font-medium">Upcoming Deadlines</CardTitle>
                            <Link href={`${basePath}/calendar`} className="text-xs text-indigo-400 hover:text-indigo-300">
                                View all
                            </Link>
                        </div>
                    </CardHeader>
                    <CardContent>
                        {deadlinesLoading ? (
                            <div className="space-y-2">
                                <Skeleton className="h-10 w-full" />
                                <Skeleton className="h-10 w-full" />
                            </div>
                        ) : upcomingDeadlines.length === 0 && overdueCount === 0 ? (
                            <p className="text-sm text-muted-foreground">No upcoming deadlines</p>
                        ) : (
                            <div className="space-y-2">
                                {overdueCount > 0 && (
                                    <div className="flex items-center gap-2 p-2 rounded bg-red-500/10 border border-red-500/20">
                                        <span className="h-2 w-2 rounded-full bg-red-500 shrink-0" />
                                        <p className="text-sm text-red-400 font-medium">
                                            {overdueCount} overdue deadline{overdueCount !== 1 ? "s" : ""}
                                        </p>
                                    </div>
                                )}
                                {upcomingDeadlines.map((d: any, i: number) => (
                                    <div key={i} className="flex items-center justify-between p-2 rounded bg-white/[0.02]">
                                        <div>
                                            <p className="text-sm text-zinc-300">{d.title || d.description}</p>
                                            <p className="text-xs text-muted-foreground">{formatDate(d.due_date || d.date)}</p>
                                        </div>
                                        <span className="text-xs text-muted-foreground shrink-0 ml-2">
                                            {formatRelativeTime(d.due_date || d.date)}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Row 3: Strengths/Vulnerabilities (from score) */}
            {score && (score.strengths?.length > 0 || score.vulnerabilities?.length > 0) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {score.strengths?.length > 0 && (
                        <Card className="border-green-500/10">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-green-400">Key Strengths</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <ul className="space-y-1.5">
                                    {score.strengths.slice(0, 4).map((s: string, i: number) => (
                                        <li key={i} className="text-sm text-zinc-400 flex items-start gap-2">
                                            <span className="text-green-500 mt-0.5 shrink-0">+</span>
                                            {s}
                                        </li>
                                    ))}
                                </ul>
                            </CardContent>
                        </Card>
                    )}
                    {score.vulnerabilities?.length > 0 && (
                        <Card className="border-red-500/10">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-red-400">Vulnerabilities</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <ul className="space-y-1.5">
                                    {score.vulnerabilities.slice(0, 4).map((v: string, i: number) => (
                                        <li key={i} className="text-sm text-zinc-400 flex items-start gap-2">
                                            <span className="text-red-500 mt-0.5 shrink-0">-</span>
                                            {v}
                                        </li>
                                    ))}
                                </ul>
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}

            {/* Row 4: Quick Actions + Recent Activity */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Quick Actions */}
                <div className="lg:col-span-2">
                    <h2 className="text-sm font-medium text-muted-foreground mb-3">Quick Actions</h2>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <QuickAction
                            href={`${basePath}/ask`}
                            icon="💬"
                            label="Ask Your Case"
                            description="AI-powered Q&A across all case data"
                        />
                        <QuickAction
                            href={`${basePath}/war-game`}
                            icon="⚔️"
                            label="War Game"
                            description="5-round adversarial case stress test"
                        />
                        <QuickAction
                            href={`${basePath}/mock-exam`}
                            icon="🎯"
                            label="Mock Examination"
                            description="Practice witness examination with AI"
                        />
                        <QuickAction
                            href={`${basePath}/command-center`}
                            icon="📊"
                            label="Command Center"
                            description="Full tactical dashboard and analytics"
                        />
                    </div>
                </div>

                {/* Recent Activity */}
                <Card className="border-white/5">
                    <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-sm font-medium">Recent Activity</CardTitle>
                            <Link href={`${basePath}/activity`} className="text-xs text-indigo-400 hover:text-indigo-300">
                                View all
                            </Link>
                        </div>
                    </CardHeader>
                    <CardContent>
                        {activityLoading ? (
                            <div className="space-y-2">
                                <Skeleton className="h-8 w-full" />
                                <Skeleton className="h-8 w-full" />
                                <Skeleton className="h-8 w-3/4" />
                            </div>
                        ) : activityList.length === 0 ? (
                            <p className="text-sm text-muted-foreground">No recent activity</p>
                        ) : (
                            <div className="space-y-2">
                                {activityList.slice(0, 5).map((a: any, i: number) => (
                                    <div key={i} className="flex items-start gap-2">
                                        <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1.5 shrink-0" />
                                        <div className="min-w-0">
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

            {/* Row 5: Witness roster (compact) */}
            {witnessList.length > 0 && (
                <Card className="border-white/5">
                    <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-sm font-medium">Witnesses</CardTitle>
                            <Link href={`${basePath}/witnesses`} className="text-xs text-indigo-400 hover:text-indigo-300">
                                Manage
                            </Link>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="flex flex-wrap gap-2">
                            {witnessList.slice(0, 12).map((w: any, i: number) => (
                                <div
                                    key={i}
                                    className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-white/10 bg-white/[0.02]"
                                >
                                    <div className="w-5 h-5 rounded-full bg-indigo-500/20 flex items-center justify-center text-[10px] font-medium text-indigo-400">
                                        {(w.name || "?")[0]}
                                    </div>
                                    <span className="text-xs text-zinc-300">{w.name}</span>
                                    <StatusBadge status={w.type || "unknown"} domain="witness" />
                                </div>
                            ))}
                            {witnessList.length > 12 && (
                                <span className="text-xs text-muted-foreground self-center ml-1">
                                    +{witnessList.length - 12} more
                                </span>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Row 6: Export Panel */}
            <ExportPanel caseId={caseId} />
        </div>
    );
}
