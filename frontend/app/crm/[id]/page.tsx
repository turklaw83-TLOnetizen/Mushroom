// ---- Client Detail Page --------------------------------------------------
// Shows client info, rep agreement, payment plan, and linked cases.
"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { z } from "zod";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { FormDialog, type FieldConfig } from "@/components/shared/form-dialog";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { RepAgreementSection } from "@/components/crm/rep-agreement-section";
import { PaymentPlanTab } from "@/components/billing/payment-plan-tab";
import type { Client } from "@/types/api";

// ---- Edit Client Schema -------------------------------------------------

const editClientSchema = z.object({
    name: z.string().min(1, "Name required").max(200),
    email: z.string().email("Invalid email").max(320).or(z.literal("")).optional().default(""),
    phone: z.string().max(30).optional().default(""),
    company: z.string().max(200).optional().default(""),
});
type EditClientInput = z.infer<typeof editClientSchema>;

const editClientFields: FieldConfig<EditClientInput>[] = [
    { name: "name", label: "Full Name", required: true, placeholder: "e.g. John Smith" },
    { name: "email", label: "Email", placeholder: "e.g. john@example.com" },
    { name: "phone", label: "Phone", placeholder: "e.g. (555) 123-4567" },
    { name: "company", label: "Company", placeholder: "e.g. Smith & Associates" },
];

export default function ClientDetailPage() {
    const params = useParams();
    const router = useRouter();
    const clientId = params.id as string;
    const { getToken } = useAuth();
    const { canEdit, canDelete } = useRole();
    const [editOpen, setEditOpen] = useState(false);
    const [deleteOpen, setDeleteOpen] = useState(false);

    const { data: client, isLoading, error } = useQuery({
        queryKey: ["crm-client", clientId],
        queryFn: () => api.get<Client>(`/crm/clients/${clientId}`, { getToken }),
    });

    const linkedCasesQuery = useQuery({
        queryKey: ["crm-client-cases", clientId],
        queryFn: () => api.get<{ case_ids: string[] }>(`/crm/clients/${clientId}/cases`, { getToken }),
    });

    const updateClient = useMutationWithToast<EditClientInput>({
        mutationFn: (data) => api.put(`/crm/clients/${clientId}`, data, { getToken }),
        successMessage: "Client updated",
        invalidateKeys: [["crm-client", clientId], ["crm-clients"]],
        onSuccess: () => setEditOpen(false),
    });

    const deleteClient = useMutationWithToast<void>({
        mutationFn: () => api.delete(`/crm/clients/${clientId}`, { getToken }),
        successMessage: "Client deleted",
        invalidateKeys: [["crm-clients"]],
        onSuccess: () => router.push("/crm"),
    });

    if (isLoading) {
        return (
            <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-6">
                <Skeleton className="h-8 w-48" />
                <Skeleton className="h-24 rounded-lg" />
                <Skeleton className="h-48 rounded-lg" />
                <Skeleton className="h-64 rounded-lg" />
            </div>
        );
    }

    if (error || !client) {
        return (
            <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-4">
                <Button variant="ghost" size="sm" onClick={() => router.push("/crm")}>
                    &larr; Back to Clients
                </Button>
                <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
                    {error instanceof Error ? error.message : "Client not found"}
                </div>
            </div>
        );
    }

    const linkedCases = linkedCasesQuery.data?.case_ids ?? client.cases ?? [];

    return (
        <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-6">
            {/* Back link */}
            <Button variant="ghost" size="sm" onClick={() => router.push("/crm")}>
                &larr; Back to Clients
            </Button>

            {/* Client Header */}
            <div className="flex items-start justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">{client.name}</h1>
                    <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                        {client.email && <span>{client.email}</span>}
                        {client.phone && <span>{client.phone}</span>}
                        {client.company && <span>{client.company}</span>}
                    </div>
                </div>
                {canEdit && (
                    <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
                            Edit
                        </Button>
                        {canDelete && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="text-destructive hover:text-destructive"
                                onClick={() => setDeleteOpen(true)}
                            >
                                Delete
                            </Button>
                        )}
                    </div>
                )}
            </div>

            {/* Client Info Card */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Client Information</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                        <div>
                            <span className="text-muted-foreground text-xs">Name</span>
                            <p className="font-medium">{client.name}</p>
                        </div>
                        <div>
                            <span className="text-muted-foreground text-xs">Email</span>
                            <p className="font-medium">{client.email || "—"}</p>
                        </div>
                        <div>
                            <span className="text-muted-foreground text-xs">Phone</span>
                            <p className="font-medium">{client.phone || "—"}</p>
                        </div>
                        <div>
                            <span className="text-muted-foreground text-xs">Company</span>
                            <p className="font-medium">{client.company || "—"}</p>
                        </div>
                    </div>

                    {/* Linked Cases */}
                    {linkedCases.length > 0 && (
                        <div className="mt-4 pt-4 border-t">
                            <p className="text-muted-foreground text-xs mb-2">Linked Cases</p>
                            <div className="flex gap-2 flex-wrap">
                                {linkedCases.map((caseId) => (
                                    <Badge
                                        key={caseId}
                                        variant="outline"
                                        className="text-xs cursor-pointer hover:bg-accent"
                                        onClick={() => router.push(`/cases/${caseId}`)}
                                    >
                                        {caseId.slice(0, 8)}...
                                    </Badge>
                                ))}
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Rep Agreement */}
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Representation Agreement</CardTitle>
                </CardHeader>
                <CardContent>
                    <RepAgreementSection
                        clientId={clientId}
                        agreement={client.rep_agreement ?? null}
                    />
                </CardContent>
            </Card>

            {/* Payment Plan — the main feature */}
            <div>
                <h2 className="text-lg font-semibold tracking-tight mb-3">Payment Plan</h2>
                <PaymentPlanTab clientId={clientId} clientName={client.name} />
            </div>

            {/* Edit Dialog */}
            {canEdit && (
                <FormDialog
                    open={editOpen}
                    onOpenChange={setEditOpen}
                    title="Edit Client"
                    description="Update client information."
                    schema={editClientSchema}
                    defaultValues={{
                        name: client.name,
                        email: client.email || "",
                        phone: client.phone || "",
                        company: client.company || "",
                    }}
                    fields={editClientFields}
                    onSubmit={(data) => updateClient.mutate(data)}
                    submitLabel="Save Changes"
                    isLoading={updateClient.isPending}
                />
            )}

            {/* Delete Confirm */}
            <ConfirmDialog
                open={deleteOpen}
                onOpenChange={setDeleteOpen}
                title="Delete Client"
                description="This will permanently delete this client and their payment plan. This cannot be undone."
                onConfirm={() => deleteClient.mutate()}
                isLoading={deleteClient.isPending}
            />
        </div>
    );
}
