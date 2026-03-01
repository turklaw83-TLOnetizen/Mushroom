// ---- Dynamic Page Title Hook --------------------------------------------
// Sets the document title based on case name and active tab.
"use client";

import { useEffect } from "react";
import { usePathname, useParams } from "next/navigation";
import { useCase } from "@/hooks/use-cases";

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

const APP_NAME = "Mushroom Cloud";

export function usePageTitle() {
    const pathname = usePathname();
    const params = useParams();
    const caseId = params.id as string | undefined;
    const { data: caseData } = useCase(caseId || "");

    useEffect(() => {
        let title = APP_NAME;

        if (pathname === "/") {
            title = `Dashboard | ${APP_NAME}`;
        } else if (caseId && caseData?.name) {
            const parts = pathname.split("/");
            const tab = parts[3];
            if (tab && tabLabels[tab]) {
                title = `${tabLabels[tab]} - ${caseData.name} | ${APP_NAME}`;
            } else {
                title = `${caseData.name} | ${APP_NAME}`;
            }
        }

        document.title = title;
    }, [pathname, caseId, caseData]);
}
