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
                <MetricCard label="Type" value={caseData.case_type || "—"} delay={0} />
                <MetricCard label="Category" value={caseData.case_category || "—"} delay={0.06} />
                <MetricCard label="Client" value={caseData.client_name || "—"} delay={0.12} />
                <MetricCard label="Jurisdiction" value={caseData.jurisdiction || "—"} delay={0.18} />
                <MetricCard label="Phase" value={`${caseData.phase}${caseData.sub_phase ? ` / ${caseData.sub_phase}` : ""}`} delay={0.24} />
                <MetricCard label="Status" value={caseData.status || "active"} delay={0.30} />
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

function MetricCard({ label, value, delay = 0 }: { label: string; value: string; delay?: number }) {
    return (
        <div
            className="glass-card px-5 py-4"
            style={{ animationDelay: `${delay}s` }}
        >
            <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                {label}
            </p>
            <p className="text-lg font-semibold mt-1 truncate">{value}</p>
        </div>
    );
}
