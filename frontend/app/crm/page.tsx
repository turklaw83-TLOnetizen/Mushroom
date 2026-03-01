// ---- CRM Page -----------------------------------------------------------
// Client management: list clients, link to cases, intake forms.
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
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

interface Client {
    id: string;
    name: string;
    email: string;
    phone: string;
    company: string;
    cases: string[];
    created_at: string;
}

export default function CRMPage() {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [search, setSearch] = useState("");
    const [addOpen, setAddOpen] = useState(false);
    const [form, setForm] = useState({ name: "", email: "", phone: "", company: "" });

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
                                {client.email && <p className="text-xs text-muted-foreground">📧 {client.email}</p>}
                                {client.phone && <p className="text-xs text-muted-foreground">📞 {client.phone}</p>}
                                {client.company && <p className="text-xs text-muted-foreground">🏢 {client.company}</p>}
                                {client.cases?.length > 0 && (
                                    <div className="flex gap-1 mt-2 flex-wrap">
                                        {client.cases.map((caseId) => (
                                            <Badge key={caseId} variant="outline" className="text-[10px]">
                                                {caseId.slice(0, 8)}
                                            </Badge>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Add Client Dialog */}
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
        </div>
    );
}
