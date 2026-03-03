// ---- Negotiations Tracker Tab -------------------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

interface JournalEntry {
    id: string;
    timestamp: string;
    category: string;
    content: string;
    author: string;
}

interface NegotiationFormData {
    date: string;
    party: string;
    type: string;
    summary: string;
    terms: string;
}

const partyColors: Record<string, string> = {
    Prosecution: "bg-red-500/15 text-red-400 border-red-500/30",
    Defense: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    Mediator: "bg-purple-500/15 text-purple-400 border-purple-500/30",
};

const typeColors: Record<string, string> = {
    Offer: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    Counteroffer: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    Discussion: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    Settlement: "bg-green-500/15 text-green-400 border-green-500/30",
};

function formatTimestamp(ts: string): string {
    try {
        const d = new Date(ts);
        return d.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    } catch {
        return ts;
    }
}

function parseNegotiationContent(content: string): {
    party: string;
    type: string;
    summary: string;
    terms: string;
} {
    const lines = content.split("\n");
    let party = "";
    let type = "";
    let summary = "";
    let terms = "";

    for (const line of lines) {
        if (line.startsWith("Party: ")) party = line.slice(7);
        else if (line.startsWith("Type: ")) type = line.slice(6);
        else if (line.startsWith("Summary: ")) summary = line.slice(9);
        else if (line.startsWith("Terms: ")) terms = line.slice(7);
    }

    return { party, type, summary, terms };
}

function buildNegotiationContent(data: NegotiationFormData): string {
    return [
        `Party: ${data.party}`,
        `Type: ${data.type}`,
        `Summary: ${data.summary}`,
        data.terms ? `Terms: ${data.terms}` : "",
    ]
        .filter(Boolean)
        .join("\n");
}

const emptyForm: NegotiationFormData = {
    date: new Date().toISOString().split("T")[0],
    party: "Prosecution",
    type: "Offer",
    summary: "",
    terms: "",
};

export default function NegotiationsPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { canEdit } = useRole();
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState<NegotiationFormData>({ ...emptyForm });

    const { data, isLoading } = useQuery({
        queryKey: ["journal", caseId, "Negotiation"],
        queryFn: () =>
            api.get<JournalEntry[]>(`/cases/${caseId}/journal`, {
                params: { category: "Negotiation" },
                getToken,
            }),
    });

    const entries = data ?? [];

    const createEntry = useMutationWithToast<NegotiationFormData>({
        mutationFn: (formData) =>
            api.post(
                `/cases/${caseId}/journal`,
                {
                    category: "Negotiation",
                    content: buildNegotiationContent(formData),
                    timestamp: new Date(formData.date).toISOString(),
                },
                { getToken },
            ),
        successMessage: "Negotiation entry added",
        invalidateKeys: [["journal", caseId, "Negotiation"]],
        onSuccess: () => {
            setShowForm(false);
            setForm({ ...emptyForm });
        },
    });

    const handleSubmit = () => {
        if (!form.summary.trim()) return;
        createEntry.mutate(form);
    };

    return (
        <div className="space-y-5">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold tracking-tight">Negotiations Tracker</h2>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Track offers, counteroffers, and settlement discussions
                    </p>
                </div>
                {canEdit && !showForm && (
                    <Button size="sm" className="gap-1.5" onClick={() => setShowForm(true)}>
                        <span>+</span> Add Entry
                    </Button>
                )}
            </div>

            {/* Add Entry Form */}
            {showForm && canEdit && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">New Negotiation Entry</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div>
                                <label className="text-xs font-medium text-muted-foreground mb-1 block">
                                    Date
                                </label>
                                <Input
                                    type="date"
                                    value={form.date}
                                    onChange={(e) => setForm({ ...form, date: e.target.value })}
                                />
                            </div>
                            <div>
                                <label className="text-xs font-medium text-muted-foreground mb-1 block">
                                    Party
                                </label>
                                <select
                                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={form.party}
                                    onChange={(e) => setForm({ ...form, party: e.target.value })}
                                >
                                    <option value="Prosecution">Prosecution</option>
                                    <option value="Defense">Defense</option>
                                    <option value="Mediator">Mediator</option>
                                </select>
                            </div>
                            <div>
                                <label className="text-xs font-medium text-muted-foreground mb-1 block">
                                    Type
                                </label>
                                <select
                                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    value={form.type}
                                    onChange={(e) => setForm({ ...form, type: e.target.value })}
                                >
                                    <option value="Offer">Offer</option>
                                    <option value="Counteroffer">Counteroffer</option>
                                    <option value="Discussion">Discussion</option>
                                    <option value="Settlement">Settlement</option>
                                </select>
                            </div>
                        </div>
                        <div>
                            <label className="text-xs font-medium text-muted-foreground mb-1 block">
                                Summary
                            </label>
                            <textarea
                                className="flex min-h-[80px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                placeholder="Describe the offer, counteroffer, or discussion points..."
                                value={form.summary}
                                onChange={(e) => setForm({ ...form, summary: e.target.value })}
                            />
                        </div>
                        <div>
                            <label className="text-xs font-medium text-muted-foreground mb-1 block">
                                Terms (optional)
                            </label>
                            <textarea
                                className="flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                placeholder="Key terms, conditions, or stipulations..."
                                value={form.terms}
                                onChange={(e) => setForm({ ...form, terms: e.target.value })}
                            />
                        </div>
                        <div className="flex gap-2 justify-end">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                    setShowForm(false);
                                    setForm({ ...emptyForm });
                                }}
                            >
                                Cancel
                            </Button>
                            <Button
                                size="sm"
                                onClick={handleSubmit}
                                disabled={!form.summary.trim() || createEntry.isPending}
                            >
                                {createEntry.isPending ? "Saving..." : "Add Entry"}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Entries List */}
            {isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-24 w-full rounded-lg" />
                    ))}
                </div>
            ) : entries.length === 0 ? (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        No negotiation entries yet. Add an entry to start tracking offers and discussions.
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-3">
                    {entries.map((entry, i) => {
                        const parsed = parseNegotiationContent(entry.content);
                        return (
                            <Card key={entry.id || i} className="hover:bg-accent/20 transition-colors">
                                <CardContent className="py-4">
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="flex-1 space-y-2">
                                            <div className="flex items-center gap-2 flex-wrap">
                                                <Badge
                                                    variant="outline"
                                                    className={partyColors[parsed.party] || ""}
                                                >
                                                    {parsed.party || "Unknown"}
                                                </Badge>
                                                <Badge
                                                    variant="outline"
                                                    className={typeColors[parsed.type] || ""}
                                                >
                                                    {parsed.type || "Note"}
                                                </Badge>
                                            </div>
                                            <p className="text-sm whitespace-pre-wrap">
                                                {parsed.summary || entry.content}
                                            </p>
                                            {parsed.terms && (
                                                <div className="bg-muted rounded p-2 mt-1">
                                                    <p className="text-xs font-medium text-muted-foreground mb-0.5">
                                                        Terms
                                                    </p>
                                                    <p className="text-sm whitespace-pre-wrap">
                                                        {parsed.terms}
                                                    </p>
                                                </div>
                                            )}
                                        </div>
                                        <span className="text-xs text-muted-foreground whitespace-nowrap">
                                            {formatTimestamp(entry.timestamp)}
                                        </span>
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
