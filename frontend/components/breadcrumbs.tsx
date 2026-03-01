// ---- Breadcrumbs --------------------------------------------------------
// Dashboard > Case Name > Tab navigation breadcrumbs.
"use client";

import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import { useCase } from "@/hooks/use-cases";
import { usePageTitle } from "@/hooks/use-page-title";

const tabLabels: Record<string, string> = {
    files: "Files",
    analysis: "Analysis",
    witnesses: "Witnesses",
    evidence: "Evidence",
    strategy: "Strategy",
    documents: "Documents",
    research: "Research",
    billing: "Billing",
    calendar: "Calendar",
    compliance: "Compliance",
    activity: "Activity",
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
    }

    return (
        <nav className="flex items-center gap-1.5 text-xs text-muted-foreground px-6 pt-3 pb-0">
            {segments.map((seg, i) => (
                <span key={seg.href} className="flex items-center gap-1.5">
                    {i > 0 && <span className="text-border">/</span>}
                    {i === segments.length - 1 ? (
                        <span className="text-foreground font-medium">{seg.label}</span>
                    ) : (
                        <Link
                            href={seg.href}
                            className="hover:text-foreground transition-colors"
                        >
                            {seg.label}
                        </Link>
                    )}
                </span>
            ))}
        </nav>
    );
}
