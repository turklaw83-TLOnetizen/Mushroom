// ---- Case Table ---------------------------------------------------------
"use client";

import type { CaseItem } from "@/hooks/use-cases";
import { formatDate } from "@/lib/constants";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";

const phaseColors: Record<string, string> = {
    active: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    closed: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    archived: "bg-amber-500/15 text-amber-400 border-amber-500/30",
};

function readinessGrade(score: number): { letter: string; color: string } {
    if (score >= 90) return { letter: "A", color: "text-emerald-400 bg-emerald-500/15" };
    if (score >= 80) return { letter: "B", color: "text-blue-400 bg-blue-500/15" };
    if (score >= 70) return { letter: "C", color: "text-yellow-400 bg-yellow-500/15" };
    if (score >= 60) return { letter: "D", color: "text-orange-400 bg-orange-500/15" };
    return { letter: "F", color: "text-red-400 bg-red-500/15" };
}

export function CaseTable({
    cases,
    onRowClick,
    onDelete,
}: {
    cases: CaseItem[];
    onRowClick: (c: CaseItem) => void;
    onDelete?: (c: CaseItem) => void;
}) {
    if (cases.length === 0) {
        return (
            <EmptyState
                icon="📁"
                title="No cases yet"
                description="Create your first case to get started with analysis and preparation."
            />
        );
    }

    return (
        <div className="rounded-lg border border-border overflow-hidden">
            <Table>
                <TableHeader>
                    <TableRow className="bg-muted/50 hover:bg-muted/50">
                        <TableHead className="font-semibold">Case Name</TableHead>
                        <TableHead className="font-semibold hidden md:table-cell">Client</TableHead>
                        <TableHead className="font-semibold hidden lg:table-cell">Category</TableHead>
                        <TableHead className="font-semibold">Phase</TableHead>
                        <TableHead className="font-semibold text-center hidden lg:table-cell">Health</TableHead>
                        <TableHead className="font-semibold text-right hidden sm:table-cell">Updated</TableHead>
                        {onDelete && <TableHead className="w-10" />}
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {cases.map((c) => (
                        <TableRow
                            key={c.id}
                            onClick={() => onRowClick(c)}
                            className="cursor-pointer transition-colors hover:bg-accent/50 group stagger-item"
                        >
                            <TableCell className="font-medium">{c.name}</TableCell>
                            <TableCell className="text-muted-foreground hidden md:table-cell">
                                {c.client_name || "—"}
                            </TableCell>
                            <TableCell className="text-muted-foreground hidden lg:table-cell">
                                {c.case_category || c.case_type || "—"}
                            </TableCell>
                            <TableCell>
                                <Badge
                                    variant="outline"
                                    className={phaseColors[c.phase] || phaseColors.active}
                                >
                                    {c.phase}
                                    {c.sub_phase && ` / ${c.sub_phase}`}
                                </Badge>
                            </TableCell>
                            <TableCell className="text-center hidden lg:table-cell">
                                {c.readiness_score != null ? (
                                    <span className={`inline-flex items-center justify-center h-6 w-6 rounded-full text-xs font-bold ${readinessGrade(c.readiness_score).color}`}>
                                        {readinessGrade(c.readiness_score).letter}
                                    </span>
                                ) : (
                                    <span className="text-xs text-muted-foreground">—</span>
                                )}
                            </TableCell>
                            <TableCell className="text-right text-muted-foreground text-sm hidden sm:table-cell">
                                {formatDate(c.last_updated)}
                            </TableCell>
                            {onDelete && (
                                <TableCell>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onDelete(c);
                                        }}
                                    >
                                        ✕
                                    </Button>
                                </TableCell>
                            )}
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </div>
    );
}

