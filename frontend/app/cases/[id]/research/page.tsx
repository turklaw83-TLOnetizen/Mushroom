// ---- Research Tab (updated to use PrepProvider) -------------------------
"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { usePrep } from "@/hooks/use-prep";
import { DataPage } from "@/components/shared/data-page";
import { Card, CardContent } from "@/components/ui/card";

interface ResearchItem {
    topic: string;
    summary: string;
    source: string;
    citations: string[];
}

export default function ResearchPage() {
    const params = useParams();
    const caseId = params.id as string;
    const { getToken } = useAuth();
    const { activePrepId, isLoading: prepLoading } = usePrep();

    const query = useQuery({
        queryKey: ["research", caseId, activePrepId],
        queryFn: () =>
            api.get<ResearchItem[]>(`/documents/research/${caseId}/${activePrepId}`, { getToken }),
        enabled: !!activePrepId,
    });

    if (!activePrepId && !prepLoading) {
        return (
            <div className="text-center py-16">
                <p className="text-muted-foreground">Create a preparation first to view research.</p>
            </div>
        );
    }

    return (
        <DataPage
            title="Legal Research"
            subtitle="Research data, case law, and citations"
            query={query}
            searchFilter={(r, s) =>
                r.topic?.toLowerCase().includes(s) || r.summary?.toLowerCase().includes(s)
            }
            searchPlaceholder="Search research..."
            createLabel={null}
            renderItem={(item, i) => (
                <Card key={i} className="hover:bg-accent/30 transition-colors">
                    <CardContent className="py-3">
                        <p className="font-medium text-sm">{item.topic || `Research Item ${i + 1}`}</p>
                        {item.summary && (
                            <p className="text-xs text-muted-foreground mt-1 line-clamp-3">{item.summary}</p>
                        )}
                        {item.source && (
                            <p className="text-xs text-muted-foreground mt-1">Source: {item.source}</p>
                        )}
                    </CardContent>
                </Card>
            )}
        />
    );
}
