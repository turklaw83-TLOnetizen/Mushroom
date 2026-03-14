// ---- Case Shell Layout --------------------------------------------------
// Shared layout for all case pages. Shows case header + tab navigation.
// Wraps children in PrepProvider. Supports tab prefetching on hover.
"use client";

import { useState, useRef, useEffect } from "react";
import { useParams, usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { z } from "zod";
import { useCase } from "@/hooks/use-cases";
import { PrepProvider, usePrep } from "@/hooks/use-prep";
import { useCreatePrep } from "@/hooks/use-create-prep";
import { useTabPrefetch } from "@/hooks/use-tab-prefetch";
import { useTabPersistence } from "@/hooks/use-tab-persistence";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { ScrollableTabs, type TabGroup } from "@/components/shared/scrollable-tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

// Primary tabs — always visible in the tab bar
const primaryTabs = [
    { label: "Overview", href: "" },
    { label: "Files", href: "/files" },
    { label: "Analysis", href: "/analysis" },
    { label: "Documents", href: "/documents" },
    { label: "Witnesses", href: "/witnesses" },
    { label: "Evidence", href: "/evidence" },
    { label: "Strategy", href: "/strategy" },
];

// Grouped tabs — appear as dropdown menus in the tab bar
const tabGroups: TabGroup[] = [
    {
        label: "Practice & Testing",
        tabs: [
            { label: "Mock Exam", href: "/mock-exam" },
            { label: "War Game", href: "/war-game" },
            { label: "Ask Case", href: "/ask" },
            { label: "Command Center", href: "/command-center" },
            { label: "Case Score", href: "/predictive-score" },
        ],
    },
    {
        label: "Research & Discovery",
        tabs: [
            { label: "Research", href: "/research" },
            { label: "Discovery", href: "/discovery" },
            { label: "Timeline", href: "/timeline" },
            { label: "Contradictions", href: "/contradictions" },
            { label: "Transcription", href: "/transcription" },
            { label: "Redaction", href: "/redaction" },
        ],
    },
    {
        label: "Admin & Compliance",
        tabs: [
            { label: "Billing", href: "/billing" },
            { label: "Calendar", href: "/calendar" },
            { label: "Compliance", href: "/compliance" },
            { label: "Exhibits", href: "/exhibits" },
            { label: "E-Sign", href: "/esign" },
            { label: "Exports", href: "/exports" },
            { label: "Activity", href: "/activity" },
        ],
    },
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
            { value: "general", label: "General Analysis" },
            { value: "trial", label: "Trial Preparation" },
            { value: "prelim_hearing", label: "Preliminary Hearing" },
            { value: "motion_hearing", label: "Motion Hearing" },
        ],
    },
    { name: "name", label: "Name (optional)", placeholder: "e.g. Suppression Hearing" },
];

function phaseColors(phase: string): string {
    switch (phase?.toLowerCase()) {
        case "active": return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
        case "closed": return "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";
        case "archived": return "bg-amber-500/15 text-amber-400 border-amber-500/30";
        case "purged": return "bg-red-500/15 text-red-400 border-red-500/30";
        default: return "bg-blue-500/15 text-blue-400 border-blue-500/30";
    }
}

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
    const [isScrolled, setIsScrolled] = useState(false);
    const contentRef = useRef<HTMLDivElement>(null);

    const basePath = `/cases/${caseId}`;

    // Restore last-visited tab on case root and persist tab changes
    useTabPersistence(caseId);

    // Track whether content area has scrolled for header shadow effect
    useEffect(() => {
        const el = contentRef.current;
        if (!el) return;
        const onScroll = () => setIsScrolled(el.scrollTop > 8);
        el.addEventListener("scroll", onScroll, { passive: true });
        return () => el.removeEventListener("scroll", onScroll);
    }, []);

    const handleCreatePrep = async (data: PrepInput) => {
        await createPrep.mutateAsync(data);
        setPrepDialogOpen(false);
    };

    return (
        <div className="flex flex-col h-full">
            {/* Case Header — gains shadow when content scrolls */}
            <div className={cn(
                "border-b border-border bg-card/50 px-6 pt-5 pb-0 transition-shadow",
                isScrolled && "shadow-md",
            )}>
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
                            <Badge variant="outline" className={phaseColors(caseData.phase)}>
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
                                    <Select
                                        value={activePrepId || ""}
                                        onValueChange={setActivePrepId}
                                    >
                                        <SelectTrigger className="h-7 text-xs w-auto min-w-[140px]">
                                            <SelectValue placeholder="Select prep" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {preparations.map((p) => (
                                                <SelectItem key={p.id} value={p.id} className="text-xs">
                                                    {p.name || p.type}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                ) : (
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        className="h-7 text-xs border-dashed border-amber-500/40 text-amber-400 hover:bg-amber-500/10"
                                        onClick={() => setPrepDialogOpen(true)}
                                    >
                                        Create Preparation to Start
                                    </Button>
                                )}
                                {preparations.length > 0 && (
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-6 text-xs px-2"
                                        onClick={() => setPrepDialogOpen(true)}
                                    >
                                        + Prep
                                    </Button>
                                )}
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="pb-4">
                        <p className="text-sm text-destructive">Case not found</p>
                    </div>
                )}

                {/* Tab Navigation — scrollable with arrow indicators */}
                <ScrollableTabs
                    tabs={primaryTabs}
                    groups={tabGroups}
                    basePath={basePath}
                    activeHref={pathname}
                    onPrefetch={prefetch}
                />
            </div>

            {/* Tab Content — page-enter animation on route change */}
            <div ref={contentRef} key={pathname} className="flex-1 overflow-y-auto p-6 page-enter">{children}</div>

            {/* Prep Creation Dialog */}
            <FormDialog
                open={prepDialogOpen}
                onOpenChange={setPrepDialogOpen}
                title="New Preparation"
                description="Create a preparation to organize your case analysis. General Analysis runs all modules."
                schema={prepSchema}
                defaultValues={{ type: "general", name: "" }}
                fields={prepFields}
                onSubmit={handleCreatePrep}
                submitLabel="Create Prep"
                isLoading={createPrep.isPending}
            />
        </div>
    );
}
