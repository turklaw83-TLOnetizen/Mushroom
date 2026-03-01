// ---- Case Overview Page -------------------------------------------------
"use client";

import { useParams } from "next/navigation";
import { useCase } from "@/hooks/use-cases";
import { ExportPanel } from "@/components/export-panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function CaseOverviewPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { data: caseData, isLoading } = useCase(caseId);

    if (isLoading) {
        return (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-32 rounded-lg" />
                ))}
            </div>
        );
    }

    if (!caseData) {
        return (
            <div className="text-center py-16 text-muted-foreground">
                Case not found.
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Metadata Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <MetricCard label="Type" value={caseData.case_type || "—"} />
                <MetricCard label="Category" value={caseData.case_category || "—"} />
                <MetricCard label="Client" value={caseData.client_name || "—"} />
                <MetricCard label="Jurisdiction" value={caseData.jurisdiction || "—"} />
                <MetricCard label="Phase" value={`${caseData.phase}${caseData.sub_phase ? ` / ${caseData.sub_phase}` : ""}`} />
                <MetricCard label="Status" value={caseData.status || "active"} />
            </div>

            {/* Description */}
            {caseData.description && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Description</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                            {caseData.description}
                        </p>
                    </CardContent>
                </Card>
            )}

            {/* Export Panel */}
            <ExportPanel caseId={caseId} />
        </div>
    );
}

function MetricCard({ label, value }: { label: string; value: string }) {
    return (
        <Card>
            <CardContent className="pt-4 pb-3">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    {label}
                </p>
                <p className="text-lg font-semibold mt-1 truncate">{value}</p>
            </CardContent>
        </Card>
    );
}
