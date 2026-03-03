// ---- Case Shell Layout --------------------------------------------------
// Shared layout for all case pages. Shows case header + tab navigation.
// Wraps children in PrepProvider. Supports tab prefetching on hover.
"use client";

import { useState } from "react";
import { useParams, usePathname } from "next/navigation";
import Link from "next/link";
import { z } from "zod";
import { useCase } from "@/hooks/use-cases";
import { PrepProvider, usePrep } from "@/hooks/use-prep";
import { useCreatePrep } from "@/hooks/use-create-prep";
import { useTabPrefetch } from "@/hooks/use-tab-prefetch";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const tabs = [
    { label: "Overview", href: "" },
    { label: "Files", href: "/files" },
    { label: "Analysis", href: "/analysis" },
    { label: "Chat", href: "/chat" },
    { label: "Directives", href: "/directives" },
    { label: "Witnesses", href: "/witnesses" },
    { label: "Evidence", href: "/evidence" },
    { label: "Strategy", href: "/strategy" },
    { label: "Timeline", href: "/timeline" },
    { label: "Documents", href: "/documents" },
    { label: "Cards", href: "/cards" },
    { label: "Research", href: "/research" },
    { label: "History", href: "/history" },
    { label: "Billing", href: "/billing" },
    { label: "Calendar", href: "/calendar" },
    { label: "Compliance", href: "/compliance" },
    { label: "Journal", href: "/journal" },
    { label: "Negotiations", href: "/negotiations" },
    { label: "Playbook", href: "/playbook" },
    { label: "E-Sign", href: "/esign" },
    { label: "Transcription", href: "/transcription" },
    { label: "AI Tools", href: "/ai-tools" },
    { label: "Security", href: "/security" },
    { label: "Activity", href: "/activity" },
];

// Prep creation schema
const prepSchema = z.object({
    type: z.string().min(1, "Type is required"),
    name: z.string().max(200).optional().default(""),
});
type PrepInput = z.infer<typeof prepSchema>;

const prepFields: FieldConfig<PrepInput>[] = [
    {
        name: "type",
        label: "Preparation Type",
        type: "select",
        required: true,
        options: [
            { value: "trial", label: "Trial" },
            { value: "hearing", label: "Hearing" },
            { value: "motion", label: "Motion" },
            { value: "deposition", label: "Deposition" },
            { value: "mediation", label: "Mediation" },
        ],
    },
    { name: "name", label: "Name (optional)", placeholder: "e.g. Suppression Hearing" },
];

export default function CaseLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const params = useParams();
    const caseId = params.id as string;

    return (
        <PrepProvider caseId={caseId}>
            <CaseLayoutInner caseId={caseId}>{children}</CaseLayoutInner>
        </PrepProvider>
    );
}

function CaseLayoutInner({
    caseId,
    children,
}: {
    caseId: string;
    children: React.ReactNode;
}) {
    const pathname = usePathname();
    const { data: caseData, isLoading } = useCase(caseId);
    const { preparations, activePrepId, setActivePrepId } = usePrep();
    const prefetch = useTabPrefetch(caseId, activePrepId);
    const createPrep = useCreatePrep(caseId);
    const [prepDialogOpen, setPrepDialogOpen] = useState(false);

    const basePath = `/cases/${caseId}`;

    const handleCreatePrep = async (data: PrepInput) => {
        await createPrep.mutateAsync(data);
        setPrepDialogOpen(false);
    };

    return (
        <div className="flex flex-col h-full">
            {/* Case Header */}
            <div className="border-b border-border bg-card/50 px-6 pt-5 pb-0">
                {isLoading ? (
                    <div className="space-y-2 pb-4">
                        <Skeleton className="h-7 w-64" />
                        <Skeleton className="h-4 w-40" />
                    </div>
                ) : caseData ? (
                    <div className="pb-3">
                        <div className="flex items-center gap-3">
                            <h1 className="text-xl font-bold tracking-tight">
                                {caseData.name}
                            </h1>
                            <Badge
                                variant="outline"
                                className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                            >
                                {caseData.phase}
                            </Badge>
                            {caseData.case_type && (
                                <Badge variant="secondary" className="text-xs">
                                    {caseData.case_type}
                                </Badge>
                            )}
                        </div>
                        <div className="flex items-center gap-3 mt-1">
                            {(caseData.client_name || caseData.case_category) && (
                                <p className="text-sm text-muted-foreground">
                                    {[caseData.client_name, caseData.case_category]
                                        .filter(Boolean)
                                        .join(" · ")}
                                </p>
                            )}
                            {/* Prep selector + create */}
                            <div className="flex items-center gap-1.5">
                                {preparations.length > 0 ? (
                                    <select
                                        value={activePrepId || ""}
                                        onChange={(e) => setActivePrepId(e.target.value)}
                                        className="text-xs bg-muted border border-border rounded px-2 py-0.5"
                                    >
                                        {preparations.map((p) => (
                                            <option key={p.id} value={p.id}>
                                                {p.name || p.type} prep
                                            </option>
                                        ))}
                                    </select>
                                ) : (
                                    <span className="text-xs text-muted-foreground">No preps</span>
                                )}
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-6 text-xs px-2"
                                    onClick={() => setPrepDialogOpen(true)}
                                >
                                    + Prep
                                </Button>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="pb-4">
                        <p className="text-sm text-destructive">Case not found</p>
                    </div>
                )}

                {/* Tab Navigation with prefetch on hover — scrollable on mobile */}
                <div className="relative">
                    <nav
                        className="flex gap-0 -mb-px overflow-x-auto scrollbar-none"
                        style={{
                            maskImage: "linear-gradient(to right, transparent 0, black 24px, black calc(100% - 24px), transparent 100%)",
                            WebkitMaskImage: "linear-gradient(to right, transparent 0, black 24px, black calc(100% - 24px), transparent 100%)",
                        }}
                    >
                        {tabs.map((tab) => {
                            const tabPath = `${basePath}${tab.href}`;
                            const isActive =
                                tab.href === ""
                                    ? pathname === basePath
                                    : pathname.startsWith(tabPath);

                            return (
                                <Link
                                    key={tab.href}
                                    href={tabPath}
                                    onMouseEnter={() => prefetch(tab.href)}
                                    className={cn(
                                        "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap shrink-0",
                                        isActive
                                            ? "border-primary text-primary"
                                            : "border-transparent text-muted-foreground hover:text-foreground hover:border-border",
                                    )}
                                >
                                    {tab.label}
                                </Link>
                            );
                        })}
                    </nav>
                </div>
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-y-auto p-6">{children}</div>

            {/* Prep Creation Dialog */}
            <FormDialog
                open={prepDialogOpen}
                onOpenChange={setPrepDialogOpen}
                title="New Preparation"
                description="Create a preparation for trial, hearing, motion, or other proceeding."
                schema={prepSchema}
                defaultValues={{ type: "trial", name: "" }}
                fields={prepFields}
                onSubmit={handleCreatePrep}
                submitLabel="Create Prep"
                isLoading={createPrep.isPending}
            />
        </div>
    );
}
