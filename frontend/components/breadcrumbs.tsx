// ---- Breadcrumbs --------------------------------------------------------
// Dashboard > Case Name > Tab navigation breadcrumbs.
"use client";

import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import { useCase } from "@/hooks/use-cases";
import { usePageTitle } from "@/hooks/use-page-title";
import { cn } from "@/lib/utils";

const tabLabels: Record<string, string> = {
    // Primary tabs
    files: "Files",
    analysis: "Analysis",
    witnesses: "Witnesses",
    evidence: "Evidence",
    strategy: "Strategy",
    documents: "Documents",
    overview: "Overview",
    // Practice & Testing
    "mock-exam": "Mock Exam",
    "war-game": "War Game",
    "ask-case": "Ask Case",
    "command-center": "Command Center",
    "case-score": "Case Score",
    // Research & Discovery
    research: "Research",
    discovery: "Discovery",
    timeline: "Timeline",
    contradictions: "Contradictions",
    transcription: "Transcription",
    redaction: "Redaction",
    // Admin & Compliance
    billing: "Billing",
    calendar: "Calendar",
    compliance: "Compliance",
    exhibits: "Exhibits",
    esign: "E-Sign",
    exports: "Exports",
    activity: "Activity",
};

const subPageLabels: Record<string, string> = {
    compare: "Compare",
    report: "Battle Report",
    versions: "Versions",
    new: "New",
    edit: "Edit",
};

export function Breadcrumbs() {
    const pathname = usePathname();
    const params = useParams();
    const caseId = params.id as string | undefined;
    const { data: caseData } = useCase(caseId || "");

    // Update document.title dynamically
    usePageTitle();

    // Don't show on dashboard
    if (pathname === "/") return null;
    // Don't show on auth pages
    if (pathname.startsWith("/sign-")) return null;

    const segments: { label: string; href: string }[] = [
        { label: "Dashboard", href: "/" },
    ];

    if (caseId) {
        segments.push({
            label: caseData?.name || "Case",
            href: `/cases/${caseId}`,
        });

        // Extract tab name
        const parts = pathname.split("/");
        const tabSlug = parts[3]; // /cases/[id]/[tab]
        if (tabSlug && tabLabels[tabSlug]) {
            segments.push({
                label: tabLabels[tabSlug],
                href: `/cases/${caseId}/${tabSlug}`,
            });
        }

        // Extract sub-page (4th segment)
        const subPage = parts[4]; // /cases/[id]/[tab]/[subpage]
        if (subPage && subPageLabels[subPage]) {
            segments.push({
                label: subPageLabels[subPage],
                href: `/cases/${caseId}/${tabSlug}/${subPage}`,
            });
        }
    }

    // On mobile (< 640px), collapse middle segments when 4+ segments
    const shouldCollapse = segments.length > 3;

    return (
        <nav className="flex items-center gap-1.5 text-xs text-muted-foreground px-6 pt-3 pb-0 min-w-0">
            {segments.map((seg, i) => {
                // On mobile, hide middle segments (keep first, last 2)
                const isMiddle = shouldCollapse && i > 0 && i < segments.length - 2;
                const isEllipsis = shouldCollapse && i === 1; // Show ellipsis in place of first hidden

                return (
                    <span
                        key={seg.href}
                        className={cn(
                            "flex items-center gap-1.5",
                            isMiddle && !isEllipsis && "hidden sm:flex",
                        )}
                    >
                        {i > 0 && (
                            <span
                                className={cn(
                                    "text-border",
                                    isMiddle && !isEllipsis && "hidden sm:inline",
                                )}
                            >
                                /
                            </span>
                        )}
                        {isEllipsis && (
                            <span className="sm:hidden flex items-center gap-1.5">
                                <span className="text-border">/</span>
                                <span>&hellip;</span>
                            </span>
                        )}
                        {i === segments.length - 1 ? (
                            <span
                                className={cn(
                                    "text-foreground font-medium truncate max-w-[200px]",
                                    isMiddle && "hidden sm:inline",
                                )}
                            >
                                {seg.label}
                            </span>
                        ) : (
                            <Link
                                href={seg.href}
                                className={cn(
                                    "hover:text-foreground transition-colors truncate max-w-[200px]",
                                    isMiddle && "hidden sm:inline",
                                )}
                            >
                                {seg.label}
                            </Link>
                        )}
                    </span>
                );
            })}
        </nav>
    );
}
