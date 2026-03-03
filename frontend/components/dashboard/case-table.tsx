// ---- Case Table ---------------------------------------------------------
"use client";

import type { CaseItem } from "@/hooks/use-cases";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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

function formatDate(iso: string): string {
    if (!iso) return "—";
    try {
        return new Date(iso).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    } catch {
        return iso;
    }
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
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-16">
                <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-4 text-xl">
                    ⚖️
                </div>
                <p className="text-lg font-medium">No cases found</p>
                <p className="text-sm text-muted-foreground mt-1 max-w-sm text-center">
                    Create your first case to start managing your legal practice with AI-powered analysis.
                </p>
            </div>
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
                        <TableHead className="font-semibold text-right hidden sm:table-cell">Updated</TableHead>
                        {onDelete && <TableHead className="w-10" />}
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {cases.map((c) => (
                        <TableRow
                            key={c.id}
                            onClick={() => onRowClick(c)}
                            className="cursor-pointer transition-colors hover:bg-accent/50 group"
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

