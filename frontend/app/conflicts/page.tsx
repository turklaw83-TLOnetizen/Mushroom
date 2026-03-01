// ---- Conflict Check Page ------------------------------------------------
// Search for conflicts of interest before taking new clients/cases.
"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

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
                        {check.isPending ? "Checking..." : "🔍 Run Conflict Check"}
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
                                ✅ No conflicts found. Clear to proceed.
                            </p>
                        ) : (
                            <div className="space-y-3">
                                <p className={`text-sm font-medium ${severityColor[result.severity as keyof typeof severityColor] || ""}`}>
                                    ⚠️ {result.matches.length} potential conflict{result.matches.length > 1 ? "s" : ""} found
                                </p>
                                {result.matches.map((m, i) => (
                                    <div key={i} className="border rounded-md p-3 space-y-1">
                                        <p className="text-sm font-medium">{m.name}</p>
                                        <div className="flex gap-2 flex-wrap">
                                            <Badge variant="outline" className="text-[10px]">
                                                {m.source.replace("_", " ")}
                                            </Badge>
                                            <Badge variant="outline" className="text-[10px]">
                                                match: {m.match_type}
                                            </Badge>
                                            {m.alias && (
                                                <Badge variant="outline" className="text-[10px]">
                                                    via alias: {m.alias}
                                                </Badge>
                                            )}
                                        </div>
                                        {m.cases && m.cases.length > 0 && (
                                            <p className="text-xs text-muted-foreground">
                                                Linked to {m.cases.length} case(s)
                                            </p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
