// ---- Session Cost Widget -------------------------------------------------
// Collapsible sidebar panel showing API token usage and estimated cost.
"use client";

import { useState } from "react";
import { useSessionCostStore, type CostEntry } from "@/lib/stores/session-cost-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

// ---- Helpers ------------------------------------------------------------

function formatTokens(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return String(n);
}

function formatCost(c: number): string {
    return `$${c.toFixed(4)}`;
}

function formatTime(ts: number): string {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// ---- Component ----------------------------------------------------------

export function SessionCostWidget() {
    const [expanded, setExpanded] = useState(false);
    const totalTokens = useSessionCostStore((s) => s.totalTokens);
    const totalCost = useSessionCostStore((s) => s.totalCost);
    const entries = useSessionCostStore((s) => s.entries);
    const reset = useSessionCostStore((s) => s.reset);

    // Nothing to show if no usage recorded
    if (totalTokens === 0 && entries.length === 0) return null;

    // Show last 20 entries, newest first
    const recentEntries = entries.slice(-20).reverse();

    return (
        <div className="px-3 pb-2">
            <Separator className="mb-2" />

            {/* Collapsed summary row */}
            <button
                onClick={() => setExpanded((v) => !v)}
                className={cn(
                    "w-full flex items-center gap-2 rounded-md px-2 py-1.5 text-xs transition-colors",
                    "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )}
            >
                {/* Token icon */}
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="shrink-0"
                >
                    <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                </svg>

                <span className="flex-1 text-left truncate">
                    {formatTokens(totalTokens)} tokens &middot; {formatCost(totalCost)}
                </span>

                {/* Chevron */}
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className={cn("transition-transform", expanded && "rotate-180")}
                >
                    <path d="m18 15-6-6-6 6" />
                </svg>
            </button>

            {/* Expanded detail panel */}
            {expanded && (
                <div className="mt-1 rounded-md border border-border bg-background/50 overflow-hidden">
                    {/* Header row */}
                    <div className="flex items-center justify-between px-3 py-2 border-b border-border">
                        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                            Session Usage
                        </span>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                                e.stopPropagation();
                                reset();
                                setExpanded(false);
                            }}
                            className="h-6 px-2 text-xs text-muted-foreground hover:text-destructive"
                        >
                            Reset
                        </Button>
                    </div>

                    {/* Totals */}
                    <div className="grid grid-cols-2 gap-2 px-3 py-2 border-b border-border">
                        <div>
                            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
                                Tokens
                            </div>
                            <div className="text-sm font-semibold tabular-nums">
                                {totalTokens.toLocaleString()}
                            </div>
                        </div>
                        <div>
                            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
                                Est. Cost
                            </div>
                            <div className="text-sm font-semibold tabular-nums">
                                {formatCost(totalCost)}
                            </div>
                        </div>
                    </div>

                    {/* Recent entries */}
                    {recentEntries.length > 0 && (
                        <div className="max-h-48 overflow-y-auto">
                            <table className="w-full text-[11px]">
                                <thead>
                                    <tr className="border-b border-border text-muted-foreground">
                                        <th className="px-2 py-1 text-left font-medium">Time</th>
                                        <th className="px-2 py-1 text-left font-medium">Endpoint</th>
                                        <th className="px-2 py-1 text-right font-medium">Tokens</th>
                                        <th className="px-2 py-1 text-right font-medium">Cost</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {recentEntries.map((entry: CostEntry, idx: number) => (
                                        <tr
                                            key={`${entry.timestamp}-${idx}`}
                                            className="border-b border-border/50 text-muted-foreground hover:bg-accent/30"
                                        >
                                            <td className="px-2 py-1 tabular-nums">
                                                {formatTime(entry.timestamp)}
                                            </td>
                                            <td className="px-2 py-1 truncate max-w-[80px]" title={entry.endpoint}>
                                                {entry.endpoint}
                                            </td>
                                            <td className="px-2 py-1 text-right tabular-nums">
                                                {formatTokens(entry.tokens)}
                                            </td>
                                            <td className="px-2 py-1 text-right tabular-nums">
                                                {formatCost(entry.cost)}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}

                    {/* Entry count footer */}
                    {entries.length > 20 && (
                        <div className="px-3 py-1 text-[10px] text-muted-foreground text-center border-t border-border">
                            Showing last 20 of {entries.length} entries
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
