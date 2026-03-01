// ---- CRM Page -----------------------------------------------------------
// Client management: list clients, link to cases, intake forms.
// Detail drawer with status toggle, linked cases, and delete action.
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
    Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetFooter,
} from "@/components/ui/sheet";
import {
    DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
    DropdownMenuLabel, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import {
    AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
    AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

// ---- Types --------------------------------------------------------------

const CLIENT_STATUSES = ["active", "prospective", "former", "declined"] as const;
type ClientStatus = (typeof CLIENT_STATUSES)[number];

interface Client {
    id: string;
    name: string;
    first_name?: string;
    last_name?: string;
    email: string;
    phone: string;
    company?: string;
    cases?: string[];
    linked_case_ids?: string[];
    intake_status?: ClientStatus;
    client_type?: string;
    mailing_address?: string;
    notes?: string;
    referral_source?: string;
    tags?: string[];
    created_at?: string;
    intake_date?: string;
}

// ---- Status helpers -----------------------------------------------------

const STATUS_COLORS: Record<ClientStatus, string> = {
    active: "text-green-400 border-green-500/30 bg-green-500/10",
    prospective: "text-blue-400 border-blue-500/30 bg-blue-500/10",
    former: "text-amber-400 border-amber-500/30 bg-amber-500/10",
    declined: "text-red-400 border-red-500/30 bg-red-500/10",
};

function statusLabel(s?: string): string {
    if (!s) return "Active";
    return s.charAt(0).toUpperCase() + s.slice(1);
}

function clientDisplayName(c: Client): string {
    if (c.first_name || c.last_name) {
        return [c.first_name, c.last_name].filter(Boolean).join(" ");
    }
    return c.name || "Unnamed Client";
}

function clientLinkedCases(c: Client): string[] {
    return c.linked_case_ids ?? c.cases ?? [];
}

// ---- Component ----------------------------------------------------------

export default function CRMPage() {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const router = useRouter();
    const [search, setSearch] = useState("");
    const [addOpen, setAddOpen] = useState(false);
    const [form, setForm] = useState({ name: "", email: "", phone: "", company: "" });

    // Detail drawer state
    const [selectedClient, setSelectedClient] = useState<Client | null>(null);
    // Delete confirm state
    const [deleteTarget, setDeleteTarget] = useState<Client | null>(null);

    // ---- Queries & mutations ----

    const { data, isLoading } = useQuery({
        queryKey: ["crm-clients"],
        queryFn: () => api.get<{ items: Client[] }>("/crm/clients", { getToken }),
    });

    const addClient = useMutation({
        mutationFn: (body: typeof form) => api.post("/crm/clients", body, { getToken }),
        onSuccess: () => {
            toast.success("Client added");
            queryClient.invalidateQueries({ queryKey: ["crm-clients"] });
            setAddOpen(false);
            setForm({ name: "", email: "", phone: "", company: "" });
        },
    });

    const updateStatusMutation = useMutation({
        mutationFn: ({ clientId, status }: { clientId: string; status: string }) =>
            api.put(`/crm/clients/${clientId}`, { intake_status: status }, { getToken }),
        onSuccess: (_data, { status }) => {
            toast.success(`Status changed to ${statusLabel(status)}`);
            queryClient.invalidateQueries({ queryKey: ["crm-clients"] });
            // Update the selected client locally so the drawer reflects the change
            if (selectedClient) {
                setSelectedClient({ ...selectedClient, intake_status: status as ClientStatus });
            }
        },
        onError: (err: Error) => {
            toast.error("Failed to update status", { description: err.message });
        },
    });

    const deleteClientMutation = useMutation({
        mutationFn: (clientId: string) =>
            api.delete(`/crm/clients/${clientId}`, { getToken }),
        onSuccess: () => {
            toast.success("Client deleted");
            queryClient.invalidateQueries({ queryKey: ["crm-clients"] });
            setSelectedClient(null);
            setDeleteTarget(null);
        },
        onError: (err: Error) => {
            toast.error("Failed to delete client", { description: err.message });
        },
    });

    // ---- Derived data ----

    const clients = data?.items ?? [];
    const filtered = search
        ? clients.filter((c) => {
            const q = search.toLowerCase();
            return (
                clientDisplayName(c).toLowerCase().includes(q) ||
                c.email?.toLowerCase().includes(q) ||
                c.company?.toLowerCase().includes(q)
            );
        })
        : clients;

    // ---- Render ----

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
                    <span>+</span> Add Client
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
            ) : filtered.length === 0 ? (
                <Card>
                    <CardContent className="py-12 text-center text-muted-foreground">
                        {search ? "No clients match your search" : "No clients yet -- add your first client"}
                    </CardContent>
                </Card>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filtered.map((client) => {
                        const status = client.intake_status ?? "active";
                        const linked = clientLinkedCases(client);
                        return (
                            <Card
                                key={client.id}
                                className="hover:border-primary/30 transition-colors cursor-pointer"
                                onClick={() => setSelectedClient(client)}
                            >
                                <CardHeader className="pb-2">
                                    <div className="flex items-center justify-between">
                                        <CardTitle className="text-sm font-medium">
                                            {clientDisplayName(client)}
                                        </CardTitle>
                                        <Badge
                                            variant="outline"
                                            className={`text-[10px] ${STATUS_COLORS[status] ?? ""}`}
                                        >
                                            {statusLabel(status)}
                                        </Badge>
                                    </div>
                                </CardHeader>
                                <CardContent className="space-y-1">
                                    {client.email && (
                                        <p className="text-xs text-muted-foreground truncate">
                                            {client.email}
                                        </p>
                                    )}
                                    {client.phone && (
                                        <p className="text-xs text-muted-foreground">
                                            {client.phone}
                                        </p>
                                    )}
                                    {client.company && (
                                        <p className="text-xs text-muted-foreground">
                                            {client.company}
                                        </p>
                                    )}
                                    {linked.length > 0 && (
                                        <div className="flex gap-1 mt-2 flex-wrap">
                                            {linked.map((caseId) => (
                                                <Badge key={caseId} variant="outline" className="text-[10px]">
                                                    {caseId.slice(0, 8)}
                                                </Badge>
                                            ))}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* ---- Add Client Dialog ---- */}
            <Dialog open={addOpen} onOpenChange={setAddOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Add Client</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-3">
                        <Input placeholder="Full name *" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                        <Input placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
                        <Input placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                        <Input placeholder="Company" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
                        <Button onClick={() => addClient.mutate(form)} disabled={!form.name || addClient.isPending}>
                            {addClient.isPending ? "Adding..." : "Add Client"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* ---- Client Detail Drawer ---- */}
            <Sheet open={!!selectedClient} onOpenChange={(open) => !open && setSelectedClient(null)}>
                <SheetContent className="sm:max-w-md overflow-y-auto">
                    {selectedClient && (
                        <>
                            <SheetHeader>
                                <SheetTitle>{clientDisplayName(selectedClient)}</SheetTitle>
                                <SheetDescription>Client details and linked cases</SheetDescription>
                            </SheetHeader>

                            <div className="space-y-5 py-4">
                                {/* Status section */}
                                <div className="space-y-1.5">
                                    <label className="text-sm font-medium text-muted-foreground">Status</label>
                                    <div className="flex items-center gap-2">
                                        <DropdownMenu>
                                            <DropdownMenuTrigger asChild>
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    disabled={updateStatusMutation.isPending}
                                                    className="gap-2"
                                                >
                                                    <Badge
                                                        variant="outline"
                                                        className={STATUS_COLORS[selectedClient.intake_status ?? "active"] ?? ""}
                                                    >
                                                        {statusLabel(selectedClient.intake_status)}
                                                    </Badge>
                                                    <span className="text-xs text-muted-foreground">Change</span>
                                                </Button>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent align="start">
                                                <DropdownMenuLabel>Set Status</DropdownMenuLabel>
                                                <DropdownMenuSeparator />
                                                {CLIENT_STATUSES.map((s) => (
                                                    <DropdownMenuItem
                                                        key={s}
                                                        onClick={() =>
                                                            updateStatusMutation.mutate({
                                                                clientId: selectedClient.id,
                                                                status: s,
                                                            })
                                                        }
                                                        disabled={s === (selectedClient.intake_status ?? "active")}
                                                    >
                                                        <Badge
                                                            variant="outline"
                                                            className={`mr-2 text-[10px] ${STATUS_COLORS[s]}`}
                                                        >
                                                            {statusLabel(s)}
                                                        </Badge>
                                                        {s === (selectedClient.intake_status ?? "active") && (
                                                            <span className="text-xs text-muted-foreground ml-auto">current</span>
                                                        )}
                                                    </DropdownMenuItem>
                                                ))}
                                            </DropdownMenuContent>
                                        </DropdownMenu>
                                    </div>
                                </div>

                                {/* Contact info */}
                                <div className="space-y-3">
                                    {selectedClient.email && (
                                        <div className="space-y-0.5">
                                            <label className="text-sm font-medium text-muted-foreground">Email</label>
                                            <p className="text-sm">{selectedClient.email}</p>
                                        </div>
                                    )}
                                    {selectedClient.phone && (
                                        <div className="space-y-0.5">
                                            <label className="text-sm font-medium text-muted-foreground">Phone</label>
                                            <p className="text-sm">{selectedClient.phone}</p>
                                        </div>
                                    )}
                                    {selectedClient.company && (
                                        <div className="space-y-0.5">
                                            <label className="text-sm font-medium text-muted-foreground">Company</label>
                                            <p className="text-sm">{selectedClient.company}</p>
                                        </div>
                                    )}
                                    {selectedClient.client_type && (
                                        <div className="space-y-0.5">
                                            <label className="text-sm font-medium text-muted-foreground">Category</label>
                                            <p className="text-sm">{selectedClient.client_type}</p>
                                        </div>
                                    )}
                                    {selectedClient.mailing_address && (
                                        <div className="space-y-0.5">
                                            <label className="text-sm font-medium text-muted-foreground">Address</label>
                                            <p className="text-sm">{selectedClient.mailing_address}</p>
                                        </div>
                                    )}
                                    {selectedClient.referral_source && (
                                        <div className="space-y-0.5">
                                            <label className="text-sm font-medium text-muted-foreground">Referral Source</label>
                                            <p className="text-sm">{selectedClient.referral_source}</p>
                                        </div>
                                    )}
                                    {selectedClient.notes && (
                                        <div className="space-y-0.5">
                                            <label className="text-sm font-medium text-muted-foreground">Notes</label>
                                            <p className="text-sm whitespace-pre-wrap">{selectedClient.notes}</p>
                                        </div>
                                    )}
                                    {selectedClient.tags && selectedClient.tags.length > 0 && (
                                        <div className="space-y-0.5">
                                            <label className="text-sm font-medium text-muted-foreground">Tags</label>
                                            <div className="flex gap-1 flex-wrap">
                                                {selectedClient.tags.map((tag) => (
                                                    <Badge key={tag} variant="secondary" className="text-[10px]">{tag}</Badge>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {(selectedClient.intake_date || selectedClient.created_at) && (
                                        <div className="space-y-0.5">
                                            <label className="text-sm font-medium text-muted-foreground">Added</label>
                                            <p className="text-sm text-muted-foreground">
                                                {selectedClient.intake_date ?? selectedClient.created_at}
                                            </p>
                                        </div>
                                    )}
                                </div>

                                {/* Linked Cases */}
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-muted-foreground">
                                        Linked Cases ({clientLinkedCases(selectedClient).length})
                                    </label>
                                    {clientLinkedCases(selectedClient).length === 0 ? (
                                        <p className="text-sm text-muted-foreground italic">No linked cases</p>
                                    ) : (
                                        <div className="space-y-1.5">
                                            {clientLinkedCases(selectedClient).map((caseId) => (
                                                <Button
                                                    key={caseId}
                                                    variant="outline"
                                                    size="sm"
                                                    className="w-full justify-start text-left gap-2 font-mono text-xs"
                                                    onClick={() => {
                                                        setSelectedClient(null);
                                                        router.push(`/cases/${caseId}`);
                                                    }}
                                                >
                                                    <span className="text-primary">Case</span>
                                                    {caseId.slice(0, 12)}...
                                                </Button>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>

                            <SheetFooter className="gap-2 pt-4 border-t">
                                <Button
                                    variant="destructive"
                                    size="sm"
                                    onClick={() => setDeleteTarget(selectedClient)}
                                >
                                    Delete Client
                                </Button>
                            </SheetFooter>
                        </>
                    )}
                </SheetContent>
            </Sheet>

            {/* ---- Delete Confirm Dialog ---- */}
            <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Delete Client</AlertDialogTitle>
                        <AlertDialogDescription>
                            Permanently delete &quot;{deleteTarget ? clientDisplayName(deleteTarget) : ""}&quot;?
                            This cannot be undone.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={deleteClientMutation.isPending}>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={() => deleteTarget && deleteClientMutation.mutate(deleteTarget.id)}
                            disabled={deleteClientMutation.isPending}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            {deleteClientMutation.isPending ? "Deleting..." : "Delete"}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
