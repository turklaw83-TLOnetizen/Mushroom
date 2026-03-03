// ---- Journal Tab --------------------------------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { DataPage } from "@/components/shared/data-page";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface JournalEntry {
    id: string;
    text: string;
    category: string;
    created_at: string;
    updated_at?: string;
}

const CATEGORIES = ["General", "Court", "Investigation", "Strategy", "Client"] as const;

const CATEGORY_STYLES: Record<string, string> = {
    General: "bg-slate-500/15 text-slate-400 border-slate-500/30",
    Court: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    Investigation: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    Strategy: "bg-purple-500/15 text-purple-400 border-purple-500/30",
    Client: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
};

function formatTimestamp(ts: string): string {
    try {
        const d = new Date(ts);
        return d.toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "numeric",
            minute: "2-digit",
        });
    } catch {
        return ts;
    }
}

export default function JournalPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { canEdit, canDelete } = useRole();
    const queryClient = useQueryClient();

    // Add entry form state
    const [showAddForm, setShowAddForm] = useState(false);
    const [newText, setNewText] = useState("");
    const [newCategory, setNewCategory] = useState<string>("General");
    const [isCreating, setIsCreating] = useState(false);

    // Inline edit state
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editText, setEditText] = useState("");
    const [editCategory, setEditCategory] = useState<string>("General");
    const [isSaving, setIsSaving] = useState(false);

    // Delete state
    const [deleteTarget, setDeleteTarget] = useState<JournalEntry | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const query = useQuery({
        queryKey: ["journal", caseId],
        queryFn: () =>
            api.get<JournalEntry[]>(`/cases/${caseId}/journal`, { getToken }),
    });

    const invalidate = () =>
        queryClient.invalidateQueries({ queryKey: ["journal", caseId] });

    const handleCreate = async () => {
        const text = newText.trim();
        if (!text) return;

        setIsCreating(true);
        try {
            await api.post(
                `/cases/${caseId}/journal`,
                { text, category: newCategory },
                { getToken },
            );
            toast.success("Journal entry added");
            setNewText("");
            setNewCategory("General");
            setShowAddForm(false);
            invalidate();
        } catch (err) {
            toast.error("Failed", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        } finally {
            setIsCreating(false);
        }
    };

    const handleStartEdit = (entry: JournalEntry) => {
        setEditingId(entry.id);
        setEditText(entry.text);
        setEditCategory(entry.category);
    };

    const handleCancelEdit = () => {
        setEditingId(null);
        setEditText("");
        setEditCategory("General");
    };

    const handleSaveEdit = async () => {
        if (!editingId || !editText.trim()) return;

        setIsSaving(true);
        try {
            await api.put(
                `/cases/${caseId}/journal/${editingId}`,
                { text: editText.trim(), category: editCategory },
                { getToken },
            );
            toast.success("Entry updated");
            setEditingId(null);
            invalidate();
        } catch (err) {
            toast.error("Failed", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        } finally {
            setIsSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setIsDeleting(true);
        try {
            await api.delete(
                `/cases/${caseId}/journal/${deleteTarget.id}`,
                { getToken },
            );
            toast.success("Entry deleted");
            invalidate();
        } catch (err) {
            toast.error("Failed", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        } finally {
            setIsDeleting(false);
            setDeleteTarget(null);
        }
    };

    return (
        <DataPage
            title="Journal"
            subtitle="Case notes and observations"
            query={query}
            searchFilter={(entry, s) =>
                entry.text.toLowerCase().includes(s) ||
                entry.category.toLowerCase().includes(s)
            }
            searchPlaceholder="Search journal entries..."
            createLabel={canEdit ? "New Entry" : null}
            onCreateClick={() => setShowAddForm(true)}
            renderItem={(entry, i) => {
                const isEditing = editingId === entry.id;

                if (isEditing) {
                    return (
                        <Card key={entry.id || i} className="border-primary/50">
                            <CardContent className="py-3 space-y-3">
                                <div className="flex items-center gap-2">
                                    <select
                                        value={editCategory}
                                        onChange={(e) => setEditCategory(e.target.value)}
                                        className="h-9 rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
                                    >
                                        {CATEGORIES.map((cat) => (
                                            <option key={cat} value={cat}>
                                                {cat}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                                <textarea
                                    value={editText}
                                    onChange={(e) => setEditText(e.target.value)}
                                    rows={4}
                                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-y"
                                />
                                <div className="flex items-center gap-2 justify-end">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleCancelEdit}
                                        disabled={isSaving}
                                    >
                                        Cancel
                                    </Button>
                                    <Button
                                        size="sm"
                                        onClick={handleSaveEdit}
                                        disabled={!editText.trim() || isSaving}
                                    >
                                        {isSaving ? "Saving..." : "Save"}
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    );
                }

                return (
                    <Card
                        key={entry.id || i}
                        className="hover:bg-accent/30 transition-colors group"
                    >
                        <CardContent className="py-3">
                            <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-2 mb-1.5">
                                        <Badge
                                            variant="outline"
                                            className={`text-xs ${
                                                CATEGORY_STYLES[entry.category] || ""
                                            }`}
                                        >
                                            {entry.category}
                                        </Badge>
                                        <span className="text-xs text-muted-foreground">
                                            {formatTimestamp(entry.created_at)}
                                        </span>
                                        {entry.updated_at &&
                                            entry.updated_at !== entry.created_at && (
                                                <span className="text-xs text-muted-foreground italic">
                                                    (edited)
                                                </span>
                                            )}
                                    </div>
                                    <p className="text-sm whitespace-pre-wrap">
                                        {entry.text}
                                    </p>
                                </div>
                                <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                                    {canEdit && (
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-7 w-7"
                                            aria-label="Edit entry"
                                            onClick={() => handleStartEdit(entry)}
                                        >
                                            ✎
                                        </Button>
                                    )}
                                    {canDelete && (
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-7 w-7 text-destructive"
                                            aria-label="Delete entry"
                                            onClick={() => setDeleteTarget(entry)}
                                        >
                                            ✕
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                );
            }}
        >
            {/* Add entry form (shown when "New Entry" clicked) */}
            {showAddForm && canEdit && (
                <Card className="border-primary/50">
                    <CardContent className="py-4 space-y-3">
                        <div className="flex items-center gap-2">
                            <select
                                value={newCategory}
                                onChange={(e) => setNewCategory(e.target.value)}
                                className="h-9 rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
                            >
                                {CATEGORIES.map((cat) => (
                                    <option key={cat} value={cat}>
                                        {cat}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <textarea
                            placeholder="Write your journal entry..."
                            value={newText}
                            onChange={(e) => setNewText(e.target.value)}
                            rows={4}
                            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-y"
                            autoFocus
                        />
                        <div className="flex items-center gap-2 justify-end">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                    setShowAddForm(false);
                                    setNewText("");
                                    setNewCategory("General");
                                }}
                                disabled={isCreating}
                            >
                                Cancel
                            </Button>
                            <Button
                                size="sm"
                                onClick={handleCreate}
                                disabled={!newText.trim() || isCreating}
                            >
                                {isCreating ? "Adding..." : "Add Entry"}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Delete confirmation */}
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
                title="Delete Journal Entry"
                description={`Delete "${deleteTarget?.text?.slice(0, 60)}"? This cannot be undone.`}
                confirmLabel="Delete"
                onConfirm={handleDelete}
                isLoading={isDeleting}
            />
        </DataPage>
    );
}
