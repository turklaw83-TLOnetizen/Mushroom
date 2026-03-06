// ---- Conflict Check Page ------------------------------------------------
// Search for conflicts of interest before taking new clients/cases.
"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ConflictMatch {
    source: string;
    name: string;
    id: string;
    case_id?: string;
    cases?: string[];
    match_type: string; // exact, nickname, fuzzy, initial, partial, substring
    confidence: number; // 0.0-1.0
    explanation: string; // why this matched
    alias?: string;
    severity?: string;
}

interface ConflictResult {
    has_conflict: boolean;
    matches: ConflictMatch[];
    severity: string;
}

const matchTypeColors: Record<string, string> = {
    exact: "bg-red-500/20 text-red-400 border-red-500/30",
    nickname: "bg-red-400/20 text-red-300 border-red-400/30",
    fuzzy: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    initial: "bg-amber-400/20 text-amber-300 border-amber-400/30",
    partial: "bg-orange-500/20 text-orange-400 border-orange-500/30",
    substring: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    name: "bg-gray-500/20 text-gray-400 border-gray-500/30", // legacy fallback
};

function confidenceBarColor(confidence: number): string {
    if (confidence >= 0.8) return "bg-red-500";
    if (confidence >= 0.6) return "bg-amber-500";
    return "bg-blue-500";
}

export default function ConflictsPage() {
    const { getToken } = useAuth();
    const [name, setName] = useState("");
    const [aliases, setAliases] = useState("");

    const check = useMutation({
        mutationFn: () =>
            api.post<ConflictResult>("/conflicts/check", {
                party_name: name,
                aliases: aliases ? aliases.split(",").map((a) => a.trim()) : [],
            }, { getToken }),
    });

    const result = check.data;
    const severityColor = {
        none: "text-green-400",
        potential: "text-amber-400",
        confirmed: "text-red-400",
    };

    // Sort matches by confidence (highest first)
    const sortedMatches = result?.matches
        ? [...result.matches].sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0))
        : [];

    return (
        <div className="p-6 md:p-8 max-w-3xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Conflict Check</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    Search for conflicts of interest before taking a new client or case
                </p>
            </div>

            <Card>
                <CardContent className="pt-6 space-y-4">
                    <div>
                        <label className="text-sm font-medium mb-1.5 block">Party Name *</label>
                        <Input
                            placeholder="e.g. John Smith, Acme Corporation"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                        />
                    </div>
                    <div>
                        <label className="text-sm font-medium mb-1.5 block">Known Aliases</label>
                        <Input
                            placeholder="Comma-separated: J. Smith, Johnny Smith"
                            value={aliases}
                            onChange={(e) => setAliases(e.target.value)}
                        />
                        <p className="text-[10px] text-muted-foreground mt-1">
                            Optional — also search under these alternate names
                        </p>
                    </div>
                    <Button
                        onClick={() => check.mutate()}
                        disabled={!name || check.isPending}
                        className="w-full"
                    >
                        {check.isPending ? "Checking..." : "Run Conflict Check"}
                    </Button>
                </CardContent>
            </Card>

            {result && (
                <Card className={result.has_conflict ? "border-red-500/30" : "border-green-500/30"}>
                    <CardHeader>
                        <CardTitle className="text-base flex items-center gap-2">
                            Result
                            <Badge
                                variant={result.has_conflict ? "destructive" : "default"}
                                className="text-xs"
                            >
                                {result.severity.toUpperCase()}
                            </Badge>
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {!result.has_conflict ? (
                            <p className="text-sm text-green-400">
                                No conflicts found. Clear to proceed.
                            </p>
                        ) : (
                            <div className="space-y-3">
                                <p className={`text-sm font-medium ${severityColor[result.severity as keyof typeof severityColor] || ""}`}>
                                    {sortedMatches.length} potential conflict{sortedMatches.length > 1 ? "s" : ""} found
                                </p>
                                {sortedMatches.map((m, i) => (
                                    <div key={i} className="border rounded-md p-3 space-y-2">
                                        <div className="flex items-center justify-between">
                                            <p className="text-sm font-medium">{m.name}</p>
                                            {m.severity && (
                                                <Badge
                                                    variant="outline"
                                                    className={cn(
                                                        "text-[10px]",
                                                        m.severity === "confirmed"
                                                            ? "border-red-500/40 text-red-400"
                                                            : m.severity === "potential"
                                                              ? "border-amber-500/40 text-amber-400"
                                                              : ""
                                                    )}
                                                >
                                                    {m.severity}
                                                </Badge>
                                            )}
                                        </div>
                                        <div className="flex gap-2 flex-wrap">
                                            <Badge variant="outline" className="text-[10px]">
                                                {m.source.replace("_", " ")}
                                            </Badge>
                                            <Badge
                                                variant="outline"
                                                className={cn(
                                                    "text-[10px] border",
                                                    matchTypeColors[m.match_type] || matchTypeColors.name
                                                )}
                                            >
                                                {m.match_type}
                                            </Badge>
                                            {m.alias && (
                                                <Badge variant="outline" className="text-[10px]">
                                                    via alias: {m.alias}
                                                </Badge>
                                            )}
                                        </div>
                                        {/* Confidence bar */}
                                        {m.confidence != null && (
                                            <div className="space-y-1">
                                                <div className="w-full bg-muted rounded-full h-2">
                                                    <div
                                                        className={cn(
                                                            "h-2 rounded-full transition-all",
                                                            confidenceBarColor(m.confidence)
                                                        )}
                                                        style={{ width: `${Math.round(m.confidence * 100)}%` }}
                                                    />
                                                </div>
                                                <span className="text-xs text-muted-foreground">
                                                    {Math.round(m.confidence * 100)}% confidence
                                                </span>
                                            </div>
                                        )}
                                        {/* Explanation */}
                                        {m.explanation && (
                                            <p className="text-xs text-muted-foreground italic">
                                                {m.explanation}
                                            </p>
                                        )}
                                        {m.cases && m.cases.length > 0 && (
                                            <p className="text-xs text-muted-foreground">
                                                Linked to {m.cases.length} case(s)
                                            </p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                        <div className="text-center pt-4">
                            <Link href="/cases" className="text-sm text-muted-foreground hover:text-primary">
                                For case-specific compliance scanning, open a case &rarr; Compliance tab
                            </Link>
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
