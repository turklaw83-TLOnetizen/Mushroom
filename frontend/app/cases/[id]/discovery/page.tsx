// ---- Discovery Command Center (Civil Cases Only) --------------------------
// 5-Tab page: Sent | Received | AI Draft | Productions | Privilege Log
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { useCase } from "@/hooks/use-cases";
import { usePrep } from "@/hooks/use-prep";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import type {
    DiscoveryData,
    DiscoveryRequest,
    DiscoveryItem,
    ProductionSet,
    PrivilegeEntry,
    DraftResultItem,
} from "@/types/api";

// ---- Status badge helpers --------------------------------------------------

const STATUS_COLORS: Record<string, string> = {
    draft: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    served: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    response_pending: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
    response_received: "bg-green-500/15 text-green-400 border-green-500/30",
    deficient: "bg-red-500/15 text-red-400 border-red-500/30",
    motion_to_compel: "bg-orange-500/15 text-orange-400 border-orange-500/30",
    complete: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    preparing: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    produced: "bg-green-500/15 text-green-400 border-green-500/30",
    supplemented: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
    pending: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    answered: "bg-green-500/15 text-green-400 border-green-500/30",
    objected: "bg-red-500/15 text-red-400 border-red-500/30",
};

const TYPE_LABELS: Record<string, string> = {
    interrogatories: "Interrogatories",
    rfp: "Requests for Production",
    rfa: "Requests for Admission",
};

function StatusBadge({ status }: { status: string }) {
    return (
        <Badge variant="outline" className={STATUS_COLORS[status] || ""}>
            {status.replace(/_/g, " ")}
        </Badge>
    );
}

// ---- Main Page Component ---------------------------------------------------

export default function DiscoveryPage() {
    const { id: caseId } = useParams<{ id: string }>();
    const { getToken } = useAuth();
    const qc = useQueryClient();
    const { data: caseData } = useCase(caseId);

    const { data, isLoading } = useQuery<DiscoveryData>({
        queryKey: ["discovery", caseId],
        queryFn: () =>
            api.get<DiscoveryData>(`/cases/${caseId}/discovery`, { getToken }),
        enabled: !!caseId,
    });

    // If not a civil case, show message
    if (data && !data.civil) {
        return (
            <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
                <div className="text-4xl">&#x2696;&#xFE0F;</div>
                <h2 className="text-xl font-semibold">Discovery Command Center</h2>
                <p className="text-muted-foreground max-w-md">
                    The Discovery Command Center is available for civil cases only.
                    This case is classified as{" "}
                    <Badge variant="secondary">{data.case_type}</Badge>.
                </p>
            </div>
        );
    }

    if (isLoading) {
        return (
            <div className="space-y-4">
                <Skeleton className="h-8 w-64" />
                <div className="grid grid-cols-4 gap-4">
                    {[1, 2, 3, 4].map((i) => (
                        <Skeleton key={i} className="h-24" />
                    ))}
                </div>
                <Skeleton className="h-96" />
            </div>
        );
    }

    const summary = data?.summary;

    return (
        <div className="space-y-6">
            {/* Summary Cards */}
            {summary && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card className="glass-card">
                        <CardContent className="pt-4 pb-3 px-4">
                            <p className="text-xs text-muted-foreground uppercase tracking-wider">Total Requests</p>
                            <p className="text-2xl font-bold mt-1">{summary.total_requests}</p>
                            <p className="text-xs text-muted-foreground">
                                {summary.outbound} sent &middot; {summary.inbound} received
                            </p>
                        </CardContent>
                    </Card>
                    <Card className="glass-card">
                        <CardContent className="pt-4 pb-3 px-4">
                            <p className="text-xs text-muted-foreground uppercase tracking-wider">Overdue</p>
                            <p className={`text-2xl font-bold mt-1 ${summary.overdue > 0 ? "text-red-400" : ""}`}>
                                {summary.overdue}
                            </p>
                            <p className="text-xs text-muted-foreground">responses past due</p>
                        </CardContent>
                    </Card>
                    <Card className="glass-card">
                        <CardContent className="pt-4 pb-3 px-4">
                            <p className="text-xs text-muted-foreground uppercase tracking-wider">Items</p>
                            <p className="text-2xl font-bold mt-1">{summary.total_items}</p>
                            <p className="text-xs text-muted-foreground">
                                {summary.items_answered} answered &middot; {summary.items_pending} pending
                            </p>
                        </CardContent>
                    </Card>
                    <Card className="glass-card">
                        <CardContent className="pt-4 pb-3 px-4">
                            <p className="text-xs text-muted-foreground uppercase tracking-wider">Productions</p>
                            <p className="text-2xl font-bold mt-1">{summary.production_sets}</p>
                            <p className="text-xs text-muted-foreground">
                                {summary.privilege_entries} privilege entries
                            </p>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* Tabs */}
            <Tabs defaultValue="sent" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="sent">
                        Sent ({data?.requests.filter((r) => r.direction === "outbound").length || 0})
                    </TabsTrigger>
                    <TabsTrigger value="received">
                        Received ({data?.requests.filter((r) => r.direction === "inbound").length || 0})
                    </TabsTrigger>
                    <TabsTrigger value="draft">AI Draft</TabsTrigger>
                    <TabsTrigger value="productions">
                        Productions ({data?.production_sets.length || 0})
                    </TabsTrigger>
                    <TabsTrigger value="privilege">
                        Privilege Log ({data?.privilege_log.length || 0})
                    </TabsTrigger>
                </TabsList>

                {/* ---- Tab: Sent ---- */}
                <TabsContent value="sent">
                    <RequestsTab
                        caseId={caseId}
                        requests={data?.requests.filter((r) => r.direction === "outbound") || []}
                        direction="outbound"
                        getToken={getToken}
                        onRefresh={() => qc.invalidateQueries({ queryKey: ["discovery", caseId] })}
                    />
                </TabsContent>

                {/* ---- Tab: Received ---- */}
                <TabsContent value="received">
                    <RequestsTab
                        caseId={caseId}
                        requests={data?.requests.filter((r) => r.direction === "inbound") || []}
                        direction="inbound"
                        getToken={getToken}
                        onRefresh={() => qc.invalidateQueries({ queryKey: ["discovery", caseId] })}
                    />
                </TabsContent>

                {/* ---- Tab: AI Draft ---- */}
                <TabsContent value="draft">
                    <AIDraftTab
                        caseId={caseId}
                        getToken={getToken}
                        onRefresh={() => qc.invalidateQueries({ queryKey: ["discovery", caseId] })}
                        existingRequests={data?.requests || []}
                    />
                </TabsContent>

                {/* ---- Tab: Productions ---- */}
                <TabsContent value="productions">
                    <ProductionsTab
                        caseId={caseId}
                        sets={data?.production_sets || []}
                        getToken={getToken}
                        onRefresh={() => qc.invalidateQueries({ queryKey: ["discovery", caseId] })}
                    />
                </TabsContent>

                {/* ---- Tab: Privilege Log ---- */}
                <TabsContent value="privilege">
                    <PrivilegeTab
                        caseId={caseId}
                        entries={data?.privilege_log || []}
                        getToken={getToken}
                        onRefresh={() => qc.invalidateQueries({ queryKey: ["discovery", caseId] })}
                    />
                </TabsContent>
            </Tabs>
        </div>
    );
}


// ---- Requests Tab (shared for Sent & Received) ----------------------------

function RequestsTab({
    caseId,
    requests,
    direction,
    getToken,
    onRefresh,
}: {
    caseId: string;
    requests: DiscoveryRequest[];
    direction: "outbound" | "inbound";
    getToken: () => Promise<string | null>;
    onRefresh: () => void;
}) {
    const [createOpen, setCreateOpen] = useState(false);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [editingItemId, setEditingItemId] = useState<string | null>(null);

    const createMutation = useMutationWithToast({
        mutationFn: (data: Record<string, unknown>) =>
            api.post(`/cases/${caseId}/discovery/requests`, data, { getToken }),
        successMessage: "Discovery request created",
        onSuccess: () => {
            setCreateOpen(false);
            onRefresh();
        },
    });

    const statusMutation = useMutationWithToast({
        mutationFn: ({ requestId, status }: { requestId: string; status: string }) =>
            api.patch(`/cases/${caseId}/discovery/requests/${requestId}/status`, { status }, { getToken }),
        successMessage: "Status updated",
        onSuccess: onRefresh,
    });

    const deleteMutation = useMutationWithToast({
        mutationFn: (requestId: string) =>
            api.delete(`/cases/${caseId}/discovery/requests/${requestId}`, { getToken }),
        successMessage: "Request deleted",
        onSuccess: onRefresh,
    });

    const itemMutation = useMutationWithToast({
        mutationFn: ({ requestId, itemNumber, data }: { requestId: string; itemNumber: number; data: Record<string, unknown> }) =>
            api.patch(`/cases/${caseId}/discovery/requests/${requestId}/items/${itemNumber}`, data, { getToken }),
        successMessage: "Item updated",
        onSuccess: onRefresh,
    });

    return (
        <div className="space-y-4">
            <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold">
                    {direction === "outbound" ? "Sent Discovery Requests" : "Received Discovery Requests"}
                </h3>
                <Button onClick={() => setCreateOpen(true)}>
                    + New {direction === "outbound" ? "Outbound" : "Inbound"} Request
                </Button>
            </div>

            {requests.length === 0 ? (
                <EmptyState
                    icon={direction === "outbound" ? "\uD83D\uDCE4" : "\uD83D\uDCE5"}
                    title={`No ${direction === "outbound" ? "sent" : "received"} discovery requests yet`}
                    description={direction === "outbound" ? "Create an outbound request to send interrogatories, document requests, or admissions." : "Log incoming discovery requests received from opposing counsel."}
                />
            ) : (
                <div className="space-y-3">
                    {requests.map((req) => (
                        <Card key={req.id} className="glass-card">
                            <CardContent className="p-4">
                                {/* Request Header */}
                                <div
                                    className="flex items-center justify-between cursor-pointer"
                                    onClick={() => setExpandedId(expandedId === req.id ? null : req.id)}
                                >
                                    <div className="flex items-center gap-3">
                                        <Badge variant="secondary" className="text-xs">
                                            {TYPE_LABELS[req.request_type] || req.request_type}
                                        </Badge>
                                        <span className="font-medium">{req.title}</span>
                                        <StatusBadge status={req.status} />
                                        {req.ai_drafted && (
                                            <Badge variant="outline" className="bg-violet-500/15 text-violet-400 border-violet-500/30 text-xs">
                                                AI Drafted
                                            </Badge>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-3 text-sm text-muted-foreground">
                                        <span>{req.items.length} items</span>
                                        {req.response_due && (
                                            <span>Due: {req.response_due}</span>
                                        )}
                                        <span className="text-xs">{expandedId === req.id ? "▲" : "▼"}</span>
                                    </div>
                                </div>

                                {/* Expanded Details */}
                                {expandedId === req.id && (
                                    <div className="mt-4 space-y-4 border-t border-border pt-4">
                                        {/* Meta Info */}
                                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                                            <div>
                                                <span className="text-muted-foreground">Served On:</span>{" "}
                                                <span>{req.served_on || "—"}</span>
                                            </div>
                                            <div>
                                                <span className="text-muted-foreground">Served By:</span>{" "}
                                                <span>{req.served_by || "—"}</span>
                                            </div>
                                            <div>
                                                <span className="text-muted-foreground">Date Served:</span>{" "}
                                                <span>{req.date_served || "—"}</span>
                                            </div>
                                            <div>
                                                <span className="text-muted-foreground">Response Due:</span>{" "}
                                                <span>{req.response_due || "—"}</span>
                                            </div>
                                        </div>

                                        {req.notes && (
                                            <p className="text-sm text-muted-foreground italic">{req.notes}</p>
                                        )}

                                        {/* Items */}
                                        <div className="space-y-2">
                                            <h4 className="text-sm font-semibold">Items ({req.items.length})</h4>
                                            {req.items.map((item) => (
                                                <div
                                                    key={item.number}
                                                    className="border border-border rounded-lg p-3 space-y-2"
                                                >
                                                    <div className="flex items-start justify-between gap-2">
                                                        <div className="flex-1">
                                                            <span className="text-xs font-mono text-muted-foreground mr-2">
                                                                #{item.number}
                                                            </span>
                                                            <span className="text-sm">{item.text}</span>
                                                        </div>
                                                        <StatusBadge status={item.status} />
                                                    </div>

                                                    {/* Inline response editing for inbound requests */}
                                                    {direction === "inbound" && (
                                                        <div className="space-y-2 mt-2">
                                                            {item.response && (
                                                                <div className="text-sm">
                                                                    <span className="text-muted-foreground">Response: </span>
                                                                    {item.response}
                                                                </div>
                                                            )}
                                                            {item.objection && (
                                                                <div className="text-sm text-red-400">
                                                                    <span className="text-muted-foreground">Objection: </span>
                                                                    {item.objection}
                                                                </div>
                                                            )}
                                                            {editingItemId === `${req.id}-${item.number}` ? (
                                                                <InlineItemEditor
                                                                    item={item}
                                                                    onSave={(data) => {
                                                                        itemMutation.mutate({
                                                                            requestId: req.id,
                                                                            itemNumber: item.number,
                                                                            data,
                                                                        });
                                                                        setEditingItemId(null);
                                                                    }}
                                                                    onCancel={() => setEditingItemId(null)}
                                                                />
                                                            ) : (
                                                                <Button
                                                                    variant="ghost"
                                                                    size="sm"
                                                                    className="text-xs h-7"
                                                                    onClick={() => setEditingItemId(`${req.id}-${item.number}`)}
                                                                >
                                                                    {item.response ? "Edit Response" : "Add Response"}
                                                                </Button>
                                                            )}
                                                        </div>
                                                    )}

                                                    {/* Show responses on outbound */}
                                                    {direction === "outbound" && (item.response || item.objection) && (
                                                        <div className="space-y-1 mt-2 pl-4 border-l-2 border-border">
                                                            {item.response && (
                                                                <p className="text-sm">
                                                                    <span className="text-muted-foreground">Response: </span>
                                                                    {item.response}
                                                                </p>
                                                            )}
                                                            {item.objection && (
                                                                <p className="text-sm text-red-400">
                                                                    <span className="text-muted-foreground">Objection: </span>
                                                                    {item.objection}
                                                                </p>
                                                            )}
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                        </div>

                                        {/* Actions */}
                                        <div className="flex gap-2 pt-2">
                                            <Select
                                                value={req.status}
                                                onValueChange={(s) =>
                                                    statusMutation.mutate({ requestId: req.id, status: s })
                                                }
                                            >
                                                <SelectTrigger className="w-48 h-8 text-xs">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {["draft", "served", "response_pending", "response_received", "deficient", "motion_to_compel", "complete"].map((s) => (
                                                        <SelectItem key={s} value={s} className="text-xs">
                                                            {s.replace(/_/g, " ")}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                            <Button
                                                variant="destructive"
                                                size="sm"
                                                className="h-8 text-xs"
                                                onClick={() => {
                                                    if (confirm("Delete this discovery request?")) {
                                                        deleteMutation.mutate(req.id);
                                                    }
                                                }}
                                            >
                                                Delete
                                            </Button>
                                        </div>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Create Dialog */}
            <CreateRequestDialog
                open={createOpen}
                onOpenChange={setCreateOpen}
                direction={direction}
                onSubmit={(data) => createMutation.mutate(data)}
                isLoading={createMutation.isPending}
            />
        </div>
    );
}


// ---- Inline Item Editor ---------------------------------------------------

function InlineItemEditor({
    item,
    onSave,
    onCancel,
}: {
    item: DiscoveryItem;
    onSave: (data: Record<string, unknown>) => void;
    onCancel: () => void;
}) {
    const [response, setResponse] = useState(item.response || "");
    const [objection, setObjection] = useState(item.objection || "");
    const [status, setStatus] = useState<string>(item.status || "pending");

    return (
        <div className="space-y-2 bg-muted/30 rounded-lg p-3">
            <div>
                <Label className="text-xs">Response</Label>
                <Textarea
                    value={response}
                    onChange={(e) => setResponse(e.target.value)}
                    className="text-sm min-h-[60px]"
                    placeholder="Enter response..."
                />
            </div>
            <div>
                <Label className="text-xs">Objection (if any)</Label>
                <Textarea
                    value={objection}
                    onChange={(e) => setObjection(e.target.value)}
                    className="text-sm min-h-[40px]"
                    placeholder="Enter objection..."
                />
            </div>
            <div className="flex items-center gap-3">
                <Select value={status} onValueChange={setStatus}>
                    <SelectTrigger className="w-36 h-7 text-xs">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {["pending", "answered", "objected", "supplemented"].map((s) => (
                            <SelectItem key={s} value={s} className="text-xs">
                                {s}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <Button size="sm" className="h-7 text-xs" onClick={() => onSave({ response, objection, status })}>
                    Save
                </Button>
                <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={onCancel}>
                    Cancel
                </Button>
            </div>
        </div>
    );
}


// ---- Create Request Dialog ------------------------------------------------

function CreateRequestDialog({
    open,
    onOpenChange,
    direction,
    onSubmit,
    isLoading,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    direction: "outbound" | "inbound";
    onSubmit: (data: Record<string, unknown>) => void;
    isLoading: boolean;
}) {
    const [requestType, setRequestType] = useState("interrogatories");
    const [title, setTitle] = useState("");
    const [servedOn, setServedOn] = useState("");
    const [servedBy, setServedBy] = useState("");
    const [dateServed, setDateServed] = useState("");
    const [notes, setNotes] = useState("");

    const handleSubmit = () => {
        onSubmit({
            direction,
            request_type: requestType,
            title,
            served_on: servedOn,
            served_by: servedBy,
            date_served: dateServed,
            notes,
        });
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg">
                <DialogHeader>
                    <DialogTitle>
                        New {direction === "outbound" ? "Outbound" : "Inbound"} Discovery Request
                    </DialogTitle>
                    <DialogDescription>
                        Track a discovery request {direction === "outbound" ? "sent to" : "received from"} the opposing party.
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                    <div>
                        <Label>Request Type</Label>
                        <Select value={requestType} onValueChange={setRequestType}>
                            <SelectTrigger><SelectValue /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="interrogatories">Interrogatories</SelectItem>
                                <SelectItem value="rfp">Requests for Production</SelectItem>
                                <SelectItem value="rfa">Requests for Admission</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <div>
                        <Label>Title</Label>
                        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. First Set of Interrogatories" />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <Label>Served On</Label>
                            <Input value={servedOn} onChange={(e) => setServedOn(e.target.value)} placeholder="Party name" />
                        </div>
                        <div>
                            <Label>Served By</Label>
                            <Input value={servedBy} onChange={(e) => setServedBy(e.target.value)} placeholder="Party name" />
                        </div>
                    </div>
                    <div>
                        <Label>Date Served</Label>
                        <Input type="date" value={dateServed} onChange={(e) => setDateServed(e.target.value)} />
                    </div>
                    <div>
                        <Label>Notes</Label>
                        <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional notes..." className="min-h-[60px]" />
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
                    <Button onClick={handleSubmit} disabled={isLoading}>
                        {isLoading ? "Creating..." : "Create Request"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}


// ---- AI Draft Tab ---------------------------------------------------------

function AIDraftTab({
    caseId,
    getToken,
    onRefresh,
    existingRequests,
}: {
    caseId: string;
    getToken: () => Promise<string | null>;
    onRefresh: () => void;
    existingRequests: DiscoveryRequest[];
}) {
    const [requestType, setRequestType] = useState("interrogatories");
    const [focusWitnesses, setFocusWitnesses] = useState("");
    const [focusThemes, setFocusThemes] = useState("");
    const [focusGaps, setFocusGaps] = useState("");
    const [dateRange, setDateRange] = useState("");
    const [customInstructions, setCustomInstructions] = useState("");
    const [numItems, setNumItems] = useState([25]);
    const [draftItems, setDraftItems] = useState<DraftResultItem[]>([]);
    const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set());
    const [showMeetConfer, setShowMeetConfer] = useState(false);
    const [meetConferRequestId, setMeetConferRequestId] = useState("");
    const [meetConferItems, setMeetConferItems] = useState("");
    const [meetConferInstructions, setMeetConferInstructions] = useState("");
    const [meetConferLetter, setMeetConferLetter] = useState("");

    const draftMutation = useMutationWithToast<void, { items: DraftResultItem[] }>({
        mutationFn: () =>
            api.post<{ items: DraftResultItem[] }>(`/cases/${caseId}/discovery/draft`, {
                request_type: requestType,
                focus_witnesses: focusWitnesses ? focusWitnesses.split(",").map((s) => s.trim()) : [],
                focus_themes: focusThemes ? focusThemes.split(",").map((s) => s.trim()) : [],
                focus_evidence_gaps: focusGaps ? focusGaps.split(",").map((s) => s.trim()) : [],
                date_range: dateRange,
                custom_instructions: customInstructions,
                num_items: numItems[0],
            }, { getToken }),
        successMessage: "Draft generated",
        onSuccess: (data) => {
            const items = (data as { items: DraftResultItem[] }).items || [];
            setDraftItems(items);
            setSelectedItems(new Set(items.map((i) => i.number)));
        },
    });

    const saveDraftMutation = useMutationWithToast<void>({
        mutationFn: () => {
            const items = draftItems
                .filter((i) => selectedItems.has(i.number))
                .map((i) => ({ number: i.number, text: i.text, response: "", objection: "", status: "pending" }));
            return api.post(`/cases/${caseId}/discovery/requests`, {
                direction: "outbound",
                request_type: requestType,
                title: `${TYPE_LABELS[requestType]} — AI Draft`,
                items,
                notes: "AI-drafted. Review and edit before serving.",
            }, { getToken });
        },
        successMessage: "Saved as draft request",
        onSuccess: () => {
            setDraftItems([]);
            setSelectedItems(new Set());
            onRefresh();
        },
    });

    const meetConferMutation = useMutationWithToast<void, { letter: string }>({
        mutationFn: () =>
            api.post<{ letter: string }>(`/cases/${caseId}/discovery/meet-confer`, {
                request_id: meetConferRequestId,
                deficient_item_numbers: meetConferItems.split(",").map((s) => parseInt(s.trim())).filter(Boolean),
                custom_instructions: meetConferInstructions,
            }, { getToken }),
        successMessage: "Letter generated",
        onSuccess: (data) => {
            setMeetConferLetter((data as { letter: string }).letter || "");
        },
    });

    const toggleItem = (num: number) => {
        const next = new Set(selectedItems);
        if (next.has(num)) next.delete(num);
        else next.add(num);
        setSelectedItems(next);
    };

    const deficientRequests = existingRequests.filter(
        (r) => r.direction === "outbound" && (r.status === "response_received" || r.status === "deficient")
    );

    return (
        <div className="space-y-6">
            {/* Drafting Controls */}
            <Card className="glass-card">
                <CardHeader>
                    <CardTitle className="text-lg">AI Discovery Drafter</CardTitle>
                    <CardDescription>
                        Generate targeted discovery requests using your case analysis data.
                        The AI will draft specific, non-compound requests based on your case facts.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Step 1: Type Selection */}
                    <div>
                        <Label className="text-sm font-semibold">1. Request Type</Label>
                        <div className="flex gap-3 mt-2">
                            {(["interrogatories", "rfp", "rfa"] as const).map((t) => (
                                <Button
                                    key={t}
                                    variant={requestType === t ? "default" : "outline"}
                                    size="sm"
                                    onClick={() => setRequestType(t)}
                                >
                                    {TYPE_LABELS[t]}
                                </Button>
                            ))}
                        </div>
                    </div>

                    {/* Step 2: Targeting */}
                    <div className="space-y-3">
                        <Label className="text-sm font-semibold">2. Targeting (Optional)</Label>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <Label className="text-xs text-muted-foreground">Focus Witnesses (comma-separated)</Label>
                                <Input
                                    value={focusWitnesses}
                                    onChange={(e) => setFocusWitnesses(e.target.value)}
                                    placeholder="e.g. John Smith, Jane Doe"
                                />
                            </div>
                            <div>
                                <Label className="text-xs text-muted-foreground">Focus Themes (comma-separated)</Label>
                                <Input
                                    value={focusThemes}
                                    onChange={(e) => setFocusThemes(e.target.value)}
                                    placeholder="e.g. negligence, damages, liability"
                                />
                            </div>
                            <div>
                                <Label className="text-xs text-muted-foreground">Evidence Gaps (comma-separated)</Label>
                                <Input
                                    value={focusGaps}
                                    onChange={(e) => setFocusGaps(e.target.value)}
                                    placeholder="e.g. medical records, communications"
                                />
                            </div>
                            <div>
                                <Label className="text-xs text-muted-foreground">Date Range</Label>
                                <Input
                                    value={dateRange}
                                    onChange={(e) => setDateRange(e.target.value)}
                                    placeholder="e.g. Jan 2024 - Jun 2025"
                                />
                            </div>
                        </div>
                        <div>
                            <Label className="text-xs text-muted-foreground">Custom Instructions</Label>
                            <Textarea
                                value={customInstructions}
                                onChange={(e) => setCustomInstructions(e.target.value)}
                                placeholder="Any specific instructions for the AI drafter..."
                                className="min-h-[60px]"
                            />
                        </div>
                        <div>
                            <Label className="text-xs text-muted-foreground">Number of Items: {numItems[0]}</Label>
                            <Slider
                                value={numItems}
                                onValueChange={setNumItems}
                                min={5}
                                max={50}
                                step={5}
                                className="mt-2"
                            />
                        </div>
                    </div>

                    {/* Generate Button */}
                    <Button
                        onClick={() => draftMutation.mutate()}
                        disabled={draftMutation.isPending}
                        className="w-full"
                    >
                        {draftMutation.isPending ? "Generating (this may take 30-60 seconds)..." : `Generate ${TYPE_LABELS[requestType]}`}
                    </Button>
                </CardContent>
            </Card>

            {/* Draft Results */}
            {draftItems.length > 0 && (
                <Card className="glass-card">
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-lg">
                                Draft Results ({draftItems.length} items)
                            </CardTitle>
                            <div className="flex gap-2">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setSelectedItems(new Set(draftItems.map((i) => i.number)))}
                                >
                                    Select All
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setSelectedItems(new Set())}
                                >
                                    Deselect All
                                </Button>
                            </div>
                        </div>
                        <CardDescription>
                            Review, edit, and select items to include. Selected: {selectedItems.size}/{draftItems.length}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        {draftItems.map((item) => (
                            <div
                                key={item.number}
                                className={`border rounded-lg p-3 space-y-2 transition-colors ${
                                    selectedItems.has(item.number)
                                        ? "border-brand-indigo/50 bg-brand-indigo/5"
                                        : "border-border opacity-50"
                                }`}
                            >
                                <div className="flex items-start gap-3">
                                    <Checkbox
                                        checked={selectedItems.has(item.number)}
                                        onCheckedChange={() => toggleItem(item.number)}
                                        className="mt-1"
                                    />
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2">
                                            <span className="text-xs font-mono text-muted-foreground">
                                                #{item.number}
                                            </span>
                                        </div>
                                        <p className="text-sm mt-1">{item.text}</p>
                                        <p className="text-xs text-muted-foreground mt-1 italic">
                                            Rationale: {item.targeting_rationale}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        ))}

                        <Button
                            onClick={() => saveDraftMutation.mutate()}
                            disabled={saveDraftMutation.isPending || selectedItems.size === 0}
                            className="w-full mt-4"
                        >
                            {saveDraftMutation.isPending
                                ? "Saving..."
                                : `Save ${selectedItems.size} Items as Draft Request`}
                        </Button>
                    </CardContent>
                </Card>
            )}

            {/* Meet & Confer Section */}
            <Card className="glass-card">
                <CardHeader>
                    <CardTitle className="text-lg">Meet &amp; Confer Letter Generator</CardTitle>
                    <CardDescription>
                        Generate a professional meet-and-confer letter for deficient discovery responses.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {deficientRequests.length === 0 ? (
                        <p className="text-sm text-muted-foreground">
                            No outbound requests with received responses available for meet-and-confer.
                            Mark a request as &quot;response_received&quot; or &quot;deficient&quot; first.
                        </p>
                    ) : (
                        <>
                            <div>
                                <Label>Select Request</Label>
                                <Select value={meetConferRequestId} onValueChange={setMeetConferRequestId}>
                                    <SelectTrigger><SelectValue placeholder="Choose a request..." /></SelectTrigger>
                                    <SelectContent>
                                        {deficientRequests.map((r) => (
                                            <SelectItem key={r.id} value={r.id}>
                                                {r.title} ({r.items.length} items)
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div>
                                <Label>Deficient Item Numbers (comma-separated)</Label>
                                <Input
                                    value={meetConferItems}
                                    onChange={(e) => setMeetConferItems(e.target.value)}
                                    placeholder="e.g. 1, 3, 5, 8"
                                />
                            </div>
                            <div>
                                <Label>Custom Instructions</Label>
                                <Textarea
                                    value={meetConferInstructions}
                                    onChange={(e) => setMeetConferInstructions(e.target.value)}
                                    placeholder="Additional guidance for the letter..."
                                    className="min-h-[40px]"
                                />
                            </div>
                            <Button
                                onClick={() => meetConferMutation.mutate()}
                                disabled={meetConferMutation.isPending || !meetConferRequestId || !meetConferItems}
                            >
                                {meetConferMutation.isPending ? "Generating..." : "Generate Letter"}
                            </Button>
                        </>
                    )}

                    {meetConferLetter && (
                        <div className="mt-4 border border-border rounded-lg p-4 bg-muted/20">
                            <div className="flex justify-between items-center mb-3">
                                <h4 className="text-sm font-semibold">Generated Letter</h4>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => {
                                        navigator.clipboard.writeText(meetConferLetter);
                                        toast.success("Copied to clipboard");
                                    }}
                                >
                                    Copy
                                </Button>
                            </div>
                            <pre className="text-sm whitespace-pre-wrap font-sans">
                                {meetConferLetter}
                            </pre>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}


// ---- Productions Tab ------------------------------------------------------

function ProductionsTab({
    caseId,
    sets,
    getToken,
    onRefresh,
}: {
    caseId: string;
    sets: ProductionSet[];
    getToken: () => Promise<string | null>;
    onRefresh: () => void;
}) {
    const [createOpen, setCreateOpen] = useState(false);
    const [title, setTitle] = useState("");
    const [batesPrefix, setBatesPrefix] = useState("DEF");
    const [producedTo, setProducedTo] = useState("");
    const [dateProduced, setDateProduced] = useState("");

    const createMutation = useMutationWithToast<void>({
        mutationFn: () =>
            api.post(`/cases/${caseId}/discovery/productions`, {
                title,
                bates_prefix: batesPrefix,
                produced_to: producedTo,
                date_produced: dateProduced,
                documents: [],
            }, { getToken }),
        successMessage: "Production set created",
        onSuccess: () => {
            setCreateOpen(false);
            setTitle("");
            onRefresh();
        },
    });

    return (
        <div className="space-y-4">
            <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold">Production Sets</h3>
                <Button onClick={() => setCreateOpen(true)}>+ New Production Set</Button>
            </div>

            {sets.length === 0 ? (
                <EmptyState
                    icon="\uD83D\uDCE6"
                    title="No production sets yet"
                    description="Create one to track document productions with Bates numbering."
                />
            ) : (
                <div className="space-y-3">
                    {sets.map((ps) => (
                        <Card key={ps.id} className="glass-card">
                            <CardContent className="p-4">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <span className="font-medium">{ps.title}</span>
                                        <StatusBadge status={ps.status} />
                                        <Badge variant="secondary" className="text-xs font-mono">
                                            {ps.bates_prefix}
                                        </Badge>
                                    </div>
                                    <div className="text-sm text-muted-foreground">
                                        {ps.documents.length} documents
                                        {ps.produced_to && ` | To: ${ps.produced_to}`}
                                        {ps.date_produced && ` | ${ps.date_produced}`}
                                    </div>
                                </div>
                                {ps.documents.length > 0 && (
                                    <div className="mt-3 space-y-1">
                                        {ps.documents.map((doc, i) => (
                                            <div key={i} className="flex items-center gap-3 text-sm">
                                                <span className="font-mono text-xs text-muted-foreground w-32">
                                                    {doc.bates_range || "—"}
                                                </span>
                                                <span>{doc.filename}</span>
                                                {doc.description && (
                                                    <span className="text-muted-foreground">— {doc.description}</span>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Create Dialog */}
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>New Production Set</DialogTitle>
                        <DialogDescription>
                            Create a production set to track documents produced with Bates numbering.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div>
                            <Label>Title</Label>
                            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. First Production" />
                        </div>
                        <div>
                            <Label>Bates Prefix</Label>
                            <Input value={batesPrefix} onChange={(e) => setBatesPrefix(e.target.value)} placeholder="DEF" />
                        </div>
                        <div>
                            <Label>Produced To</Label>
                            <Input value={producedTo} onChange={(e) => setProducedTo(e.target.value)} placeholder="Opposing party" />
                        </div>
                        <div>
                            <Label>Date Produced</Label>
                            <Input type="date" value={dateProduced} onChange={(e) => setDateProduced(e.target.value)} />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
                        <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending || !title}>
                            {createMutation.isPending ? "Creating..." : "Create"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}


// ---- Privilege Log Tab ----------------------------------------------------

function PrivilegeTab({
    caseId,
    entries,
    getToken,
    onRefresh,
}: {
    caseId: string;
    entries: PrivilegeEntry[];
    getToken: () => Promise<string | null>;
    onRefresh: () => void;
}) {
    const [createOpen, setCreateOpen] = useState(false);
    const [document, setDocument] = useState("");
    const [batesNumber, setBatesNumber] = useState("");
    const [privilegeType, setPrivilegeType] = useState("attorney-client");
    const [description, setDescription] = useState("");
    const [entryDate, setEntryDate] = useState("");
    const [fromParty, setFromParty] = useState("");
    const [toParty, setToParty] = useState("");
    const [subject, setSubject] = useState("");
    const [basis, setBasis] = useState("");

    const createMutation = useMutationWithToast<void>({
        mutationFn: () =>
            api.post(`/cases/${caseId}/discovery/privilege`, {
                document,
                bates_number: batesNumber,
                privilege_type: privilegeType,
                description,
                entry_date: entryDate,
                from_party: fromParty,
                to_party: toParty,
                subject,
                basis,
            }, { getToken }),
        successMessage: "Privilege entry added",
        onSuccess: () => {
            setCreateOpen(false);
            setDocument("");
            setBatesNumber("");
            setDescription("");
            setEntryDate("");
            setFromParty("");
            setToParty("");
            setSubject("");
            setBasis("");
            onRefresh();
        },
    });

    const deleteMutation = useMutationWithToast({
        mutationFn: (entryId: string) =>
            api.delete(`/cases/${caseId}/discovery/privilege/${entryId}`, { getToken }),
        successMessage: "Entry removed",
        onSuccess: onRefresh,
    });

    return (
        <div className="space-y-4">
            <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold">Privilege Log</h3>
                <Button onClick={() => setCreateOpen(true)}>+ Add Entry</Button>
            </div>

            {entries.length === 0 ? (
                <EmptyState
                    icon="\uD83D\uDD12"
                    title="No privilege log entries"
                    description="Add entries for documents withheld from production."
                />
            ) : (
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="sticky top-0 z-10 bg-background">
                            <tr className="border-b border-border text-left text-muted-foreground">
                                <th className="py-2 px-3">Document</th>
                                <th className="py-2 px-3">Bates #</th>
                                <th className="py-2 px-3">Privilege</th>
                                <th className="py-2 px-3">From</th>
                                <th className="py-2 px-3">To</th>
                                <th className="py-2 px-3">Date</th>
                                <th className="py-2 px-3">Subject</th>
                                <th className="py-2 px-3 w-8"></th>
                            </tr>
                        </thead>
                        <tbody>
                            {entries.map((entry) => (
                                <tr key={entry.id} className="border-b border-border/50 hover:bg-muted/20">
                                    <td className="py-2 px-3">{entry.document}</td>
                                    <td className="py-2 px-3 font-mono text-xs">{entry.bates_number}</td>
                                    <td className="py-2 px-3">
                                        <Badge variant="outline" className="text-xs">
                                            {entry.privilege_type.replace(/_/g, " ")}
                                        </Badge>
                                    </td>
                                    <td className="py-2 px-3">{entry.from_party}</td>
                                    <td className="py-2 px-3">{entry.to_party}</td>
                                    <td className="py-2 px-3">{entry.date}</td>
                                    <td className="py-2 px-3">{entry.subject}</td>
                                    <td className="py-2 px-3">
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="h-6 w-6 p-0 text-destructive"
                                            onClick={() => {
                                                if (confirm("Remove this privilege entry?")) {
                                                    deleteMutation.mutate(entry.id);
                                                }
                                            }}
                                        >
                                            &#x2715;
                                        </Button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Create Dialog */}
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Add Privilege Log Entry</DialogTitle>
                        <DialogDescription>
                            Log a document withheld from production on privilege grounds.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <Label>Document</Label>
                                <Input value={document} onChange={(e) => setDocument(e.target.value)} placeholder="Document name" />
                            </div>
                            <div>
                                <Label>Bates Number</Label>
                                <Input value={batesNumber} onChange={(e) => setBatesNumber(e.target.value)} placeholder="e.g. DEF-001" />
                            </div>
                        </div>
                        <div>
                            <Label>Privilege Type</Label>
                            <Select value={privilegeType} onValueChange={setPrivilegeType}>
                                <SelectTrigger><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="attorney-client">Attorney-Client</SelectItem>
                                    <SelectItem value="work_product">Work Product</SelectItem>
                                    <SelectItem value="joint_defense">Joint Defense</SelectItem>
                                    <SelectItem value="other">Other</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <Label>From</Label>
                                <Input value={fromParty} onChange={(e) => setFromParty(e.target.value)} placeholder="Sender" />
                            </div>
                            <div>
                                <Label>To</Label>
                                <Input value={toParty} onChange={(e) => setToParty(e.target.value)} placeholder="Recipient" />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <Label>Date</Label>
                                <Input type="date" value={entryDate} onChange={(e) => setEntryDate(e.target.value)} />
                            </div>
                            <div>
                                <Label>Subject</Label>
                                <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject matter" />
                            </div>
                        </div>
                        <div>
                            <Label>Description</Label>
                            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Brief description of the document" className="min-h-[40px]" />
                        </div>
                        <div>
                            <Label>Basis for Privilege</Label>
                            <Textarea value={basis} onChange={(e) => setBasis(e.target.value)} placeholder="Legal basis for withholding" className="min-h-[40px]" />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
                        <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending || !document}>
                            {createMutation.isPending ? "Adding..." : "Add Entry"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
