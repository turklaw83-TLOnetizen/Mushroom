// ---- Attorney Directives Tab --------------------------------------------
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

interface Directive {
    id: string;
    text: string;
    category: "fact" | "strategy" | "instruction";
    created_at?: string;
}

const CATEGORY_OPTIONS = ["fact", "strategy", "instruction"] as const;

const CATEGORY_STYLES: Record<string, string> = {
    fact: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    strategy: "bg-purple-500/15 text-purple-400 border-purple-500/30",
    instruction: "bg-amber-500/15 text-amber-400 border-amber-500/30",
};

export default function DirectivesPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { canEdit, canDelete } = useRole();
    const queryClient = useQueryClient();

    const [newText, setNewText] = useState("");
    const [newCategory, setNewCategory] = useState<Directive["category"]>("instruction");
    const [isCreating, setIsCreating] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<Directive | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    const { data, isLoading } = useQuery({
        queryKey: ["directives", caseId],
        queryFn: () =>
            api.get<Directive[]>(`/cases/${caseId}/directives`, { getToken }),
    });

    const directives = data ?? [];

    const invalidate = () =>
        queryClient.invalidateQueries({ queryKey: ["directives", caseId] });

    const handleCreate = async () => {
        const text = newText.trim();
        if (!text) return;

        setIsCreating(true);
        try {
            await api.post(
                `/cases/${caseId}/directives`,
                { text, category: newCategory },
                { getToken },
            );
            toast.success("Directive added");
            setNewText("");
            invalidate();
        } catch (err) {
            toast.error("Failed", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        } finally {
            setIsCreating(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setIsDeleting(true);
        try {
            await api.delete(
                `/cases/${caseId}/directives/${deleteTarget.id}`,
                { getToken },
            );
            toast.success("Directive removed");
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

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleCreate();
        }
    };

    return (
        <div className="space-y-5">
            {/* Header */}
            <div>
                <h2 className="text-xl font-bold tracking-tight">
                    Attorney Directives
                </h2>
                <p className="text-sm text-muted-foreground mt-0.5">
                    Directives guide AI analysis across all modules
                </p>
            </div>

            {/* Add directive form */}
            {canEdit && (
                <Card>
                    <CardContent className="py-3">
                        <div className="flex items-center gap-2">
                            <select
                                value={newCategory}
                                onChange={(e) =>
                                    setNewCategory(
                                        e.target.value as Directive["category"],
                                    )
                                }
                                className="h-9 rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
                            >
                                {CATEGORY_OPTIONS.map((cat) => (
                                    <option key={cat} value={cat}>
                                        {cat.charAt(0).toUpperCase() + cat.slice(1)}
                                    </option>
                                ))}
                            </select>
                            <Input
                                placeholder="Enter a directive for AI analysis..."
                                value={newText}
                                onChange={(e) => setNewText(e.target.value)}
                                onKeyDown={handleKeyDown}
                                disabled={isCreating}
                                className="flex-1"
                            />
                            <Button
                                onClick={handleCreate}
                                disabled={!newText.trim() || isCreating}
                                size="sm"
                            >
                                {isCreating ? "Adding..." : "Add"}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Directives list */}
            {isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-14 w-full rounded-lg" />
                    ))}
                </div>
            ) : directives.length === 0 ? (
                <Card className="border-dashed">
                    <CardContent className="py-12 text-center text-muted-foreground">
                        No directives yet. Add directives to guide AI analysis.
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-2">
                    {directives.map((directive, i) => (
                        <Card
                            key={directive.id || i}
                            className="hover:bg-accent/30 transition-colors group"
                        >
                            <CardContent className="py-3">
                                <div className="flex items-center justify-between gap-3">
                                    <div className="flex items-center gap-3 min-w-0">
                                        <Badge
                                            variant="outline"
                                            className={`text-xs shrink-0 ${
                                                CATEGORY_STYLES[directive.category] || ""
                                            }`}
                                        >
                                            {directive.category}
                                        </Badge>
                                        <p className="text-sm truncate">
                                            {directive.text}
                                        </p>
                                    </div>
                                    {canDelete && (
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive shrink-0"
                                            aria-label={`Delete directive`}
                                            onClick={() => setDeleteTarget(directive)}
                                        >
                                            ✕
                                        </Button>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Delete confirmation */}
            <ConfirmDialog
                open={!!deleteTarget}
                onOpenChange={(open) => !open && setDeleteTarget(null)}
                title="Remove Directive"
                description={`Remove "${deleteTarget?.text?.slice(0, 60)}"?`}
                confirmLabel="Remove"
                onConfirm={handleDelete}
                isLoading={isDeleting}
            />
        </div>
    );
}
