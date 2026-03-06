// ---- Compliance Suite (7-Tab) -------------------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { routes } from "@/lib/api-routes";
import { queryKeys } from "@/lib/query-keys";
import { formatDate, formatCurrency, SEVERITY_COLORS, PRIORITY_COLORS, GENERIC_STATUS_COLORS, getStatusColor } from "@/lib/constants";
import { StatusBadge } from "@/components/shared/status-badge";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import type {
    ComplianceDashboard,
    SmartConflictMatch,
    SmartConflictResult,
    ProspectiveClient,
    FeeAgreementData,
    SupervisionEntry,
} from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Local Interfaces
// ---------------------------------------------------------------------------

interface TrustEntry {
    id: string;
    date: string;
    amount: number;
    type: string;
    description: string;
}

interface TrustData {
    entries: TrustEntry[];
    balance: number;
}

interface SOLClaim {
    id: string;
    claim_type: string;
    incident_date: string;
    discovery_date?: string;
    deadline: string;
    days_remaining: number | null;
    urgency: string;
    urgency_level: string;
    description?: string;
    tolling_notes?: string;
}

interface SOLData {
    claims: SOLClaim[];
    notes?: string;
}

interface FeeAgreementResponse {
    agreement: FeeAgreementData | null;
    status: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function SOLBadge({ claim }: { claim: SOLClaim }) {
    const days = claim.days_remaining;
    if (days === null || days === undefined) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                N/A
            </span>
        );
    }
    if (days < 0) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                EXPIRED
            </span>
        );
    }
    if (days <= 30) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-800 animate-pulse dark:bg-red-900/40 dark:text-red-300">
                {days} days
            </span>
        );
    }
    if (days <= 90) {
        return (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
                {days} days
            </span>
        );
    }
    return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300">
            {days} days
        </span>
    );
}

function scoreColor(score: number): string {
    if (score >= 80) return "text-emerald-500";
    if (score >= 60) return "text-amber-500";
    return "text-red-500";
}

function matchTypeBadgeVariant(matchType: string): string {
    switch (matchType) {
        case "exact":
        case "nickname":
            return "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300";
        case "fuzzy":
        case "initial":
            return "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300";
        case "partial":
            return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300";
        case "substring":
            return "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300";
        default:
            return "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";
    }
}

function todayString(): string {
    return new Date().toISOString().split("T")[0];
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function CompliancePage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();

    // ---- Query Keys ----
    const keys = {
        dashboard: ["compliance", "dashboard"],
        conflicts: ["compliance", "conflicts", caseId],
        prospective: [...queryKeys.compliance.prospectiveClients],
        trust: ["compliance", "trust", caseId],
        feeAgreement: [...queryKeys.compliance.feeAgreement(caseId)],
        sol: [...queryKeys.compliance.solClaims(caseId)],
        supervision: [...queryKeys.compliance.supervision(caseId)],
    };

    // ---- State for forms ----
    const [showProspectiveForm, setShowProspectiveForm] = useState(false);
    const [prospectiveForm, setProspectiveForm] = useState({
        name: "",
        subject: "",
        disclosed_info: "",
        date: todayString(),
        notes: "",
    });
    const [deleteProspectiveId, setDeleteProspectiveId] = useState<string | null>(null);

    const [showTrustForm, setShowTrustForm] = useState(false);
    const [trustForm, setTrustForm] = useState({
        type: "deposit",
        amount: "",
        description: "",
        date: todayString(),
    });

    const [feeForm, setFeeForm] = useState<{
        fee_type: string;
        rate: string;
        retainer: string;
        scope: string;
        signed: boolean;
        signed_date: string;
    }>({
        fee_type: "hourly",
        rate: "",
        retainer: "",
        scope: "",
        signed: false,
        signed_date: "",
    });
    const [feeFormLoaded, setFeeFormLoaded] = useState(false);

    const [showSolForm, setShowSolForm] = useState(false);
    const [solForm, setSolForm] = useState({
        claim_type: "",
        incident_date: "",
        discovery_date: "",
        deadline: "",
        description: "",
        tolling_notes: "",
    });

    const [showSupervisionForm, setShowSupervisionForm] = useState(false);
    const [supervisionForm, setSupervisionForm] = useState({
        task: "",
        assignee: "",
        supervisor: "",
        status: "assigned",
        notes: "",
    });

    // ---- Queries ----

    const dashboardQuery = useQuery({
        queryKey: keys.dashboard,
        queryFn: () => api.get<ComplianceDashboard>("/compliance/dashboard", { getToken }),
    });

    const conflictScanQuery = useQuery({
        queryKey: keys.conflicts,
        queryFn: () => api.get<SmartConflictResult | null>(`/compliance/conflicts/${caseId}`, { getToken }),
        enabled: false, // manually triggered via scan button
    });

    const prospectiveQuery = useQuery({
        queryKey: keys.prospective,
        queryFn: () => api.get<ProspectiveClient[]>(routes.compliance.prospectiveClients, { getToken }),
    });

    const trustQuery = useQuery({
        queryKey: keys.trust,
        queryFn: () => api.get<TrustData>(`/compliance/trust/${caseId}`, { getToken }),
    });

    const feeQuery = useQuery({
        queryKey: keys.feeAgreement,
        queryFn: () => api.get<FeeAgreementResponse>(routes.compliance.feeAgreement(caseId), { getToken }),
    });

    const solQuery = useQuery({
        queryKey: keys.sol,
        queryFn: () => api.get<SOLData>(routes.compliance.solClaims(caseId), { getToken }),
    });

    const supervisionQuery = useQuery({
        queryKey: keys.supervision,
        queryFn: () => api.get<SupervisionEntry[]>(routes.compliance.supervision(caseId), { getToken }),
    });

    // ---- Populate fee form when data loads ----
    if (feeQuery.data?.agreement && !feeFormLoaded) {
        const a = feeQuery.data.agreement;
        setFeeForm({
            fee_type: a.fee_type || "hourly",
            rate: a.rate || "",
            retainer: a.retainer || "",
            scope: a.scope || "",
            signed: a.signed || false,
            signed_date: a.signed_date || "",
        });
        setFeeFormLoaded(true);
    }

    // ---- Mutations ----

    const scanConflicts = useMutationWithToast<void, SmartConflictResult>({
        mutationFn: () => api.post<SmartConflictResult>(routes.compliance.scan(caseId), {}, { getToken }),
        successMessage: "Conflict scan complete",
        errorMessage: "Conflict scan failed",
        invalidateKeys: [keys.conflicts],
    });

    const createProspective = useMutationWithToast<typeof prospectiveForm>({
        mutationFn: (data) => api.post(routes.compliance.prospectiveClients, data, { getToken }),
        successMessage: "Prospective client added",
        errorMessage: "Failed to add prospective client",
        invalidateKeys: [keys.prospective, keys.dashboard],
        onSuccess: () => {
            setShowProspectiveForm(false);
            setProspectiveForm({ name: "", subject: "", disclosed_info: "", date: todayString(), notes: "" });
        },
    });

    const deleteProspective = useMutationWithToast<string>({
        mutationFn: (id) => api.delete(routes.compliance.prospectiveClient(id), { getToken }),
        successMessage: "Prospective client removed",
        errorMessage: "Failed to delete",
        invalidateKeys: [keys.prospective, keys.dashboard],
        onSuccess: () => setDeleteProspectiveId(null),
    });

    const createTrustEntry = useMutationWithToast<typeof trustForm>({
        mutationFn: (data) =>
            api.post(`/compliance/trust/${caseId}`, {
                ...data,
                amount: parseFloat(data.amount) || 0,
            }, { getToken }),
        successMessage: "Trust entry added",
        errorMessage: "Failed to add trust entry",
        invalidateKeys: [keys.trust, keys.dashboard],
        onSuccess: () => {
            setShowTrustForm(false);
            setTrustForm({ type: "deposit", amount: "", description: "", date: todayString() });
        },
    });

    const saveFeeAgreement = useMutationWithToast<typeof feeForm>({
        mutationFn: (data) => api.post(routes.compliance.feeAgreement(caseId), data, { getToken }),
        successMessage: "Fee agreement saved",
        errorMessage: "Failed to save fee agreement",
        invalidateKeys: [keys.feeAgreement, keys.dashboard],
    });

    const createSolClaim = useMutationWithToast<typeof solForm>({
        mutationFn: (data) => {
            const payload: Record<string, string> = {
                claim_type: data.claim_type,
                incident_date: data.incident_date,
                deadline: data.deadline,
                description: data.description,
            };
            if (data.discovery_date) payload.discovery_date = data.discovery_date;
            if (data.tolling_notes) payload.tolling_notes = data.tolling_notes;
            return api.post(routes.compliance.solClaims(caseId), payload, { getToken });
        },
        successMessage: "SOL claim added",
        errorMessage: "Failed to add SOL claim",
        invalidateKeys: [keys.sol, keys.dashboard],
        onSuccess: () => {
            setShowSolForm(false);
            setSolForm({ claim_type: "", incident_date: "", discovery_date: "", deadline: "", description: "", tolling_notes: "" });
        },
    });

    const deleteSolClaim = useMutationWithToast<string>({
        mutationFn: (claimId) => api.delete(routes.compliance.solClaim(caseId, claimId), { getToken }),
        successMessage: "SOL claim removed",
        errorMessage: "Failed to delete claim",
        invalidateKeys: [keys.sol, keys.dashboard],
    });

    const createSupervision = useMutationWithToast<typeof supervisionForm>({
        mutationFn: (data) => api.post(routes.compliance.supervision(caseId), data, { getToken }),
        successMessage: "Supervision entry added",
        errorMessage: "Failed to add entry",
        invalidateKeys: [keys.supervision],
        onSuccess: () => {
            setShowSupervisionForm(false);
            setSupervisionForm({ task: "", assignee: "", supervisor: "", status: "assigned", notes: "" });
        },
    });

    // ---- Derived data ----
    const dashboard = dashboardQuery.data;
    const scanResult = scanConflicts.data as SmartConflictResult | undefined;
    const prospectiveClients = prospectiveQuery.data ?? [];
    const trustData = trustQuery.data;
    const trustEntries = trustData?.entries ?? [];
    const trustBalance = trustData?.balance ?? 0;
    const feeAgreement = feeQuery.data;
    const solData = solQuery.data;
    const solClaims = solData?.claims ?? [];
    const supervisionEntries = supervisionQuery.data ?? [];

    // =====================================================================
    // RENDER
    // =====================================================================

    return (
        <div className="space-y-6">
            <Tabs defaultValue="dashboard">
                <TabsList className="flex-wrap">
                    <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
                    <TabsTrigger value="conflicts">Conflict Scanner</TabsTrigger>
                    <TabsTrigger value="prospective">Prospective Clients</TabsTrigger>
                    <TabsTrigger value="trust">Trust Accounts</TabsTrigger>
                    <TabsTrigger value="fees">Fee Agreements</TabsTrigger>
                    <TabsTrigger value="sol">SOL Tracker</TabsTrigger>
                    <TabsTrigger value="supervision">Supervision</TabsTrigger>
                </TabsList>

                {/* ============================================================
                    TAB 1: DASHBOARD
                   ============================================================ */}
                <TabsContent value="dashboard" className="space-y-6 mt-4">
                    {dashboardQuery.isLoading ? (
                        <div className="space-y-4">
                            {Array.from({ length: 4 }).map((_, i) => (
                                <Skeleton key={i} className="h-24 w-full rounded-lg" />
                            ))}
                        </div>
                    ) : dashboard ? (
                        <>
                            {/* Score + Issues */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <Card className="glass-card">
                                    <CardContent className="pt-6 pb-4 text-center">
                                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                                            Compliance Score
                                        </p>
                                        <p className={`text-6xl font-black mt-2 ${scoreColor(dashboard.score)}`}>
                                            {dashboard.score}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-1">out of 100</p>
                                    </CardContent>
                                </Card>
                                <Card className="glass-card">
                                    <CardContent className="pt-6 pb-4 text-center">
                                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                                            Total Issues
                                        </p>
                                        <p className={`text-6xl font-black mt-2 ${dashboard.total_issues > 0 ? "text-red-500" : "text-emerald-500"}`}>
                                            {dashboard.total_issues}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-1">requiring attention</p>
                                    </CardContent>
                                </Card>
                            </div>

                            {/* Overdue Deadlines */}
                            {dashboard.overdue_deadlines.length > 0 && (
                                <Card className="border-red-500/30">
                                    <CardHeader>
                                        <CardTitle className="text-base flex items-center gap-2">
                                            <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
                                            Overdue Deadlines
                                            <Badge variant="destructive" className="ml-auto">
                                                {dashboard.overdue_deadlines.length}
                                            </Badge>
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-2">
                                            {dashboard.overdue_deadlines.map((d, i) => (
                                                <div
                                                    key={i}
                                                    className="flex items-center justify-between py-2 border-b border-border last:border-0 text-sm"
                                                >
                                                    <div>
                                                        <p className="font-medium">{String(d.title || d.name || "Deadline")}</p>
                                                        <p className="text-xs text-muted-foreground">
                                                            {String(d.case_name || "")} {d.date ? `- ${String(d.date)}` : ""}
                                                        </p>
                                                    </div>
                                                    <Badge variant="destructive">Overdue</Badge>
                                                </div>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            )}

                            {/* Upcoming Deadlines */}
                            {dashboard.upcoming_deadlines.length > 0 && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="text-base flex items-center gap-2">
                                            Upcoming Deadlines
                                            <Badge variant="secondary" className="ml-auto">
                                                {dashboard.upcoming_deadlines.length}
                                            </Badge>
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-2">
                                            {dashboard.upcoming_deadlines.map((d, i) => (
                                                <div
                                                    key={i}
                                                    className="flex items-center justify-between py-2 border-b border-border last:border-0 text-sm"
                                                >
                                                    <div>
                                                        <p className="font-medium">{String(d.title || d.name || "Deadline")}</p>
                                                        <p className="text-xs text-muted-foreground">
                                                            {String(d.case_name || "")} {d.date ? `- ${String(d.date)}` : ""}
                                                        </p>
                                                    </div>
                                                    <Badge variant="outline">{String(d.date || "")}</Badge>
                                                </div>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            )}

                            {/* Communication Gaps */}
                            {dashboard.communication_gaps.length > 0 && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="text-base">
                                            Communication Gaps
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-sm">
                                                <thead>
                                                    <tr className="border-b border-border text-left">
                                                        <th className="pb-2 font-medium text-muted-foreground">Case</th>
                                                        <th className="pb-2 font-medium text-muted-foreground">Last Contact</th>
                                                        <th className="pb-2 font-medium text-muted-foreground">Days Since</th>
                                                        <th className="pb-2 font-medium text-muted-foreground">Urgency</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {dashboard.communication_gaps.map((gap, i) => (
                                                        <tr key={i} className="border-b border-border last:border-0">
                                                            <td className="py-2">{gap.case_name}</td>
                                                            <td className="py-2 text-muted-foreground">
                                                                {gap.last_contact || "Never"}
                                                            </td>
                                                            <td className="py-2">
                                                                {gap.days_since !== null ? gap.days_since : "N/A"}
                                                            </td>
                                                            <td className="py-2">
                                                                <StatusBadge status={gap.urgency} domain="priority" />
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </CardContent>
                                </Card>
                            )}

                            {/* Missing Fee Agreements */}
                            {dashboard.missing_fee_agreements.length > 0 && (
                                <Card className="border-amber-500/30">
                                    <CardHeader>
                                        <CardTitle className="text-base flex items-center gap-2">
                                            Missing Fee Agreements
                                            <Badge className="ml-auto bg-amber-500/20 text-amber-600 dark:text-amber-400">
                                                {dashboard.missing_fee_agreements.length}
                                            </Badge>
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                            {dashboard.missing_fee_agreements.map((item, i) => (
                                                <Card key={i} className="border-amber-500/20">
                                                    <CardContent className="py-3">
                                                        <p className="text-sm font-medium">
                                                            {String(item.case_name || item.name || `Case ${i + 1}`)}
                                                        </p>
                                                        <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                                                            No fee agreement on file
                                                        </p>
                                                    </CardContent>
                                                </Card>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            )}

                            {/* Prospective Client Count */}
                            <Card>
                                <CardContent className="pt-4 pb-3">
                                    <p className="text-xs font-medium text-muted-foreground uppercase">
                                        Prospective Clients Tracked
                                    </p>
                                    <p className="text-2xl font-bold mt-1">{dashboard.prospective_count}</p>
                                </CardContent>
                            </Card>
                        </>
                    ) : (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                Unable to load compliance dashboard.
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>

                {/* ============================================================
                    TAB 2: CONFLICT SCANNER
                   ============================================================ */}
                <TabsContent value="conflicts" className="space-y-6 mt-4">
                    <Card className="glass-card">
                        <CardHeader>
                            <CardTitle className="text-base flex items-center justify-between">
                                Conflict of Interest Scanner
                                <Button
                                    size="sm"
                                    onClick={() => scanConflicts.mutate()}
                                    disabled={scanConflicts.isPending}
                                >
                                    {scanConflicts.isPending ? "Scanning..." : "Scan Conflicts"}
                                </Button>
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {scanConflicts.isPending && (
                                <div className="space-y-3">
                                    <Skeleton className="h-6 w-48" />
                                    <Skeleton className="h-20 w-full rounded-lg" />
                                    <Skeleton className="h-20 w-full rounded-lg" />
                                </div>
                            )}

                            {scanResult && !scanConflicts.isPending && (
                                <div className="space-y-4">
                                    {/* Stats */}
                                    <div className="flex gap-4 text-sm">
                                        <div>
                                            <span className="text-muted-foreground">Cases scanned: </span>
                                            <span className="font-bold">{scanResult.cases_scanned}</span>
                                        </div>
                                        <div>
                                            <span className="text-muted-foreground">Entities checked: </span>
                                            <span className="font-bold">{scanResult.entities_checked}</span>
                                        </div>
                                    </div>

                                    {/* Conflict Matches */}
                                    {scanResult.conflicts.length === 0 ? (
                                        <div className="text-center py-6">
                                            <Badge variant="outline" className="text-emerald-500 border-emerald-500/30 text-sm px-4 py-1">
                                                No conflicts found
                                            </Badge>
                                        </div>
                                    ) : (
                                        <div className="space-y-3">
                                            <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                                                Conflict Matches ({scanResult.conflicts.length})
                                            </h4>
                                            {scanResult.conflicts.map((match, i) => (
                                                <ConflictMatchCard key={i} match={match} />
                                            ))}
                                        </div>
                                    )}

                                    {/* Prospective Client Hits */}
                                    {scanResult.prospective_hits.length > 0 && (
                                        <div className="space-y-3 mt-4">
                                            <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                                                Prospective Client Hits ({scanResult.prospective_hits.length})
                                            </h4>
                                            {scanResult.prospective_hits.map((match, i) => (
                                                <ConflictMatchCard key={`p-${i}`} match={match} />
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}

                            {!scanResult && !scanConflicts.isPending && (
                                <p className="text-sm text-muted-foreground text-center py-6">
                                    Click &quot;Scan Conflicts&quot; to check for conflicts of interest across all cases and prospective clients.
                                </p>
                            )}

                            <div className="mt-4 pt-4 border-t border-border">
                                <p className="text-xs text-muted-foreground">
                                    For firm-wide conflict checks, visit the{" "}
                                    <a href="/conflicts" className="text-primary underline hover:no-underline">
                                        Conflicts page
                                    </a>{" "}
                                    &rarr;
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ============================================================
                    TAB 3: PROSPECTIVE CLIENTS (RPC 1.18)
                   ============================================================ */}
                <TabsContent value="prospective" className="space-y-4 mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center justify-between">
                                Prospective Clients (RPC 1.18)
                                <Button
                                    size="sm"
                                    onClick={() => setShowProspectiveForm(!showProspectiveForm)}
                                >
                                    {showProspectiveForm ? "Cancel" : "+ Add Prospective Client"}
                                </Button>
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {/* Add Form */}
                            {showProspectiveForm && (
                                <div className="border border-border rounded-lg p-4 mb-4 space-y-3 bg-muted/30">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                        <div>
                                            <Label htmlFor="pc-name">Name *</Label>
                                            <Input
                                                id="pc-name"
                                                value={prospectiveForm.name}
                                                onChange={(e) => setProspectiveForm({ ...prospectiveForm, name: e.target.value })}
                                                placeholder="Full name"
                                            />
                                        </div>
                                        <div>
                                            <Label htmlFor="pc-subject">Subject Matter *</Label>
                                            <Input
                                                id="pc-subject"
                                                value={prospectiveForm.subject}
                                                onChange={(e) => setProspectiveForm({ ...prospectiveForm, subject: e.target.value })}
                                                placeholder="Subject of consultation"
                                            />
                                        </div>
                                    </div>
                                    <div>
                                        <Label htmlFor="pc-disclosed">Disclosed Information</Label>
                                        <Textarea
                                            id="pc-disclosed"
                                            value={prospectiveForm.disclosed_info}
                                            onChange={(e) => setProspectiveForm({ ...prospectiveForm, disclosed_info: e.target.value })}
                                            placeholder="Information disclosed during consultation"
                                            rows={3}
                                        />
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                        <div>
                                            <Label htmlFor="pc-date">Date</Label>
                                            <Input
                                                id="pc-date"
                                                type="date"
                                                value={prospectiveForm.date}
                                                onChange={(e) => setProspectiveForm({ ...prospectiveForm, date: e.target.value })}
                                            />
                                        </div>
                                        <div>
                                            <Label htmlFor="pc-notes">Notes</Label>
                                            <Input
                                                id="pc-notes"
                                                value={prospectiveForm.notes}
                                                onChange={(e) => setProspectiveForm({ ...prospectiveForm, notes: e.target.value })}
                                                placeholder="Additional notes"
                                            />
                                        </div>
                                    </div>
                                    <div className="flex justify-end">
                                        <Button
                                            size="sm"
                                            onClick={() => {
                                                if (!prospectiveForm.name || !prospectiveForm.subject) {
                                                    toast.error("Name and subject are required");
                                                    return;
                                                }
                                                createProspective.mutate(prospectiveForm);
                                            }}
                                            disabled={createProspective.isPending}
                                        >
                                            {createProspective.isPending ? "Saving..." : "Save"}
                                        </Button>
                                    </div>
                                </div>
                            )}

                            {/* Table */}
                            {prospectiveQuery.isLoading ? (
                                <div className="space-y-3">
                                    {Array.from({ length: 3 }).map((_, i) => (
                                        <Skeleton key={i} className="h-12 w-full rounded-lg" />
                                    ))}
                                </div>
                            ) : prospectiveClients.length === 0 ? (
                                <p className="text-sm text-muted-foreground text-center py-8">
                                    No prospective clients recorded.
                                </p>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="border-b border-border text-left">
                                                <th className="pb-2 font-medium text-muted-foreground">Name</th>
                                                <th className="pb-2 font-medium text-muted-foreground">Subject</th>
                                                <th className="pb-2 font-medium text-muted-foreground">Date</th>
                                                <th className="pb-2 font-medium text-muted-foreground">Disclosed Info</th>
                                                <th className="pb-2 font-medium text-muted-foreground">Notes</th>
                                                <th className="pb-2 font-medium text-muted-foreground w-16"></th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {prospectiveClients.map((pc) => (
                                                <tr key={pc.id} className="border-b border-border last:border-0">
                                                    <td className="py-2 font-medium">{pc.name}</td>
                                                    <td className="py-2">{pc.subject}</td>
                                                    <td className="py-2 text-muted-foreground">{pc.date}</td>
                                                    <td className="py-2 text-muted-foreground max-w-[200px] truncate">
                                                        {pc.disclosed_info || "-"}
                                                    </td>
                                                    <td className="py-2 text-muted-foreground max-w-[150px] truncate">
                                                        {pc.notes || "-"}
                                                    </td>
                                                    <td className="py-2">
                                                        {deleteProspectiveId === pc.id ? (
                                                            <div className="flex gap-1">
                                                                <Button
                                                                    variant="destructive"
                                                                    size="sm"
                                                                    className="h-6 text-xs px-2"
                                                                    onClick={() => deleteProspective.mutate(pc.id)}
                                                                    disabled={deleteProspective.isPending}
                                                                >
                                                                    Confirm
                                                                </Button>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="sm"
                                                                    className="h-6 text-xs px-2"
                                                                    onClick={() => setDeleteProspectiveId(null)}
                                                                >
                                                                    Cancel
                                                                </Button>
                                                            </div>
                                                        ) : (
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="h-7 w-7 text-destructive hover:text-destructive"
                                                                onClick={() => setDeleteProspectiveId(pc.id)}
                                                            >
                                                                &times;
                                                            </Button>
                                                        )}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ============================================================
                    TAB 4: TRUST ACCOUNTS
                   ============================================================ */}
                <TabsContent value="trust" className="space-y-4 mt-4">
                    {/* Balance Card */}
                    <Card className="glass-card">
                        <CardContent className="pt-4 pb-3 flex items-center justify-between">
                            <div>
                                <p className="text-xs font-medium text-muted-foreground uppercase">Trust Balance</p>
                                <p className={`text-3xl font-bold mt-1 ${trustBalance < 0 ? "text-red-400" : "text-emerald-400"}`}>
                                    ${trustBalance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </p>
                            </div>
                            <Badge variant="secondary">{trustEntries.length} entries</Badge>
                        </CardContent>
                    </Card>

                    {/* Add Entry Form */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center justify-between">
                                Trust Account Ledger
                                <Button
                                    size="sm"
                                    onClick={() => setShowTrustForm(!showTrustForm)}
                                >
                                    {showTrustForm ? "Cancel" : "+ Add Entry"}
                                </Button>
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {showTrustForm && (
                                <div className="border border-border rounded-lg p-4 mb-4 space-y-3 bg-muted/30">
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                        <div>
                                            <Label htmlFor="trust-type">Type</Label>
                                            <select
                                                id="trust-type"
                                                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                value={trustForm.type}
                                                onChange={(e) => setTrustForm({ ...trustForm, type: e.target.value })}
                                            >
                                                <option value="deposit">Deposit</option>
                                                <option value="withdrawal">Withdrawal</option>
                                            </select>
                                        </div>
                                        <div>
                                            <Label htmlFor="trust-amount">Amount ($)</Label>
                                            <Input
                                                id="trust-amount"
                                                type="number"
                                                step="0.01"
                                                min="0"
                                                value={trustForm.amount}
                                                onChange={(e) => setTrustForm({ ...trustForm, amount: e.target.value })}
                                                placeholder="0.00"
                                            />
                                        </div>
                                        <div>
                                            <Label htmlFor="trust-date">Date</Label>
                                            <Input
                                                id="trust-date"
                                                type="date"
                                                value={trustForm.date}
                                                onChange={(e) => setTrustForm({ ...trustForm, date: e.target.value })}
                                            />
                                        </div>
                                    </div>
                                    <div>
                                        <Label htmlFor="trust-desc">Description</Label>
                                        <Input
                                            id="trust-desc"
                                            value={trustForm.description}
                                            onChange={(e) => setTrustForm({ ...trustForm, description: e.target.value })}
                                            placeholder="Description of transaction"
                                        />
                                    </div>
                                    <div className="flex justify-end">
                                        <Button
                                            size="sm"
                                            onClick={() => {
                                                if (!trustForm.amount || parseFloat(trustForm.amount) <= 0) {
                                                    toast.error("Amount must be greater than zero");
                                                    return;
                                                }
                                                if (!trustForm.description) {
                                                    toast.error("Description is required");
                                                    return;
                                                }
                                                createTrustEntry.mutate(trustForm);
                                            }}
                                            disabled={createTrustEntry.isPending}
                                        >
                                            {createTrustEntry.isPending ? "Adding..." : "Add Entry"}
                                        </Button>
                                    </div>
                                </div>
                            )}

                            {/* Entries List */}
                            {trustQuery.isLoading ? (
                                <div className="space-y-3">
                                    {Array.from({ length: 3 }).map((_, i) => (
                                        <Skeleton key={i} className="h-12 w-full rounded-lg" />
                                    ))}
                                </div>
                            ) : trustEntries.length === 0 ? (
                                <p className="text-sm text-muted-foreground text-center py-6">
                                    No trust account entries.
                                </p>
                            ) : (
                                <div className="space-y-2">
                                    {trustEntries.map((entry, i) => (
                                        <div
                                            key={entry.id || i}
                                            className="flex items-center justify-between py-2 border-b border-border last:border-0"
                                        >
                                            <div>
                                                <p className="text-sm">{entry.description}</p>
                                                <p className="text-xs text-muted-foreground">{entry.date}</p>
                                            </div>
                                            <span
                                                className={`text-sm font-bold ${
                                                    entry.type === "deposit" ? "text-emerald-400" : "text-red-400"
                                                }`}
                                            >
                                                {entry.type === "deposit" ? "+" : "\u2212"}$
                                                {Math.abs(entry.amount).toFixed(2)}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ============================================================
                    TAB 5: FEE AGREEMENTS
                   ============================================================ */}
                <TabsContent value="fees" className="space-y-4 mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center justify-between">
                                Fee Agreement
                                {feeAgreement && (
                                    <Badge
                                        variant={feeAgreement.agreement ? "default" : "destructive"}
                                    >
                                        {feeAgreement.agreement ? "On File" : "Missing"}
                                    </Badge>
                                )}
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {feeQuery.isLoading ? (
                                <div className="space-y-3">
                                    <Skeleton className="h-10 w-full" />
                                    <Skeleton className="h-10 w-full" />
                                    <Skeleton className="h-20 w-full" />
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div>
                                            <Label htmlFor="fee-type">Fee Type</Label>
                                            <select
                                                id="fee-type"
                                                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                value={feeForm.fee_type}
                                                onChange={(e) => setFeeForm({ ...feeForm, fee_type: e.target.value })}
                                            >
                                                <option value="flat">Flat Fee</option>
                                                <option value="hourly">Hourly</option>
                                                <option value="contingency">Contingency</option>
                                                <option value="hybrid">Hybrid</option>
                                            </select>
                                        </div>
                                        <div>
                                            <Label htmlFor="fee-rate">Rate</Label>
                                            <Input
                                                id="fee-rate"
                                                value={feeForm.rate}
                                                onChange={(e) => setFeeForm({ ...feeForm, rate: e.target.value })}
                                                placeholder={feeForm.fee_type === "hourly" ? "$/hr" : feeForm.fee_type === "contingency" ? "33%" : "Amount"}
                                            />
                                        </div>
                                    </div>
                                    <div>
                                        <Label htmlFor="fee-retainer">Retainer</Label>
                                        <Input
                                            id="fee-retainer"
                                            value={feeForm.retainer}
                                            onChange={(e) => setFeeForm({ ...feeForm, retainer: e.target.value })}
                                            placeholder="Retainer amount"
                                        />
                                    </div>
                                    <div>
                                        <Label htmlFor="fee-scope">Scope of Representation</Label>
                                        <Textarea
                                            id="fee-scope"
                                            value={feeForm.scope}
                                            onChange={(e) => setFeeForm({ ...feeForm, scope: e.target.value })}
                                            placeholder="Describe the scope of representation covered by this agreement"
                                            rows={4}
                                        />
                                    </div>
                                    <div className="flex items-center gap-4">
                                        <div className="flex items-center gap-2">
                                            <input
                                                id="fee-signed"
                                                type="checkbox"
                                                className="h-4 w-4 rounded border-gray-300"
                                                checked={feeForm.signed}
                                                onChange={(e) => setFeeForm({ ...feeForm, signed: e.target.checked })}
                                            />
                                            <Label htmlFor="fee-signed" className="mb-0">Signed</Label>
                                        </div>
                                        {feeForm.signed && (
                                            <div className="flex items-center gap-2">
                                                <Label htmlFor="fee-signed-date" className="mb-0 whitespace-nowrap">
                                                    Signed Date
                                                </Label>
                                                <Input
                                                    id="fee-signed-date"
                                                    type="date"
                                                    className="w-44"
                                                    value={feeForm.signed_date}
                                                    onChange={(e) => setFeeForm({ ...feeForm, signed_date: e.target.value })}
                                                />
                                            </div>
                                        )}
                                    </div>
                                    <div className="flex justify-end">
                                        <Button
                                            size="sm"
                                            onClick={() => saveFeeAgreement.mutate(feeForm)}
                                            disabled={saveFeeAgreement.isPending}
                                        >
                                            {saveFeeAgreement.isPending ? "Saving..." : "Save Agreement"}
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ============================================================
                    TAB 6: SOL TRACKER
                   ============================================================ */}
                <TabsContent value="sol" className="space-y-4 mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center justify-between">
                                Statute of Limitations Tracking
                                <div className="flex items-center gap-2">
                                    <Badge variant="secondary">
                                        {solClaims.length} claims
                                    </Badge>
                                    <Button
                                        size="sm"
                                        onClick={() => setShowSolForm(!showSolForm)}
                                    >
                                        {showSolForm ? "Cancel" : "+ Add Claim"}
                                    </Button>
                                </div>
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {/* Add Claim Form */}
                            {showSolForm && (
                                <div className="border border-border rounded-lg p-4 mb-4 space-y-3 bg-muted/30">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                        <div>
                                            <Label htmlFor="sol-type">Claim Type *</Label>
                                            <Input
                                                id="sol-type"
                                                value={solForm.claim_type}
                                                onChange={(e) => setSolForm({ ...solForm, claim_type: e.target.value })}
                                                placeholder="e.g., Personal Injury, Breach of Contract"
                                            />
                                        </div>
                                        <div>
                                            <Label htmlFor="sol-deadline">Deadline *</Label>
                                            <Input
                                                id="sol-deadline"
                                                type="date"
                                                value={solForm.deadline}
                                                onChange={(e) => setSolForm({ ...solForm, deadline: e.target.value })}
                                            />
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                        <div>
                                            <Label htmlFor="sol-incident">Incident Date *</Label>
                                            <Input
                                                id="sol-incident"
                                                type="date"
                                                value={solForm.incident_date}
                                                onChange={(e) => setSolForm({ ...solForm, incident_date: e.target.value })}
                                            />
                                        </div>
                                        <div>
                                            <Label htmlFor="sol-discovery">Discovery Date</Label>
                                            <Input
                                                id="sol-discovery"
                                                type="date"
                                                value={solForm.discovery_date}
                                                onChange={(e) => setSolForm({ ...solForm, discovery_date: e.target.value })}
                                            />
                                        </div>
                                    </div>
                                    <div>
                                        <Label htmlFor="sol-desc">Description</Label>
                                        <Textarea
                                            id="sol-desc"
                                            value={solForm.description}
                                            onChange={(e) => setSolForm({ ...solForm, description: e.target.value })}
                                            placeholder="Description of the claim"
                                            rows={2}
                                        />
                                    </div>
                                    <div>
                                        <Label htmlFor="sol-tolling">Tolling Notes</Label>
                                        <Textarea
                                            id="sol-tolling"
                                            value={solForm.tolling_notes}
                                            onChange={(e) => setSolForm({ ...solForm, tolling_notes: e.target.value })}
                                            placeholder="Any tolling agreements, minority status, etc."
                                            rows={2}
                                        />
                                    </div>
                                    <div className="flex justify-end">
                                        <Button
                                            size="sm"
                                            onClick={() => {
                                                if (!solForm.claim_type || !solForm.incident_date || !solForm.deadline) {
                                                    toast.error("Claim type, incident date, and deadline are required");
                                                    return;
                                                }
                                                createSolClaim.mutate(solForm);
                                            }}
                                            disabled={createSolClaim.isPending}
                                        >
                                            {createSolClaim.isPending ? "Adding..." : "Add Claim"}
                                        </Button>
                                    </div>
                                </div>
                            )}

                            {/* Claims List */}
                            {solQuery.isLoading ? (
                                <div className="space-y-3">
                                    {Array.from({ length: 2 }).map((_, i) => (
                                        <Skeleton key={i} className="h-16 w-full rounded-lg" />
                                    ))}
                                </div>
                            ) : solClaims.length === 0 ? (
                                <p className="text-sm text-muted-foreground text-center py-6">
                                    No SOL claims tracked for this case.
                                </p>
                            ) : (
                                <div className="space-y-2">
                                    {solClaims.map((claim) => (
                                        <div
                                            key={claim.id}
                                            className="flex items-center justify-between py-3 border-b border-border last:border-0 group"
                                        >
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-0.5">
                                                    <span className="text-sm font-medium">
                                                        {claim.claim_type}
                                                    </span>
                                                    <SOLBadge claim={claim} />
                                                </div>
                                                {claim.description && (
                                                    <p className="text-xs text-muted-foreground">
                                                        {claim.description}
                                                    </p>
                                                )}
                                                <p className="text-xs text-muted-foreground mt-0.5">
                                                    Incident: {claim.incident_date}
                                                    {claim.deadline && claim.deadline !== "See administrative filing deadlines"
                                                        ? ` \u00b7 Deadline: ${claim.deadline}`
                                                        : ""}
                                                </p>
                                                {claim.tolling_notes && (
                                                    <p className="text-[10px] text-muted-foreground italic mt-0.5">
                                                        Tolling: {claim.tolling_notes}
                                                    </p>
                                                )}
                                            </div>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-7 w-7 text-destructive opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                                                onClick={() => deleteSolClaim.mutate(claim.id)}
                                            >
                                                &times;
                                            </Button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ============================================================
                    TAB 7: SUPERVISION
                   ============================================================ */}
                <TabsContent value="supervision" className="space-y-4 mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center justify-between">
                                Supervision Log
                                <Button
                                    size="sm"
                                    onClick={() => setShowSupervisionForm(!showSupervisionForm)}
                                >
                                    {showSupervisionForm ? "Cancel" : "+ Add Entry"}
                                </Button>
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {/* Add Entry Form */}
                            {showSupervisionForm && (
                                <div className="border border-border rounded-lg p-4 mb-4 space-y-3 bg-muted/30">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                        <div>
                                            <Label htmlFor="sup-task">Task *</Label>
                                            <Input
                                                id="sup-task"
                                                value={supervisionForm.task}
                                                onChange={(e) => setSupervisionForm({ ...supervisionForm, task: e.target.value })}
                                                placeholder="Task description"
                                            />
                                        </div>
                                        <div>
                                            <Label htmlFor="sup-status">Status</Label>
                                            <select
                                                id="sup-status"
                                                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                                value={supervisionForm.status}
                                                onChange={(e) => setSupervisionForm({ ...supervisionForm, status: e.target.value })}
                                            >
                                                <option value="assigned">Assigned</option>
                                                <option value="in_progress">In Progress</option>
                                                <option value="review">Under Review</option>
                                                <option value="complete">Complete</option>
                                            </select>
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                        <div>
                                            <Label htmlFor="sup-assignee">Assignee *</Label>
                                            <Input
                                                id="sup-assignee"
                                                value={supervisionForm.assignee}
                                                onChange={(e) => setSupervisionForm({ ...supervisionForm, assignee: e.target.value })}
                                                placeholder="Person assigned"
                                            />
                                        </div>
                                        <div>
                                            <Label htmlFor="sup-supervisor">Supervisor *</Label>
                                            <Input
                                                id="sup-supervisor"
                                                value={supervisionForm.supervisor}
                                                onChange={(e) => setSupervisionForm({ ...supervisionForm, supervisor: e.target.value })}
                                                placeholder="Supervising attorney"
                                            />
                                        </div>
                                    </div>
                                    <div>
                                        <Label htmlFor="sup-notes">Notes</Label>
                                        <Textarea
                                            id="sup-notes"
                                            value={supervisionForm.notes}
                                            onChange={(e) => setSupervisionForm({ ...supervisionForm, notes: e.target.value })}
                                            placeholder="Additional notes"
                                            rows={2}
                                        />
                                    </div>
                                    <div className="flex justify-end">
                                        <Button
                                            size="sm"
                                            onClick={() => {
                                                if (!supervisionForm.task || !supervisionForm.assignee || !supervisionForm.supervisor) {
                                                    toast.error("Task, assignee, and supervisor are required");
                                                    return;
                                                }
                                                createSupervision.mutate(supervisionForm);
                                            }}
                                            disabled={createSupervision.isPending}
                                        >
                                            {createSupervision.isPending ? "Saving..." : "Save"}
                                        </Button>
                                    </div>
                                </div>
                            )}

                            {/* Table */}
                            {supervisionQuery.isLoading ? (
                                <div className="space-y-3">
                                    {Array.from({ length: 3 }).map((_, i) => (
                                        <Skeleton key={i} className="h-12 w-full rounded-lg" />
                                    ))}
                                </div>
                            ) : supervisionEntries.length === 0 ? (
                                <p className="text-sm text-muted-foreground text-center py-8">
                                    No supervision entries recorded.
                                </p>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="border-b border-border text-left">
                                                <th className="pb-2 font-medium text-muted-foreground">Task</th>
                                                <th className="pb-2 font-medium text-muted-foreground">Assignee</th>
                                                <th className="pb-2 font-medium text-muted-foreground">Supervisor</th>
                                                <th className="pb-2 font-medium text-muted-foreground">Status</th>
                                                <th className="pb-2 font-medium text-muted-foreground">Date</th>
                                                <th className="pb-2 font-medium text-muted-foreground">Notes</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {supervisionEntries.map((entry) => (
                                                <tr key={entry.id} className="border-b border-border last:border-0">
                                                    <td className="py-2 font-medium">{entry.task}</td>
                                                    <td className="py-2">{entry.assignee}</td>
                                                    <td className="py-2">{entry.supervisor}</td>
                                                    <td className="py-2">
                                                        <StatusBadge status={entry.status} domain="generic" />
                                                    </td>
                                                    <td className="py-2 text-muted-foreground">{entry.date}</td>
                                                    <td className="py-2 text-muted-foreground max-w-[200px] truncate">
                                                        {entry.notes || "-"}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ConflictMatchCard({ match }: { match: SmartConflictMatch }) {
    return (
        <Card className="border-l-4 border-l-amber-500/60">
            <CardContent className="py-3 space-y-2">
                <div className="flex items-start justify-between gap-2">
                    <div>
                        <p className="text-sm font-semibold">{match.name}</p>
                        <p className="text-xs text-muted-foreground">
                            Matched: <span className="font-medium">{match.matched_name}</span>
                            {match.source && ` (${match.source})`}
                        </p>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                        <span
                            className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${matchTypeBadgeVariant(match.match_type)}`}
                        >
                            {match.match_type}
                        </span>
                        <StatusBadge status={match.severity} domain="severity" />
                    </div>
                </div>

                {/* Confidence Bar */}
                <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground w-20 shrink-0">Confidence</span>
                    <Progress value={match.confidence * 100} className="h-2 flex-1" />
                    <span className="text-xs font-medium w-10 text-right">
                        {Math.round(match.confidence * 100)}%
                    </span>
                </div>

                {/* Explanation */}
                <p className="text-xs text-muted-foreground">{match.explanation}</p>

                {/* Source case info */}
                {match.other_case && (
                    <div className="flex items-center gap-2 text-xs">
                        <span className="text-muted-foreground">Source case:</span>
                        <span className="font-medium">{match.other_case}</span>
                        {match.current_role && (
                            <span className="text-muted-foreground">
                                (current: {match.current_role})
                            </span>
                        )}
                        {match.other_role && (
                            <span className="text-muted-foreground">
                                (other: {match.other_role})
                            </span>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

