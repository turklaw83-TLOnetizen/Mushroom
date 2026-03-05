// ---- CRM Page -----------------------------------------------------------
// Client management: list clients, link to cases, intake forms.
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import { api } from "@/lib/api-client";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { RepAgreementSection } from "@/components/crm/rep-agreement-section";
import type { Client } from "@/types/api";

// ---- Form Schema --------------------------------------------------------

const clientSchema = z.object({
    name: z.string().min(1, "Name is required").max(200),
    email: z.string().email("Invalid email").max(320).or(z.literal("")).optional().default(""),
    phone: z.string().max(30).optional().default(""),
    company: z.string().max(200).optional().default(""),
});
type ClientInput = z.infer<typeof clientSchema>;

const clientFields: FieldConfig<ClientInput>[] = [
    { name: "name", label: "Full Name", required: true, placeholder: "e.g. John Smith" },
    { name: "email", label: "Email", placeholder: "e.g. john@example.com" },
    { name: "phone", label: "Phone", placeholder: "e.g. (555) 123-4567" },
    { name: "company", label: "Company", placeholder: "e.g. Smith & Associates" },
];

export default function CRMPage() {
    const { getToken } = useAuth();
    const [search, setSearch] = useState("");
    const [addOpen, setAddOpen] = useState(false);

    const { data, isLoading, error } = useQuery({
        queryKey: ["crm-clients"],
        queryFn: () => api.get<{ items: Client[] }>("/crm/clients", { getToken }),
    });

    const addClient = useMutationWithToast<ClientInput>({
        mutationFn: (input) => api.post("/crm/clients", input, { getToken }),
        successMessage: "Client added",
        invalidateKeys: [["crm-clients"]],
        onSuccess: () => setAddOpen(false),
    });

    const clients = data?.items ?? [];
    const filtered = search
        ? clients.filter((c) =>
            c.name?.toLowerCase().includes(search.toLowerCase()) ||
            c.email?.toLowerCase().includes(search.toLowerCase()) ||
            c.company?.toLowerCase().includes(search.toLowerCase()),
        )
        : clients;

    return (
        <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Clients</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        {clients.length} total clients
                    </p>
                </div>
                <Button onClick={() => setAddOpen(true)} className="gap-2">
                    <span aria-hidden="true">+</span> Add Client
                </Button>
            </div>

            <Input
                placeholder="Search by name, email, or company..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="max-w-md"
            />

            {isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 5 }).map((_, i) => (
                        <Skeleton key={i} className="h-20 w-full rounded-lg" />
                    ))}
                </div>
            ) : error ? (
                <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
                    Failed to load clients: {error instanceof Error ? error.message : "Unknown error"}
                </div>
            ) : filtered.length === 0 ? (
                <Card>
                    <CardContent className="py-12 text-center text-muted-foreground">
                        {search ? "No clients match your search" : "No clients yet — add your first client"}
                    </CardContent>
                </Card>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filtered.map((client) => (
                        <Card key={client.id} className="hover:border-primary/30 transition-colors">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium">{client.name}</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-1">
                                {client.email && (
                                    <p className="text-xs text-muted-foreground">
                                        <span aria-hidden="true">📧 </span>{client.email}
                                    </p>
                                )}
                                {client.phone && (
                                    <p className="text-xs text-muted-foreground">
                                        <span aria-hidden="true">📞 </span>{client.phone}
                                    </p>
                                )}
                                {client.company && (
                                    <p className="text-xs text-muted-foreground">
                                        <span aria-hidden="true">🏢 </span>{client.company}
                                    </p>
                                )}
                                {client.cases?.length > 0 && (
                                    <div className="flex gap-1 mt-2 flex-wrap">
                                        {client.cases.map((caseId) => (
                                            <Badge key={caseId} variant="outline" className="text-[10px]">
                                                {caseId.slice(0, 8)}
                                            </Badge>
                                        ))}
                                    </div>
                                )}
                                <RepAgreementSection
                                    clientId={client.id}
                                    agreement={client.rep_agreement ?? null}
                                />
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Add Client Dialog */}
            <FormDialog
                open={addOpen}
                onOpenChange={setAddOpen}
                title="Add Client"
                description="Add a new client to your directory."
                schema={clientSchema}
                defaultValues={{ name: "", email: "", phone: "", company: "" }}
                fields={clientFields}
                onSubmit={async (data) => { await addClient.mutateAsync(data); }}
                submitLabel="Add Client"
                isLoading={addClient.isPending}
            />
        </div>
    );
}
