// ---- Exhibits Page (case subtab) ----------------------------------------
// Exhibits list and Bates number management.
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface ExhibitItem {
    id: string;
    label: string;
    file_key: string;
    description: string;
    assigned_at?: string;
}

interface BatesItem {
    id: string;
    file_key: string;
    prefix: string;
    start_number: number;
    end_number: number;
    range: string;
    assigned_at?: string;
}

interface ExhibitsResponse {
    items: ExhibitItem[];
}

interface BatesResponse {
    items: BatesItem[];
}

export default function ExhibitsPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    const [showAssignExhibits, setShowAssignExhibits] = useState(false);
    const [showAssignBates, setShowAssignBates] = useState(false);
    const [exhibitFileKeys, setExhibitFileKeys] = useState("");
    const [batesFileKeys, setBatesFileKeys] = useState("");
    const [batesPrefix, setBatesPrefix] = useState("");
    const [batesStartNumber, setBatesStartNumber] = useState("");

    // Fetch exhibits
    const exhibitsQuery = useQuery({
        queryKey: ["exhibits", caseId],
        queryFn: () =>
            api.get<ExhibitsResponse>(`/cases/${caseId}/exhibits`, { getToken }),
    });

    // Fetch bates numbers
    const batesQuery = useQuery({
        queryKey: ["bates", caseId],
        queryFn: () =>
            api.get<BatesResponse>(`/cases/${caseId}/exhibits/bates`, { getToken }),
    });

    // Assign exhibits mutation
    const assignExhibits = useMutation({
        mutationFn: (fileKeys: string[]) =>
            api.post(`/cases/${caseId}/exhibits/assign`, { file_keys: fileKeys }, { getToken }),
        onSuccess: () => {
            toast.success("Exhibits assigned");
            queryClient.invalidateQueries({ queryKey: ["exhibits", caseId] });
            setShowAssignExhibits(false);
            setExhibitFileKeys("");
        },
        onError: (err) => {
            toast.error("Failed to assign exhibits", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        },
    });

    // Assign bates mutation
    const assignBates = useMutation({
        mutationFn: (body: { file_keys: string[]; prefix: string; start_number: number | null }) =>
            api.post(`/cases/${caseId}/exhibits/bates/assign`, body, { getToken }),
        onSuccess: () => {
            toast.success("Bates numbers assigned");
            queryClient.invalidateQueries({ queryKey: ["bates", caseId] });
            setShowAssignBates(false);
            setBatesFileKeys("");
            setBatesPrefix("");
            setBatesStartNumber("");
        },
        onError: (err) => {
            toast.error("Failed to assign Bates numbers", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        },
    });

    const exhibits = exhibitsQuery.data?.items ?? [];
    const batesItems = batesQuery.data?.items ?? [];

    const handleAssignExhibits = () => {
        const keys = exhibitFileKeys
            .split(",")
            .map((k) => k.trim())
            .filter(Boolean);
        if (keys.length === 0) {
            toast.error("Enter at least one file key");
            return;
        }
        assignExhibits.mutate(keys);
    };

    const handleAssignBates = () => {
        const keys = batesFileKeys
            .split(",")
            .map((k) => k.trim())
            .filter(Boolean);
        if (keys.length === 0) {
            toast.error("Enter at least one file key");
            return;
        }
        const startNum = batesStartNumber ? parseInt(batesStartNumber, 10) : null;
        assignBates.mutate({ file_keys: keys, prefix: batesPrefix, start_number: startNum });
    };

    return (
        <div className="space-y-5">
            <div>
                <h2 className="text-xl font-bold tracking-tight">Exhibits</h2>
                <p className="text-sm text-muted-foreground mt-0.5">
                    Exhibit assignments and Bates numbering
                </p>
            </div>

            <Tabs defaultValue="exhibits">
                <TabsList>
                    <TabsTrigger value="exhibits">
                        Exhibits
                        {exhibits.length > 0 && (
                            <Badge variant="secondary" className="ml-1.5 text-[10px]">
                                {exhibits.length}
                            </Badge>
                        )}
                    </TabsTrigger>
                    <TabsTrigger value="bates">
                        Bates Numbers
                        {batesItems.length > 0 && (
                            <Badge variant="secondary" className="ml-1.5 text-[10px]">
                                {batesItems.length}
                            </Badge>
                        )}
                    </TabsTrigger>
                </TabsList>

                {/* ---- Exhibits Tab ---- */}
                <TabsContent value="exhibits" className="space-y-4 mt-4">
                    <div className="flex justify-end">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setShowAssignExhibits(!showAssignExhibits)}
                        >
                            {showAssignExhibits ? "Cancel" : "Assign Exhibits"}
                        </Button>
                    </div>

                    {/* Inline assign form */}
                    {showAssignExhibits && (
                        <Card>
                            <CardContent className="py-4 space-y-3">
                                <p className="text-sm font-medium">Assign Exhibits</p>
                                <Input
                                    placeholder="File keys (comma-separated)"
                                    value={exhibitFileKeys}
                                    onChange={(e) => setExhibitFileKeys(e.target.value)}
                                />
                                <div className="flex justify-end">
                                    <Button
                                        size="sm"
                                        onClick={handleAssignExhibits}
                                        disabled={assignExhibits.isPending || !exhibitFileKeys.trim()}
                                    >
                                        {assignExhibits.isPending ? "Assigning..." : "Assign"}
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {exhibitsQuery.isLoading ? (
                        <div className="space-y-3">
                            {Array.from({ length: 4 }).map((_, i) => (
                                <Skeleton key={i} className="h-16 w-full rounded-lg" />
                            ))}
                        </div>
                    ) : exhibits.length === 0 ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No exhibits assigned yet.
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="space-y-2">
                            {exhibits.map((exhibit) => (
                                <Card key={exhibit.id} className="hover:bg-accent/20 transition-colors">
                                    <CardContent className="py-3">
                                        <div className="flex items-center justify-between">
                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <Badge variant="outline" className="text-xs font-mono">
                                                        {exhibit.label}
                                                    </Badge>
                                                    <p className="text-sm font-medium">{exhibit.file_key}</p>
                                                </div>
                                                {exhibit.description && (
                                                    <p className="text-xs text-muted-foreground mt-1 ml-0.5">
                                                        {exhibit.description}
                                                    </p>
                                                )}
                                            </div>
                                            {exhibit.assigned_at && (
                                                <span className="text-xs text-muted-foreground whitespace-nowrap">
                                                    {new Date(exhibit.assigned_at).toLocaleDateString()}
                                                </span>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </TabsContent>

                {/* ---- Bates Numbers Tab ---- */}
                <TabsContent value="bates" className="space-y-4 mt-4">
                    <div className="flex justify-end">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setShowAssignBates(!showAssignBates)}
                        >
                            {showAssignBates ? "Cancel" : "Assign Bates"}
                        </Button>
                    </div>

                    {/* Inline assign form */}
                    {showAssignBates && (
                        <Card>
                            <CardContent className="py-4 space-y-3">
                                <p className="text-sm font-medium">Assign Bates Numbers</p>
                                <Input
                                    placeholder="File keys (comma-separated)"
                                    value={batesFileKeys}
                                    onChange={(e) => setBatesFileKeys(e.target.value)}
                                />
                                <div className="grid grid-cols-2 gap-3">
                                    <Input
                                        placeholder="Prefix (e.g. DEF)"
                                        value={batesPrefix}
                                        onChange={(e) => setBatesPrefix(e.target.value)}
                                    />
                                    <Input
                                        placeholder="Start number (optional)"
                                        type="number"
                                        value={batesStartNumber}
                                        onChange={(e) => setBatesStartNumber(e.target.value)}
                                    />
                                </div>
                                <div className="flex justify-end">
                                    <Button
                                        size="sm"
                                        onClick={handleAssignBates}
                                        disabled={assignBates.isPending || !batesFileKeys.trim()}
                                    >
                                        {assignBates.isPending ? "Assigning..." : "Assign Bates"}
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {batesQuery.isLoading ? (
                        <div className="space-y-3">
                            {Array.from({ length: 4 }).map((_, i) => (
                                <Skeleton key={i} className="h-16 w-full rounded-lg" />
                            ))}
                        </div>
                    ) : batesItems.length === 0 ? (
                        <Card className="border-dashed">
                            <CardContent className="py-12 text-center text-muted-foreground">
                                No Bates numbers assigned yet.
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="space-y-2">
                            {batesItems.map((bates) => (
                                <Card key={bates.id} className="hover:bg-accent/20 transition-colors">
                                    <CardContent className="py-3">
                                        <div className="flex items-center justify-between">
                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <Badge variant="outline" className="text-xs font-mono">
                                                        {bates.range || `${bates.prefix}${bates.start_number}-${bates.end_number}`}
                                                    </Badge>
                                                    <p className="text-sm font-medium">{bates.file_key}</p>
                                                </div>
                                                {bates.prefix && (
                                                    <p className="text-xs text-muted-foreground mt-1 ml-0.5">
                                                        Prefix: {bates.prefix}
                                                    </p>
                                                )}
                                            </div>
                                            {bates.assigned_at && (
                                                <span className="text-xs text-muted-foreground whitespace-nowrap">
                                                    {new Date(bates.assigned_at).toLocaleDateString()}
                                                </span>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </TabsContent>
            </Tabs>
        </div>
    );
}
