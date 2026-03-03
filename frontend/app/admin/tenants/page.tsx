// ---- Tenant Admin Page (Phase 22) -----------------------------------------
"use client";

export const dynamic = "force-dynamic";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

interface Tenant {
    id: string;
    name: string;
    slug: string;
    plan: "starter" | "professional" | "enterprise";
    active: boolean;
    user_count: number;
    case_count: number;
    storage_used_gb: number;
    created_at: string;
    branding?: {
        primary_color: string;
        firm_name: string;
        logo_url: string;
    };
}

interface TenantUsage {
    users: { current: number; limit: number };
    cases: { current: number; limit: number };
    storage_gb: { current: number; limit: number };
    api_calls: { current: number; limit: number };
}

const PLAN_LIMITS: Record<string, { users: number; cases: number; storage: string }> = {
    starter: { users: 5, cases: 50, storage: "10 GB" },
    professional: { users: 25, cases: 500, storage: "100 GB" },
    enterprise: { users: -1, cases: -1, storage: "Unlimited" },
};

const PLAN_COLORS: Record<string, string> = {
    starter: "bg-gray-500/10 text-gray-400",
    professional: "bg-indigo-500/10 text-indigo-400",
    enterprise: "bg-amber-500/10 text-amber-400",
};

export default function TenantsAdminPage() {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [selectedTenant, setSelectedTenant] = useState<string | null>(null);
    const [showCreate, setShowCreate] = useState(false);
    const [newTenant, setNewTenant] = useState({ name: "", slug: "", plan: "starter" });

    const { data: tenants, isLoading } = useQuery({
        queryKey: ["tenants"],
        queryFn: () => api.get<Tenant[]>("/tenants", { getToken }),
    });

    const { data: usage } = useQuery({
        queryKey: ["tenant-usage", selectedTenant],
        queryFn: () =>
            api.get<TenantUsage>(`/tenants/${selectedTenant}/usage`, { getToken }),
        enabled: !!selectedTenant,
    });

    const createTenantMutation = useMutation({
        mutationFn: (data: { name: string; slug: string; plan: string }) =>
            api.post("/tenants", data, { getToken }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["tenants"] });
            setShowCreate(false);
            setNewTenant({ name: "", slug: "", plan: "starter" });
        },
    });

    const selectedTenantData = tenants?.find((t) => t.id === selectedTenant);

    return (
        <div className="max-w-7xl mx-auto p-6 space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Tenant Management</h1>
                    <p className="text-sm text-muted-foreground mt-0.5">
                        Manage organizations, plans, and branding
                    </p>
                </div>
                <Button onClick={() => setShowCreate(!showCreate)}>
                    {showCreate ? "Cancel" : "New Tenant"}
                </Button>
            </div>

            {/* Create Tenant Form */}
            {showCreate && (
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Create Tenant</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="grid grid-cols-3 gap-3">
                            <div>
                                <label className="text-xs font-medium text-muted-foreground">Name</label>
                                <input
                                    type="text"
                                    value={newTenant.name}
                                    onChange={(e) => setNewTenant({ ...newTenant, name: e.target.value })}
                                    placeholder="Acme Law Firm"
                                    className="w-full mt-1 text-sm bg-muted border border-border rounded-md px-3 py-1.5"
                                />
                            </div>
                            <div>
                                <label className="text-xs font-medium text-muted-foreground">Slug</label>
                                <input
                                    type="text"
                                    value={newTenant.slug}
                                    onChange={(e) => setNewTenant({ ...newTenant, slug: e.target.value })}
                                    placeholder="acme-law"
                                    className="w-full mt-1 text-sm bg-muted border border-border rounded-md px-3 py-1.5"
                                />
                            </div>
                            <div>
                                <label className="text-xs font-medium text-muted-foreground">Plan</label>
                                <select
                                    value={newTenant.plan}
                                    onChange={(e) => setNewTenant({ ...newTenant, plan: e.target.value })}
                                    className="w-full mt-1 text-sm bg-muted border border-border rounded-md px-3 py-1.5"
                                >
                                    <option value="starter">Starter</option>
                                    <option value="professional">Professional</option>
                                    <option value="enterprise">Enterprise</option>
                                </select>
                            </div>
                        </div>
                        <Button
                            size="sm"
                            onClick={() => createTenantMutation.mutate(newTenant)}
                            disabled={!newTenant.name || !newTenant.slug || createTenantMutation.isPending}
                        >
                            {createTenantMutation.isPending ? "Creating..." : "Create"}
                        </Button>
                    </CardContent>
                </Card>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Tenant List */}
                <div className="space-y-2">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Tenants ({tenants?.length || 0})
                    </p>
                    {isLoading ? (
                        Array.from({ length: 3 }).map((_, i) => (
                            <Skeleton key={i} className="h-20 rounded-lg" />
                        ))
                    ) : !tenants || tenants.length === 0 ? (
                        <Card className="border-dashed">
                            <CardContent className="py-8 text-center text-muted-foreground text-sm">
                                No tenants yet.
                            </CardContent>
                        </Card>
                    ) : (
                        tenants.map((tenant) => (
                            <Card
                                key={tenant.id}
                                className={`cursor-pointer transition-colors ${
                                    selectedTenant === tenant.id
                                        ? "border-primary bg-primary/5"
                                        : "hover:bg-accent/30"
                                }`}
                                onClick={() => setSelectedTenant(tenant.id)}
                            >
                                <CardContent className="py-3">
                                    <div className="flex items-center justify-between">
                                        <p className="text-sm font-medium">{tenant.name}</p>
                                        <Badge className={`text-[10px] ${PLAN_COLORS[tenant.plan] || ""}`}>
                                            {tenant.plan}
                                        </Badge>
                                    </div>
                                    <p className="text-xs text-muted-foreground mt-0.5">{tenant.slug}</p>
                                    <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
                                        <span>{tenant.user_count} users</span>
                                        <span>{tenant.case_count} cases</span>
                                        <span>{tenant.storage_used_gb.toFixed(1)} GB</span>
                                    </div>
                                </CardContent>
                            </Card>
                        ))
                    )}
                </div>

                {/* Tenant Detail */}
                <div className="lg:col-span-2 space-y-4">
                    {selectedTenantData ? (
                        <>
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-base">
                                        {selectedTenantData.name}
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <p className="text-xs text-muted-foreground">Plan</p>
                                            <p className="text-sm font-medium capitalize">
                                                {selectedTenantData.plan}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-muted-foreground">Status</p>
                                            <Badge variant={selectedTenantData.active ? "default" : "secondary"}>
                                                {selectedTenantData.active ? "Active" : "Inactive"}
                                            </Badge>
                                        </div>
                                        <div>
                                            <p className="text-xs text-muted-foreground">Created</p>
                                            <p className="text-sm">
                                                {new Date(selectedTenantData.created_at).toLocaleDateString()}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-muted-foreground">Slug</p>
                                            <p className="text-sm font-mono">{selectedTenantData.slug}</p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Usage */}
                            {usage && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="text-base">Usage & Quotas</CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        {[
                                            { label: "Users", ...usage.users },
                                            { label: "Cases", ...usage.cases },
                                            { label: "Storage (GB)", ...usage.storage_gb },
                                            { label: "API Calls", ...usage.api_calls },
                                        ].map((item) => (
                                            <div key={item.label}>
                                                <div className="flex justify-between text-sm mb-1">
                                                    <span>{item.label}</span>
                                                    <span className="text-muted-foreground">
                                                        {item.current} / {item.limit < 0 ? "\u221E" : item.limit}
                                                    </span>
                                                </div>
                                                <div className="h-2 bg-muted rounded-full overflow-hidden">
                                                    <div
                                                        className={`h-full rounded-full transition-all ${
                                                            item.limit > 0 && item.current / item.limit > 0.9
                                                                ? "bg-red-500"
                                                                : item.limit > 0 && item.current / item.limit > 0.7
                                                                ? "bg-amber-500"
                                                                : "bg-emerald-500"
                                                        }`}
                                                        style={{
                                                            width: `${
                                                                item.limit > 0
                                                                    ? Math.min(100, (item.current / item.limit) * 100)
                                                                    : 10
                                                            }%`,
                                                        }}
                                                    />
                                                </div>
                                            </div>
                                        ))}
                                    </CardContent>
                                </Card>
                            )}

                            {/* Branding Preview */}
                            {selectedTenantData.branding && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="text-base">Branding</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="flex items-center gap-4">
                                            {selectedTenantData.branding.logo_url && (
                                                <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center overflow-hidden">
                                                    <img
                                                        src={selectedTenantData.branding.logo_url}
                                                        alt="Logo"
                                                        className="max-w-full max-h-full object-contain"
                                                    />
                                                </div>
                                            )}
                                            <div>
                                                <p className="text-sm font-medium">
                                                    {selectedTenantData.branding.firm_name || selectedTenantData.name}
                                                </p>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <div
                                                        className="w-4 h-4 rounded-full border border-border"
                                                        style={{
                                                            backgroundColor: selectedTenantData.branding.primary_color,
                                                        }}
                                                    />
                                                    <span className="text-xs text-muted-foreground">
                                                        {selectedTenantData.branding.primary_color}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            )}
                        </>
                    ) : (
                        <Card className="border-dashed h-full">
                            <CardContent className="py-20 text-center text-muted-foreground">
                                Select a tenant to view details.
                            </CardContent>
                        </Card>
                    )}
                </div>
            </div>
        </div>
    );
}
