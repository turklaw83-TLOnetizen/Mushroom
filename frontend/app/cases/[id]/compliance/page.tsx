// ---- Enhanced Compliance Tab ---------------------------------------------
// Conflict Check, Communication Gaps, Litigation Hold, Ethics Checklist
"use client";

import { useState, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// ---- Interfaces ---------------------------------------------------------

interface TrustEntry {
    id: string;
    date: string;
    amount: number;
    type: string;
    description: string;
}

interface ConflictMatch {
    source: string;
    name: string;
    id: string;
    case_id?: string;
    cases?: string[];
    match_type: string;
    alias?: string;
}

interface ConflictResult {
    has_conflict: boolean;
    matches: ConflictMatch[];
    severity: string;
}

interface JournalEntry {
    id: string;
    text: string;
    category: string;
    timestamp: string;
}

interface CaseMetadata {
    id: string;
    name: string;
    litigation_hold?: boolean;
    ethics_checklist?: Record<string, boolean>;
    [key: string]: unknown;
}

// ---- Ethics checklist items ---------------------------------------------

const ETHICS_ITEMS = [
    { key: "client_consent", label: "Client consent obtained" },
    { key: "conflict_check", label: "Conflict check completed" },
    { key: "engagement_letter", label: "Engagement letter signed" },
    { key: "trust_compliance", label: "Trust account compliance" },
    { key: "communication_log", label: "Communication log current" },
] as const;

// ---- Component ----------------------------------------------------------

export default function CompliancePage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { canEdit } = useRole();

    // ---- State for conflict checker ------------------------------------
    const [partyName, setPartyName] = useState("");
    const [conflictResults, setConflictResults] = useState<ConflictResult | null>(null);
    const [conflictLoading, setConflictLoading] = useState(false);

    // ---- Queries -------------------------------------------------------

    const conflictsQuery = useQuery({
        queryKey: ["compliance", "conflicts", caseId],
        queryFn: () => api.get<Record<string, unknown>>(`/compliance/conflicts/${caseId}`, { getToken }),
    });

    const trustQuery = useQuery({
        queryKey: ["compliance", "trust", caseId],
        queryFn: () => api.get<TrustEntry[]>(`/compliance/trust/${caseId}`, { getToken }),
    });

    const caseQuery = useQuery({
        queryKey: ["case", caseId],
        queryFn: () => api.get<CaseMetadata>(`/cases/${caseId}`, { getToken }),
    });

    const journalQuery = useQuery({
        queryKey: ["journal", caseId],
        queryFn: () => api.get<JournalEntry[]>(`/cases/${caseId}/journal`, { getToken }),
    });

    const trust = trustQuery.data ?? [];
    const trustBalance = trust.reduce((sum, e) => {
        return sum + (e.type === "deposit" ? e.amount : -e.amount);
    }, 0);
    const caseMeta = caseQuery.data;

    // ---- Derived: ethics checklist state --------------------------------
    const ethicsState = useMemo(() => {
        const stored = caseMeta?.ethics_checklist || {};
        return ETHICS_ITEMS.map((item) => ({
            ...item,
            checked: !!stored[item.key],
        }));
    }, [caseMeta?.ethics_checklist]);

    const ethicsComplete = ethicsState.filter((i) => i.checked).length;
    const ethicsTotal = ETHICS_ITEMS.length;

    // ---- Derived: communication gap analysis ----------------------------
    const commGapAnalysis = useMemo(() => {
        const entries = journalQuery.data ?? [];
        if (entries.length === 0) {
            return { lastComm: null, daysSince: null, hasGap: true, entries: [] };
        }
        // Sort by timestamp descending
        const sorted = [...entries].sort((a, b) =>
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        );
        const lastDate = new Date(sorted[0].timestamp);
        const now = new Date();
        const daysSince = Math.floor((now.getTime() - lastDate.getTime()) / (1000 * 60 * 60 * 24));
        return {
            lastComm: sorted[0],
            daysSince,
            hasGap: daysSince >= 30,
            entries: sorted.slice(0, 10), // last 10 entries
        };
    }, [journalQuery.data]);

    // ---- Handlers: conflict check --------------------------------------
    const handleConflictCheck = useCallback(async () => {
        if (!partyName.trim()) {
            toast.error("Enter a party name to check");
            return;
        }
        setConflictLoading(true);
        try {
            const result = await api.post<ConflictResult>(
                "/conflicts/check",
                {
                    party_name: partyName.trim(),
                    party_type: "client",
                },
                { getToken },
            );
            setConflictResults(result);
            if (result.has_conflict) {
                toast.warning(`${result.matches.length} potential conflict(s) found`);
            } else {
                toast.success("No conflicts found");
            }
        } catch (err) {
            toast.error("Conflict check failed");
        } finally {
            setConflictLoading(false);
        }
    }, [partyName, getToken]);

    // ---- Handlers: litigation hold toggle -------------------------------
    const toggleLitHold = useMutationWithToast<void>({
        mutationFn: async () => {
            const newValue = !caseMeta?.litigation_hold;
            await api.patch(`/cases/${caseId}`, { litigation_hold: newValue }, { getToken });
        },
        successMessage: caseMeta?.litigation_hold ? "Litigation hold removed" : "Litigation hold activated",
        invalidateKeys: [["case", caseId]],
    });

    // ---- Handlers: ethics checklist toggle ------------------------------
    const toggleEthicsItem = useCallback(async (key: string) => {
        const currentChecklist = caseMeta?.ethics_checklist || {};
        const updated = { ...currentChecklist, [key]: !currentChecklist[key] };
        try {
            await api.patch(`/cases/${caseId}`, { ethics_checklist: updated }, { getToken });
            // Invalidate to refresh
            toast.success("Checklist updated");
        } catch {
            toast.error("Failed to update checklist");
        }
    }, [caseId, caseMeta?.ethics_checklist, getToken]);

    // ---- Render ---------------------------------------------------------
    return (
        <div className="space-y-6">
            {/* Litigation Hold Banner */}
            {caseMeta?.litigation_hold && (
                <div className="rounded-lg border border-amber-500/50 bg-amber-500/10 px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <span className="text-amber-400 text-lg">&#9888;</span>
                        <div>
                            <p className="text-sm font-semibold text-amber-300">Litigation Hold Active</p>
                            <p className="text-xs text-amber-400/80">Files cannot be deleted or purged while litigation hold is active.</p>
                        </div>
                    </div>
                    {canEdit && (
                        <Button
                            size="sm"
                            variant="outline"
                            className="border-amber-500/40 text-amber-300 hover:bg-amber-500/20"
                            onClick={() => toggleLitHold.mutate()}
                            disabled={toggleLitHold.isPending}
                        >
                            {toggleLitHold.isPending ? "Updating..." : "Release Hold"}
                        </Button>
                    )}
                </div>
            )}

            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Conflicts</p>
                        <p className="text-2xl font-bold mt-1">
                            {conflictsQuery.isLoading ? (
                                <Skeleton className="h-8 w-8 inline-block" />
                            ) : (
                                <Badge variant="outline" className="text-emerald-400 border-emerald-500/30 text-lg">
                                    Clear
                                </Badge>
                            )}
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Trust Balance</p>
                        <p className={`text-2xl font-bold mt-1 ${trustBalance < 0 ? "text-red-400" : ""}`}>
                            ${trustBalance.toLocaleString()}
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Litigation Hold</p>
                        <p className="text-2xl font-bold mt-1">
                            <Badge
                                variant="outline"
                                className={caseMeta?.litigation_hold
                                    ? "text-amber-400 border-amber-500/30 text-lg"
                                    : "text-muted-foreground border-border text-lg"
                                }
                            >
                                {caseMeta?.litigation_hold ? "Active" : "Off"}
                            </Badge>
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="pt-4 pb-3">
                        <p className="text-xs font-medium text-muted-foreground uppercase">Ethics Checklist</p>
                        <p className="text-2xl font-bold mt-1">
                            <Badge
                                variant="outline"
                                className={ethicsComplete === ethicsTotal
                                    ? "text-emerald-400 border-emerald-500/30 text-lg"
                                    : "text-amber-400 border-amber-500/30 text-lg"
                                }
                            >
                                {ethicsComplete}/{ethicsTotal}
                            </Badge>
                        </p>
                    </CardContent>
                </Card>
            </div>

            {/* Tabbed Content */}
            <Tabs defaultValue="conflicts">
                <TabsList>
                    <TabsTrigger value="conflicts">Conflict Check</TabsTrigger>
                    <TabsTrigger value="communications">
                        Communication Gaps
                        {commGapAnalysis.hasGap && (
                            <span className="ml-1.5 inline-flex h-2 w-2 rounded-full bg-red-500" />
                        )}
                    </TabsTrigger>
                    <TabsTrigger value="hold">Litigation Hold</TabsTrigger>
                    <TabsTrigger value="ethics">Ethics Checklist</TabsTrigger>
                    <TabsTrigger value="trust">Trust Ledger</TabsTrigger>
                </TabsList>

                {/* ---- Conflict Check Tab ---- */}
                <TabsContent value="conflicts" className="space-y-4 mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Conflict of Interest Check</CardTitle>
                            <CardDescription>
                                Search all cases, clients, opposing parties, and witnesses for name conflicts
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex gap-2">
                                <Input
                                    placeholder="Enter party name to check..."
                                    value={partyName}
                                    onChange={(e) => setPartyName(e.target.value)}
                                    onKeyDown={(e) => e.key === "Enter" && handleConflictCheck()}
                                    className="flex-1"
                                />
                                <Button
                                    onClick={handleConflictCheck}
                                    disabled={conflictLoading || !partyName.trim()}
                                    size="sm"
                                >
                                    {conflictLoading ? "Checking..." : "Run Check"}
                                </Button>
                            </div>

                            {conflictResults && (
                                <div className="space-y-3">
                                    {/* Status banner */}
                                    <div className={`rounded-lg px-4 py-3 border ${
                                        conflictResults.has_conflict
                                            ? "border-red-500/50 bg-red-500/10"
                                            : "border-emerald-500/50 bg-emerald-500/10"
                                    }`}>
                                        <p className={`text-sm font-semibold ${
                                            conflictResults.has_conflict ? "text-red-400" : "text-emerald-400"
                                        }`}>
                                            {conflictResults.has_conflict
                                                ? `${conflictResults.matches.length} conflict(s) found — Severity: ${conflictResults.severity}`
                                                : "No conflicts found"
                                            }
                                        </p>
                                    </div>

                                    {/* Results table */}
                                    {conflictResults.matches.length > 0 && (
                                        <div className="rounded-lg border">
                                            <div className="grid grid-cols-4 gap-2 px-4 py-2 border-b bg-muted/30 text-xs font-medium text-muted-foreground uppercase">
                                                <span>Entity Name</span>
                                                <span>Conflict Type</span>
                                                <span>Source</span>
                                                <span>Match</span>
                                            </div>
                                            {conflictResults.matches.map((m, i) => (
                                                <div key={i} className="grid grid-cols-4 gap-2 px-4 py-2 border-b last:border-0 text-sm">
                                                    <span className="font-medium">{m.name || "Unknown"}</span>
                                                    <span>
                                                        <Badge variant={m.source === "crm_client" ? "destructive" : "secondary"} className="text-xs">
                                                            {m.source.replace("_", " ")}
                                                        </Badge>
                                                    </span>
                                                    <span className="text-muted-foreground text-xs">
                                                        {m.case_id || (m.cases && m.cases.length > 0 ? m.cases.join(", ") : "N/A")}
                                                    </span>
                                                    <span className="text-xs text-muted-foreground">
                                                        {m.match_type}{m.alias ? ` (alias: ${m.alias})` : ""}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ---- Communication Gaps Tab ---- */}
                <TabsContent value="communications" className="space-y-4 mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center justify-between">
                                Client Communication Timeline
                                {commGapAnalysis.hasGap && (
                                    <Badge variant="destructive" className="text-xs">Gap Detected</Badge>
                                )}
                            </CardTitle>
                            <CardDescription>
                                Tracks journal entries as a proxy for client communications. Flags gaps of 30+ days.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {/* Gap warning */}
                            {commGapAnalysis.hasGap && (
                                <div className="rounded-lg border border-red-500/50 bg-red-500/10 px-4 py-3 mb-4">
                                    <p className="text-sm font-semibold text-red-400">
                                        {commGapAnalysis.daysSince !== null
                                            ? `Warning: No communication logged in ${commGapAnalysis.daysSince} days`
                                            : "Warning: No communications logged for this case"
                                        }
                                    </p>
                                    <p className="text-xs text-red-400/70 mt-1">
                                        Bar rules typically require regular client communication. Consider reaching out to the client.
                                    </p>
                                </div>
                            )}

                            {/* Status summary */}
                            {commGapAnalysis.lastComm && (
                                <div className="mb-4 flex items-center gap-4">
                                    <div className="rounded-lg border px-3 py-2">
                                        <p className="text-xs text-muted-foreground">Last Communication</p>
                                        <p className="text-sm font-medium">
                                            {new Date(commGapAnalysis.lastComm.timestamp).toLocaleDateString("en-US", {
                                                month: "short", day: "numeric", year: "numeric",
                                            })}
                                        </p>
                                    </div>
                                    <div className="rounded-lg border px-3 py-2">
                                        <p className="text-xs text-muted-foreground">Days Since</p>
                                        <p className={`text-sm font-bold ${
                                            (commGapAnalysis.daysSince ?? 0) >= 30 ? "text-red-400" :
                                            (commGapAnalysis.daysSince ?? 0) >= 14 ? "text-amber-400" : "text-emerald-400"
                                        }`}>
                                            {commGapAnalysis.daysSince}
                                        </p>
                                    </div>
                                    <div className="rounded-lg border px-3 py-2">
                                        <p className="text-xs text-muted-foreground">Total Entries</p>
                                        <p className="text-sm font-medium">{journalQuery.data?.length ?? 0}</p>
                                    </div>
                                </div>
                            )}

                            {/* Recent entries timeline */}
                            {journalQuery.isLoading ? (
                                <div className="space-y-2">
                                    {Array.from({ length: 5 }).map((_, i) => (
                                        <Skeleton key={i} className="h-12 w-full" />
                                    ))}
                                </div>
                            ) : commGapAnalysis.entries.length === 0 ? (
                                <p className="text-sm text-muted-foreground text-center py-6">
                                    No journal entries found. Add journal entries to track communications.
                                </p>
                            ) : (
                                <div className="space-y-0 relative">
                                    {/* Vertical timeline line */}
                                    <div className="absolute left-3 top-2 bottom-2 w-px bg-border" />
                                    {commGapAnalysis.entries.map((entry, i) => (
                                        <div key={entry.id || i} className="flex gap-4 py-2 relative">
                                            <div className="w-6 flex items-start justify-center pt-1.5 z-10">
                                                <div className="h-2.5 w-2.5 rounded-full bg-primary border-2 border-background" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-0.5">
                                                    <span className="text-xs text-muted-foreground">
                                                        {new Date(entry.timestamp).toLocaleDateString("en-US", {
                                                            month: "short", day: "numeric", year: "numeric",
                                                        })}
                                                    </span>
                                                    <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                                                        {entry.category}
                                                    </Badge>
                                                </div>
                                                <p className="text-sm text-foreground truncate">{entry.text}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ---- Litigation Hold Tab ---- */}
                <TabsContent value="hold" className="space-y-4 mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">Litigation Hold Management</CardTitle>
                            <CardDescription>
                                When active, prevents deletion or purging of case files and evidence. Required for preservation obligations.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex items-center justify-between rounded-lg border px-4 py-4">
                                <div>
                                    <p className="text-sm font-medium">
                                        Litigation Hold Status
                                    </p>
                                    <p className="text-xs text-muted-foreground mt-0.5">
                                        {caseMeta?.litigation_hold
                                            ? "All case files are preserved. Deletion and purge operations are blocked."
                                            : "No active hold. Files can be managed normally."
                                        }
                                    </p>
                                </div>
                                <div className="flex items-center gap-3">
                                    <Badge
                                        variant={caseMeta?.litigation_hold ? "default" : "secondary"}
                                        className={caseMeta?.litigation_hold
                                            ? "bg-amber-500/20 text-amber-400 border-amber-500/30"
                                            : ""
                                        }
                                    >
                                        {caseMeta?.litigation_hold ? "ACTIVE" : "INACTIVE"}
                                    </Badge>
                                    {canEdit && (
                                        <Button
                                            size="sm"
                                            variant={caseMeta?.litigation_hold ? "outline" : "default"}
                                            onClick={() => toggleLitHold.mutate()}
                                            disabled={toggleLitHold.isPending}
                                        >
                                            {toggleLitHold.isPending
                                                ? "Updating..."
                                                : caseMeta?.litigation_hold
                                                    ? "Release Hold"
                                                    : "Activate Hold"
                                            }
                                        </Button>
                                    )}
                                </div>
                            </div>

                            {caseMeta?.litigation_hold && (
                                <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3">
                                    <p className="text-sm font-medium text-amber-400 mb-2">While Litigation Hold is Active:</p>
                                    <ul className="text-xs text-amber-400/80 space-y-1 list-disc list-inside">
                                        <li>No case files may be deleted or purged</li>
                                        <li>Archival phase transitions are blocked</li>
                                        <li>All document modifications are logged</li>
                                        <li>Evidence preservation notices should be sent to relevant parties</li>
                                    </ul>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ---- Ethics Checklist Tab ---- */}
                <TabsContent value="ethics" className="space-y-4 mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center justify-between">
                                Ethics Compliance Checklist
                                <Badge
                                    variant="outline"
                                    className={ethicsComplete === ethicsTotal
                                        ? "text-emerald-400 border-emerald-500/30"
                                        : "text-amber-400 border-amber-500/30"
                                    }
                                >
                                    {ethicsComplete}/{ethicsTotal} Complete
                                </Badge>
                            </CardTitle>
                            <CardDescription>
                                Track mandatory compliance items for this case. Changes are saved automatically.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {/* Progress bar */}
                            <div className="mb-4">
                                <div className="h-2 w-full rounded-full bg-muted">
                                    <div
                                        className={`h-2 rounded-full transition-all duration-300 ${
                                            ethicsComplete === ethicsTotal ? "bg-emerald-500" : "bg-amber-500"
                                        }`}
                                        style={{ width: `${(ethicsComplete / ethicsTotal) * 100}%` }}
                                    />
                                </div>
                            </div>

                            <div className="space-y-0">
                                {ethicsState.map((item) => (
                                    <div
                                        key={item.key}
                                        className="flex items-center justify-between py-3 border-b last:border-0"
                                    >
                                        <div className="flex items-center gap-3">
                                            <button
                                                onClick={() => canEdit && toggleEthicsItem(item.key)}
                                                disabled={!canEdit}
                                                className={`h-5 w-5 rounded border flex items-center justify-center transition-colors ${
                                                    item.checked
                                                        ? "bg-emerald-500 border-emerald-500 text-white"
                                                        : "border-border hover:border-primary/50"
                                                } ${!canEdit ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
                                            >
                                                {item.checked && (
                                                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                                                        <path d="M2 6L5 9L10 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                                    </svg>
                                                )}
                                            </button>
                                            <span className={`text-sm ${item.checked ? "text-muted-foreground line-through" : "text-foreground"}`}>
                                                {item.label}
                                            </span>
                                        </div>
                                        <Badge
                                            variant="outline"
                                            className={`text-xs ${
                                                item.checked
                                                    ? "text-emerald-400 border-emerald-500/30"
                                                    : "text-muted-foreground border-border"
                                            }`}
                                        >
                                            {item.checked ? "Done" : "Pending"}
                                        </Badge>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* ---- Trust Ledger Tab (from original) ---- */}
                <TabsContent value="trust" className="space-y-4 mt-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center justify-between">
                                Trust Account Ledger
                                <div className="flex items-center gap-2">
                                    <Badge variant="secondary">{trust.length} entries</Badge>
                                    <Badge
                                        variant="outline"
                                        className={trustBalance >= 0
                                            ? "text-emerald-400 border-emerald-500/30"
                                            : "text-red-400 border-red-500/30"
                                        }
                                    >
                                        Balance: ${trustBalance.toLocaleString()}
                                    </Badge>
                                </div>
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {trust.length === 0 ? (
                                <p className="text-sm text-muted-foreground text-center py-6">
                                    No trust account entries.
                                </p>
                            ) : (
                                <div className="space-y-2">
                                    {trust.map((entry, i) => (
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
                                                {entry.type === "deposit" ? "+" : "\u2212"}${Math.abs(entry.amount).toFixed(2)}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}
