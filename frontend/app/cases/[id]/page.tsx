// ---- Case Overview Page -------------------------------------------------
// The first thing attorneys see when opening a case. Shows case vitals,
// readiness at a glance, upcoming deadlines, and quick-access actions.
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { useCase } from "@/hooks/use-cases";
import { usePrep } from "@/hooks/use-prep";
import { usePrepState } from "@/hooks/use-prep-state";
import { api } from "@/lib/api-client";
import { routes } from "@/lib/api-routes";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { formatDate, formatRelativeTime } from "@/lib/constants";
import { ExportPanel } from "@/components/export-panel";
import { StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ShieldCheck, AlertTriangle } from "lucide-react";

/* eslint-disable @typescript-eslint/no-explicit-any */

type TokenFn = () => Promise<string | null>;

// ---- Data Hooks ---------------------------------------------------------

function useCaseScore(caseId: string, prepId: string | undefined, getToken: TokenFn) {
    return useQuery<any>({
        queryKey: [...queryKeys.predictiveScore.score(caseId, prepId || "")],
        queryFn: () => api.get(routes.predictiveScore.score(caseId, prepId!), { getToken }),
        enabled: !!prepId,
        retry: false,
    });
}

function useCaseDeadlines(caseId: string, getToken: TokenFn) {
    return useQuery<any>({
        queryKey: [...queryKeys.calendar.deadlines(caseId)],
        queryFn: () => api.get(routes.calendar.deadlines(caseId), { getToken }),
        retry: false,
    });
}

function useCaseWitnesses(caseId: string, prepId: string | undefined, getToken: TokenFn) {
    return useQuery<any>({
        queryKey: [...queryKeys.witnesses.list(caseId, prepId || "")],
        queryFn: () => api.get(routes.witnesses.list(caseId, prepId!), { getToken }),
        enabled: !!prepId,
        retry: false,
    });
}

function useCaseEvidence(caseId: string, prepId: string | undefined, getToken: TokenFn) {
    return useQuery<any>({
        queryKey: [...queryKeys.evidence.list(caseId, prepId || "")],
        queryFn: () => api.get(routes.evidence.list(caseId, prepId!), { getToken }),
        enabled: !!prepId,
        retry: false,
    });
}

function useCaseActivity(caseId: string, getToken: TokenFn) {
    return useQuery<any>({
        queryKey: [...queryKeys.activity.feed(caseId)],
        queryFn: () => api.get(`${routes.activity.feed(caseId)}?limit=5`, { getToken }),
        retry: false,
    });
}

function useCaseFiles(caseId: string, getToken: TokenFn) {
    return useQuery<any>({
        queryKey: [...queryKeys.files.list(caseId)],
        queryFn: () => api.get(routes.files.list(caseId), { getToken }),
        retry: false,
    });
}

// ---- Phase Steps --------------------------------------------------------

function getPhaseSteps(caseType: string): { key: string; label: string }[] {
    switch (caseType) {
        case "criminal":
            return [
                { key: "Arrest & Booking", label: "Arrest & Booking" },
                { key: "First Appearance", label: "First Appearance" },
                { key: "Arraignment", label: "Arraignment" },
                { key: "Discovery", label: "Discovery" },
                { key: "Pre-Trial Motions", label: "Pre-Trial Motions" },
                { key: "Plea Negotiations", label: "Plea Negotiations" },
                { key: "Trial Preparation", label: "Trial Preparation" },
                { key: "Trial", label: "Trial" },
                { key: "Sentencing", label: "Sentencing" },
            ];
        case "criminal-juvenile":
            return [
                { key: "Intake & Detention", label: "Intake & Detention" },
                { key: "Arraignment", label: "Arraignment" },
                { key: "Discovery", label: "Discovery" },
                { key: "Pre-Trial Motions", label: "Pre-Trial Motions" },
                { key: "Plea Negotiations", label: "Plea Negotiations" },
                { key: "Adjudication", label: "Adjudication" },
                { key: "Disposition", label: "Disposition" },
                { key: "Post-Disposition", label: "Post-Disposition" },
            ];
        case "civil-plaintiff":
            return [
                { key: "Complaint Filed", label: "Complaint Filed" },
                { key: "Service of Process", label: "Service of Process" },
                { key: "Answer/Response", label: "Answer/Response" },
                { key: "Discovery", label: "Discovery" },
                { key: "Depositions", label: "Depositions" },
                { key: "Mediation", label: "Mediation" },
                { key: "Pre-Trial Motions", label: "Pre-Trial Motions" },
                { key: "Trial Preparation", label: "Trial Preparation" },
                { key: "Trial", label: "Trial" },
            ];
        case "civil-defendant":
            return [
                { key: "Complaint Received", label: "Complaint Received" },
                { key: "Answer Filed", label: "Answer Filed" },
                { key: "Discovery", label: "Discovery" },
                { key: "Depositions", label: "Depositions" },
                { key: "Mediation", label: "Mediation" },
                { key: "Pre-Trial Motions", label: "Pre-Trial Motions" },
                { key: "Trial Preparation", label: "Trial Preparation" },
                { key: "Trial", label: "Trial" },
            ];
        case "civil-juvenile":
            return [
                { key: "Petition Filed", label: "Petition Filed" },
                { key: "Service & Response", label: "Service & Response" },
                { key: "Discovery", label: "Discovery" },
                { key: "Mediation", label: "Mediation" },
                { key: "Pre-Trial", label: "Pre-Trial" },
                { key: "Adjudication", label: "Adjudication" },
                { key: "Disposition", label: "Disposition" },
            ];
        default:
            return [
                { key: "Filed", label: "Filed" },
                { key: "Discovery", label: "Discovery" },
                { key: "Pre-Trial", label: "Pre-Trial" },
                { key: "Trial", label: "Trial" },
                { key: "Resolution", label: "Resolution" },
            ];
    }
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
                    stroke="currentColor" className="text-muted-foreground/10" strokeWidth="8"
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
    color = "text-foreground",
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
            className="flex items-start gap-3 p-4 rounded-lg border border-border bg-muted/30 hover:bg-muted/50 hover:border-indigo-500/30 transition-all group stagger-item"
        >
            <span className="text-xl mt-0.5">{icon}</span>
            <div>
                <p className="text-sm font-medium text-foreground group-hover:text-foreground transition-colors">
                    {label}
                </p>
                <p className="text-xs text-muted-foreground">{description}</p>
            </div>
        </Link>
    );
}

// ---- Next Step Banner ---------------------------------------------------

function NextStepBanner({
    hasFiles,
    hasAnalysis,
    score,
    witnessCount,
    hasOverdueDeadlines,
    caseId,
}: {
    hasFiles: boolean;
    hasAnalysis: boolean;
    score: number | null;
    witnessCount: number;
    hasOverdueDeadlines: boolean;
    caseId: string;
}) {
    let message = "";
    let action = { label: "", href: "" };

    if (hasOverdueDeadlines) {
        message = "You have overdue deadlines that need attention";
        action = { label: "View Calendar", href: `/cases/${caseId}/calendar` };
    } else if (!hasFiles) {
        message = "Upload case documents to begin AI-powered analysis";
        action = { label: "Upload Files", href: `/cases/${caseId}/documents` };
    } else if (!hasAnalysis) {
        message = "Run AI analysis on your uploaded documents";
        action = { label: "Start Analysis", href: `/cases/${caseId}/analysis` };
    } else if (score !== null && score < 60) {
        message = "Your case readiness score needs attention — review analysis gaps";
        action = { label: "Review Analysis", href: `/cases/${caseId}/analysis` };
    } else if (witnessCount === 0) {
        message = "Define witnesses for cross and direct examination planning";
        action = { label: "Add Witnesses", href: `/cases/${caseId}/witnesses` };
    } else if (score !== null && score >= 80) {
        message = "Case is well-prepared — run a War Game to test vulnerabilities";
        action = { label: "War Game", href: `/cases/${caseId}/war-game` };
    }

    if (!message) return null;

    return (
        <Card className="relative overflow-hidden border-amber-500/30 bg-amber-500/5">
            <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-amber-400 to-orange-500" />
            <CardContent className="py-3 pl-5 flex items-center gap-3">
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    className="w-5 h-5 text-amber-400 shrink-0"
                    aria-hidden="true"
                >
                    <path d="M12 2a7 7 0 0 0-7 7c0 2.38 1.19 4.47 3 5.74V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.26c1.81-1.27 3-3.36 3-5.74a7 7 0 0 0-7-7ZM9 21a1 1 0 0 0 1 1h4a1 1 0 0 0 1-1v-1H9v1Z" />
                </svg>
                <p className="text-sm flex-1">{message}</p>
                <Link href={action.href}>
                    <Button size="sm" variant="outline" className="shrink-0">
                        {action.label}
                    </Button>
                </Link>
            </CardContent>
        </Card>
    );
}

// ---- Phase Timeline -----------------------------------------------------

function PhaseTimeline({
    currentPhase,
    subPhase,
    caseType,
}: {
    currentPhase: string;
    subPhase: string;
    caseType: string;
}) {
    const phases = getPhaseSteps(caseType);
    const currentIdx = phases.findIndex((p) => p.key === subPhase);

    // If the case is Closed or Archived, mark all phases complete
    const allComplete = currentPhase === "Closed" || currentPhase === "Archived";

    return (
        <Card className="border-border/50">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Case Progress</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="relative pl-6">
                    {/* Vertical line */}
                    <div className="absolute left-[11px] top-2 bottom-2 w-0.5 bg-border" />
                    <div className="space-y-3">
                        {phases.map((phase, i) => {
                            const isComplete = allComplete || i < currentIdx;
                            const isCurrent = !allComplete && i === currentIdx;
                            const isFuture = !allComplete && (currentIdx === -1 ? true : i > currentIdx);

                            return (
                                <div key={phase.key} className="relative flex items-center gap-3">
                                    {/* Dot */}
                                    <div
                                        className={cn(
                                            "absolute -left-6 w-[22px] h-[22px] rounded-full border-2 flex items-center justify-center text-[10px] font-bold",
                                            isComplete &&
                                                "bg-emerald-500 border-emerald-500 text-white",
                                            isCurrent &&
                                                "bg-primary border-primary text-primary-foreground animate-pulse",
                                            isFuture &&
                                                "bg-muted border-border text-muted-foreground",
                                        )}
                                    >
                                        {isComplete ? (
                                            <svg
                                                xmlns="http://www.w3.org/2000/svg"
                                                viewBox="0 0 20 20"
                                                fill="currentColor"
                                                className="w-3 h-3"
                                            >
                                                <path
                                                    fillRule="evenodd"
                                                    d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
                                                    clipRule="evenodd"
                                                />
                                            </svg>
                                        ) : (
                                            i + 1
                                        )}
                                    </div>
                                    <div>
                                        <p
                                            className={cn(
                                                "text-sm",
                                                isCurrent
                                                    ? "font-semibold text-foreground"
                                                    : "text-muted-foreground",
                                            )}
                                        >
                                            {phase.label}
                                        </p>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

// ---- Main Page ----------------------------------------------------------

export default function CaseOverviewPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { data: caseData, isLoading } = useCase(caseId);
    const { activePrep: prep } = usePrep();
    const prepId = prep?.id;

    const { data: scoreData, isLoading: scoreLoading } = useCaseScore(caseId, prepId, getToken);
    const { data: deadlines, isLoading: deadlinesLoading } = useCaseDeadlines(caseId, getToken);
    const { data: witnesses, isLoading: witnessesLoading } = useCaseWitnesses(caseId, prepId, getToken);
    const { data: evidence, isLoading: evidenceLoading } = useCaseEvidence(caseId, prepId, getToken);
    const { data: activity, isLoading: activityLoading } = useCaseActivity(caseId, getToken);
    const { data: filesData } = useCaseFiles(caseId, getToken);
    const { sections: prepSections } = usePrepState(caseId, prepId ?? null);

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

    // Derived values for NextStepBanner
    const filesList: any[] = Array.isArray(filesData?.items || filesData)
        ? (filesData?.items || filesData) : [];
    const hasFiles = filesList.length > 0;
    const hasAnalysis = !!prepSections.caseSummary;
    const overallScore: number | null = score?.overall ?? null;

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
            {/* Next Step Recommendation Banner */}
            <NextStepBanner
                hasFiles={hasFiles}
                hasAnalysis={hasAnalysis}
                score={overallScore}
                witnessCount={witnessList.length}
                hasOverdueDeadlines={overdueCount > 0}
                caseId={caseId}
            />

            {/* Row 1: Readiness + Case Vitals */}
            <div className="flex flex-col lg:flex-row gap-6">
                {/* Readiness Score */}
                <Card className="border-border/50 lg:w-56 flex-shrink-0">
                    <CardContent className="pt-5 pb-4 flex flex-col items-center">
                        {scoreLoading ? (
                            <Skeleton className="w-32 h-32 rounded-full" />
                        ) : score ? (
                            <>
                                <ReadinessGauge score={score.overall} grade={score.grade} />
                                <p className="text-xs text-muted-foreground mt-2">Case Readiness</p>
                            </>
                        ) : (
                            <div className="w-32 h-32 rounded-full border-4 border-dashed border-border flex items-center justify-center">
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

            {/* Case Phase Timeline */}
            {caseData.case_type && caseData.phase && (
                <PhaseTimeline
                    currentPhase={caseData.phase}
                    subPhase={caseData.sub_phase || ""}
                    caseType={caseData.case_type}
                />
            )}

            {/* Row 2: Description (if exists) + Upcoming Deadlines */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Description / Case Notes */}
                <Card className="border-border/50">
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
                <Card className="border-border/50">
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
                                    <div key={i} className="flex items-center justify-between p-2 rounded bg-muted/30">
                                        <div>
                                            <p className="text-sm text-foreground/90">{d.title || d.description}</p>
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
                        <Card className="border-emerald-500/10">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-emerald-400 flex items-center gap-2">
                                    <ShieldCheck className="h-4 w-4" />
                                    Key Strengths
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-2">
                                    {score.strengths.slice(0, 4).map((s: string, i: number) => (
                                        <div
                                            key={i}
                                            className="flex items-start gap-2.5 border-l-2 border-l-emerald-500 bg-emerald-500/5 rounded-md px-3 py-2"
                                        >
                                            <ShieldCheck className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                                            <span className="text-sm text-foreground/90">{s}</span>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    )}
                    {score.vulnerabilities?.length > 0 && (
                        <Card className="border-red-500/10">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-red-400 flex items-center gap-2">
                                    <AlertTriangle className="h-4 w-4" />
                                    Vulnerabilities
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-2">
                                    {score.vulnerabilities.slice(0, 4).map((v: string, i: number) => (
                                        <div
                                            key={i}
                                            className="flex items-start gap-2.5 border-l-2 border-l-red-500 bg-red-500/5 rounded-md px-3 py-2"
                                        >
                                            <AlertTriangle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                                            <span className="text-sm text-foreground/90">{v}</span>
                                        </div>
                                    ))}
                                </div>
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
                            href={`${basePath}/analysis`}
                            icon="🔬"
                            label="Run Analysis"
                            description="AI analysis pipeline — 14 modules across all documents"
                        />
                        <QuickAction
                            href={`${basePath}/documents`}
                            icon="📝"
                            label="Draft Document"
                            description="Civil complaint, motions, briefs, and more"
                        />
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
                <Card className="border-border/50">
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
                                            <p className="text-sm text-foreground/90 truncate">
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
                <Card className="border-border/50">
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
                            {witnessList.slice(0, 12).map((w: any, i: number) => {
                                const wType = (w.type || "").toLowerCase();
                                const dotColor =
                                    /^(state|prosecution)$/i.test(wType)
                                        ? "bg-amber-500"
                                        : /^defense$/i.test(wType)
                                          ? "bg-blue-500"
                                          : /^expert$/i.test(wType)
                                            ? "bg-violet-500"
                                            : /^character$/i.test(wType)
                                              ? "bg-emerald-500"
                                              : "bg-zinc-500";
                                const avatarColor =
                                    /^(state|prosecution)$/i.test(wType)
                                        ? "bg-amber-500/20 text-amber-400"
                                        : /^defense$/i.test(wType)
                                          ? "bg-blue-500/20 text-blue-400"
                                          : /^expert$/i.test(wType)
                                            ? "bg-violet-500/20 text-violet-400"
                                            : /^character$/i.test(wType)
                                              ? "bg-emerald-500/20 text-emerald-400"
                                              : "bg-indigo-500/20 text-indigo-400";
                                return (
                                    <div
                                        key={i}
                                        className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-border bg-muted/30"
                                    >
                                        <div className={`w-5 h-5 rounded-full ${avatarColor} flex items-center justify-center text-[10px] font-medium`}>
                                            {(w.name || "?")[0]}
                                        </div>
                                        <span className="text-xs text-foreground/90">{w.name}</span>
                                        <div className="flex items-center gap-1.5">
                                            <span className={`w-2 h-2 rounded-full ${dotColor} shrink-0`} />
                                            <StatusBadge status={w.type || "unknown"} domain="witness" />
                                        </div>
                                    </div>
                                );
                            })}
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
