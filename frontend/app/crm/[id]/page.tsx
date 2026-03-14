// ---- Client Detail Page --------------------------------------------------
// Full client view with tabs: Overview, Intake Forms, Rep Agreement.
// Wires to all CRM backend endpoints for CRUD, linking, intake, and files.
"use client";

import { useState, useRef, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { useRole } from "@/hooks/use-role";
import { useMutationWithToast } from "@/hooks/use-mutation-with-toast";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Dialog, DialogContent, DialogDescription,
    DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
    AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
    AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
// ---- Types --------------------------------------------------------------

interface IntakeField {
    name: string;
    label: string;
    type: string;
    required?: boolean;
    options?: string[];
}

interface IntakeTemplate {
    key: string;
    name: string;
    fields: IntakeField[];
}

interface ClientDetail {
    id: string;
    name: string;
    first_name: string;
    last_name: string;
    email: string;
    phone: string;
    mailing_address: string;
    home_address: string;
    notes: string;
    referral_source: string;
    tags: string[];
    intake_status: string;
    rep_agreement: boolean;
    last_contact: string;
    cases: string[];
}

interface EditFormData {
    first_name: string;
    last_name: string;
    email: string;
    phone: string;
    mailing_address: string;
    home_address: string;
    notes: string;
    intake_status: string;
    tags: string;
}

// ---- Helper: Info Field -------------------------------------------------

function InfoField({ label, value }: { label: string; value?: string | null }) {
    return (
        <div>
            <span className="text-muted-foreground text-xs">{label}</span>
            <p className="font-medium">{value || "\u2014"}</p>
        </div>
    );
}

// ---- Edit Client Dialog -------------------------------------------------

function EditClientDialog({
    open, onOpenChange, client, onSave, isPending,
}: {
    open: boolean;
    onOpenChange: (v: boolean) => void;
    client: ClientDetail;
    onSave: (data: EditFormData) => void;
    isPending: boolean;
}) {
    const [form, setForm] = useState<EditFormData>({
        first_name: "", last_name: "", email: "", phone: "",
        mailing_address: "", home_address: "", notes: "", intake_status: "", tags: "",
    });

    useEffect(() => {
        if (open && client) {
            setForm({
                first_name: client.first_name || "",
                last_name: client.last_name || "",
                email: client.email || "",
                phone: client.phone || "",
                mailing_address: client.mailing_address || "",
                home_address: client.home_address || "",
                notes: client.notes || "",
                intake_status: client.intake_status || "",
                tags: (client.tags || []).join(", "),
            });
        }
    }, [open, client]);

    const set = (field: keyof EditFormData, value: string) =>
        setForm((prev) => ({ ...prev, [field]: value }));

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Edit Client</DialogTitle>
                    <DialogDescription>Update client information.</DialogDescription>
                </DialogHeader>
                <form onSubmit={(e) => { e.preventDefault(); onSave(form); }} className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">First Name</label>
                            <Input value={form.first_name} onChange={(e) => set("first_name", e.target.value)} placeholder="e.g. John" />
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-sm font-medium">Last Name</label>
                            <Input value={form.last_name} onChange={(e) => set("last_name", e.target.value)} placeholder="e.g. Smith" />
                        </div>
                    </div>
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium">Email</label>
                        <Input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} placeholder="e.g. john@example.com" />
                    </div>
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium">Phone</label>
                        <Input value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="e.g. (555) 123-4567" />
                    </div>
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium">Mailing Address</label>
                        <Input value={form.mailing_address} onChange={(e) => set("mailing_address", e.target.value)} placeholder="e.g. 123 Main St, City, ST 12345" />
                    </div>
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium">Home Address</label>
                        <Input value={form.home_address} onChange={(e) => set("home_address", e.target.value)} placeholder="e.g. 456 Oak Ave, City, ST 67890" />
                    </div>
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium">Intake Status</label>
                        <Select value={form.intake_status} onValueChange={(v) => set("intake_status", v)}>
                            <SelectTrigger><SelectValue placeholder="Select status" /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="active">Active</SelectItem>
                                <SelectItem value="prospective">Prospective</SelectItem>
                                <SelectItem value="former">Former</SelectItem>
                                <SelectItem value="declined">Declined</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium">Tags</label>
                        <Input value={form.tags} onChange={(e) => set("tags", e.target.value)} placeholder="e.g. vip, criminal, referral (comma-separated)" />
                    </div>
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium">Notes</label>
                        <textarea value={form.notes} onChange={(e) => set("notes", e.target.value)} placeholder="Internal notes about this client..." rows={3} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none" />
                    </div>
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                        <Button type="submit" disabled={isPending}>{isPending ? "Saving..." : "Save Changes"}</Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

// ---- Link Case Dialog ---------------------------------------------------

function LinkCaseDialog({
    open, onOpenChange, onLink, isPending,
}: {
    open: boolean;
    onOpenChange: (v: boolean) => void;
    onLink: (caseId: string) => void;
    isPending: boolean;
}) {
    const [caseId, setCaseId] = useState("");
    useEffect(() => { if (open) setCaseId(""); }, [open]);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-sm">
                <DialogHeader>
                    <DialogTitle>Link Case</DialogTitle>
                    <DialogDescription>Enter the case ID to link to this client.</DialogDescription>
                </DialogHeader>
                <form onSubmit={(e) => { e.preventDefault(); if (caseId.trim()) onLink(caseId.trim()); }} className="space-y-4">
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium">Case ID <span className="text-destructive ml-0.5">*</span></label>
                        <Input value={caseId} onChange={(e) => setCaseId(e.target.value)} placeholder="e.g. abc12345-6789-..." autoFocus />
                    </div>
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                        <Button type="submit" disabled={isPending || !caseId.trim()}>{isPending ? "Linking..." : "Link Case"}</Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

// ---- Intake Forms Tab ---------------------------------------------------

function IntakeFormsTab({ clientId }: { clientId: string }) {
    const { getToken } = useAuth();
    const { canEdit } = useRole();
    const queryClient = useQueryClient();
    const [selectedTemplate, setSelectedTemplate] = useState("");
    const [answers, setAnswers] = useState<Record<string, string>>({});
    const [saving, setSaving] = useState(false);

    const templatesQuery = useQuery({
        queryKey: ["crm-intake-templates"],
        queryFn: () => api.get<{ templates: IntakeTemplate[] }>("/crm/intake/templates", { getToken }),
    });

    const savedAnswersQuery = useQuery({
        queryKey: ["crm-intake-answers", clientId],
        queryFn: () => api.get<{ answers: Record<string, Record<string, string>> }>(`/crm/clients/${clientId}/intake`, { getToken }),
    });

    const templates = templatesQuery.data?.templates ?? [];
    const savedData = savedAnswersQuery.data?.answers ?? {};
    const activeTemplate = templates.find((t) => t.key === selectedTemplate);

    useEffect(() => {
        if (selectedTemplate && savedData[selectedTemplate]) {
            setAnswers(savedData[selectedTemplate]);
        } else {
            setAnswers({});
        }
    }, [selectedTemplate, savedData]);

    const handleSave = async () => {
        if (!selectedTemplate) return;
        setSaving(true);
        try {
            await api.post(`/crm/clients/${clientId}/intake`, { template_key: selectedTemplate, answers }, { getToken });
            toast.success("Intake answers saved");
            queryClient.invalidateQueries({ queryKey: ["crm-intake-answers", clientId] });
        } catch (err) {
            toast.error("Failed to save", { description: err instanceof Error ? err.message : "Unknown error" });
        } finally {
            setSaving(false);
        }
    };

    const updateAnswer = (name: string, value: string) =>
        setAnswers((prev) => ({ ...prev, [name]: value }));

    if (templatesQuery.isLoading) {
        return <div className="space-y-3"><Skeleton className="h-10 w-64" /><Skeleton className="h-48 rounded-lg" /></div>;
    }
    if (templatesQuery.error) {
        return (
            <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
                Failed to load templates: {templatesQuery.error instanceof Error ? templatesQuery.error.message : "Unknown error"}
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-end gap-3">
                <div className="space-y-1.5 flex-1 max-w-xs">
                    <label className="text-sm font-medium">Intake Template</label>
                    <Select value={selectedTemplate} onValueChange={setSelectedTemplate}>
                        <SelectTrigger><SelectValue placeholder="Select a template..." /></SelectTrigger>
                        <SelectContent>
                            {templates.map((t) => (
                                <SelectItem key={t.key} value={t.key}>{t.name}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                <div className="flex gap-1.5 flex-wrap pb-1">
                    {templates.filter((t) => savedData[t.key]).map((t) => (
                        <Badge key={t.key} variant="secondary" className="text-[10px] cursor-pointer" onClick={() => setSelectedTemplate(t.key)}>
                            {t.name}
                        </Badge>
                    ))}
                </div>
            </div>

            {activeTemplate ? (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">{activeTemplate.name}</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {activeTemplate.fields.map((field) => (
                            <div key={field.name} className="space-y-1.5">
                                <label className="text-sm font-medium">
                                    {field.label}
                                    {field.required && <span className="text-destructive ml-0.5">*</span>}
                                </label>
                                {field.type === "select" && field.options ? (
                                    <Select value={answers[field.name] || ""} onValueChange={(v) => updateAnswer(field.name, v)} disabled={!canEdit}>
                                        <SelectTrigger><SelectValue placeholder="Select..." /></SelectTrigger>
                                        <SelectContent>
                                            {field.options.map((opt) => <SelectItem key={opt} value={opt}>{opt}</SelectItem>)}
                                        </SelectContent>
                                    </Select>
                                ) : field.type === "textarea" ? (
                                    <textarea value={answers[field.name] || ""} onChange={(e) => updateAnswer(field.name, e.target.value)} rows={3} disabled={!canEdit} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none disabled:opacity-50" />
                                ) : (
                                    <Input type={field.type === "date" ? "date" : "text"} value={answers[field.name] || ""} onChange={(e) => updateAnswer(field.name, e.target.value)} disabled={!canEdit} />
                                )}
                            </div>
                        ))}
                        {canEdit && (
                            <div className="pt-2">
                                <Button onClick={handleSave} disabled={saving}>{saving ? "Saving..." : "Save Answers"}</Button>
                            </div>
                        )}
                    </CardContent>
                </Card>
            ) : (
                <Card>
                    <CardContent className="py-12 text-center text-muted-foreground">
                        Select an intake template above to view or fill out the form.
                    </CardContent>
                </Card>
            )}
        </div>
    );
}

// ---- Rep Agreement Tab --------------------------------------------------

function RepAgreementTab({ clientId, hasAgreement }: { clientId: string; hasAgreement: boolean }) {
    const { getToken } = useAuth();
    const { canEdit } = useRole();
    const queryClient = useQueryClient();
    const fileRef = useRef<HTMLInputElement>(null);
    const [uploading, setUploading] = useState(false);
    const [deleteOpen, setDeleteOpen] = useState(false);
    const [deleting, setDeleting] = useState(false);

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setUploading(true);
        try {
            const token = await getToken();
            const formData = new FormData();
            formData.append("file", file);
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const csrfMatch = document.cookie.match(/(?:^|;\s*)mc-csrf=([^;]*)/);
            const csrfToken = csrfMatch ? decodeURIComponent(csrfMatch[1]) : "";
            const headers: Record<string, string> = {};
            if (token) headers["Authorization"] = `Bearer ${token}`;
            if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
            const res = await fetch(`${apiUrl}/api/v1/crm/clients/${clientId}/rep-agreement`, {
                method: "POST",
                headers,
                credentials: "include",
                body: formData,
            });
            if (!res.ok) {
                const errData = await res.json().catch(() => null);
                throw new Error(errData?.detail || `Upload failed (${res.status})`);
            }
            toast.success("Rep agreement uploaded");
            queryClient.invalidateQueries({ queryKey: ["crm-client", clientId] });
        } catch (err) {
            toast.error("Upload failed", { description: err instanceof Error ? err.message : "Unknown error" });
        } finally {
            setUploading(false);
            if (fileRef.current) fileRef.current.value = "";
        }
    };

    const handleDownload = async () => {
        try {
            const token = await getToken();
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            const res = await fetch(`${apiUrl}/api/v1/crm/clients/${clientId}/rep-agreement`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
            if (!res.ok) throw new Error("Download failed");
            const blob = await res.blob();
            const disposition = res.headers.get("Content-Disposition");
            const filename = disposition?.match(/filename="?([^"]+)"?/)?.[1] || "rep_agreement";
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch {
            toast.error("Download failed");
        }
    };

    const handleDelete = async () => {
        setDeleting(true);
        try {
            await api.delete(`/crm/clients/${clientId}/rep-agreement`, { getToken });
            toast.success("Rep agreement deleted");
            queryClient.invalidateQueries({ queryKey: ["crm-client", clientId] });
            setDeleteOpen(false);
        } catch {
            toast.error("Delete failed");
        } finally {
            setDeleting(false);
        }
    };

    return (
        <div className="space-y-4">
            <Card>
                <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Representation Agreement</CardTitle>
                </CardHeader>
                <CardContent>
                    {hasAgreement ? (
                        <div className="space-y-3">
                            <Badge variant="outline" className="text-xs">Agreement on file</Badge>
                            <div className="flex items-center gap-2 flex-wrap">
                                <Button variant="outline" size="sm" onClick={handleDownload}>Download</Button>
                                {canEdit && (
                                    <>
                                        <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={uploading}>
                                            {uploading ? "Uploading..." : "Replace"}
                                        </Button>
                                        <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => setDeleteOpen(true)}>
                                            Delete
                                        </Button>
                                    </>
                                )}
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            <p className="text-sm text-muted-foreground">No representation agreement uploaded yet.</p>
                            {canEdit && (
                                <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={uploading}>
                                    {uploading ? "Uploading..." : "Upload Agreement"}
                                </Button>
                            )}
                        </div>
                    )}
                    <input type="file" ref={fileRef} onChange={handleUpload} accept=".pdf,.docx,.doc,.txt,.rtf" className="hidden" />
                </CardContent>
            </Card>
            <ConfirmDialog open={deleteOpen} onOpenChange={setDeleteOpen} title="Delete Rep Agreement" description="This will permanently delete the uploaded representation agreement. This cannot be undone." onConfirm={handleDelete} isLoading={deleting} />
        </div>
    );
}

// ---- Main Page ----------------------------------------------------------

export default function ClientDetailPage() {
    const params = useParams();
    const router = useRouter();
    const clientId = params.id as string;
    const { getToken } = useAuth();
    const { canEdit, isAdmin } = useRole();
    const [editOpen, setEditOpen] = useState(false);
    const [deleteOpen, setDeleteOpen] = useState(false);
    const [linkOpen, setLinkOpen] = useState(false);
    const [unlinkTarget, setUnlinkTarget] = useState<string | null>(null);

    // ---- Queries --------------------------------------------------------

    const { data: client, isLoading, error } = useQuery({
        queryKey: ["crm-client", clientId],
        queryFn: () => api.get<ClientDetail>(`/crm/clients/${clientId}`, { getToken }),
    });

    const linkedCasesQuery = useQuery({
        queryKey: ["crm-client-cases", clientId],
        queryFn: () => api.get<{ case_ids: string[] }>(`/crm/clients/${clientId}/cases`, { getToken }),
    });

    // ---- Mutations ------------------------------------------------------

    const updateClient = useMutationWithToast<EditFormData>({
        mutationFn: (data) => {
            const payload: Record<string, unknown> = { ...data };
            if (typeof data.tags === "string") {
                payload.tags = data.tags.split(",").map((t) => t.trim()).filter(Boolean);
            }
            return api.put(`/crm/clients/${clientId}`, payload, { getToken });
        },
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

    const linkCase = useMutationWithToast<string>({
        mutationFn: (caseId) => api.post(`/crm/clients/${clientId}/link`, { case_id: caseId }, { getToken }),
        successMessage: "Case linked",
        invalidateKeys: [["crm-client", clientId], ["crm-client-cases", clientId], ["crm-clients"]],
        onSuccess: () => setLinkOpen(false),
    });

    const unlinkCase = useMutationWithToast<string>({
        mutationFn: (caseId) => api.delete(`/crm/clients/${clientId}/link/${caseId}`, { getToken }),
        successMessage: "Case unlinked",
        invalidateKeys: [["crm-client", clientId], ["crm-client-cases", clientId], ["crm-clients"]],
        onSuccess: () => setUnlinkTarget(null),
    });

    // ---- Loading / Error ------------------------------------------------

    if (isLoading) {
        return (
            <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-6">
                <Skeleton className="h-6 w-24" />
                <Skeleton className="h-8 w-64" />
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-10 w-full rounded-lg" />
                <Skeleton className="h-64 rounded-lg" />
            </div>
        );
    }

    if (error || !client) {
        return (
            <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-4">
                <Button variant="ghost" size="sm" onClick={() => router.push("/crm")}>&larr; Back to Clients</Button>
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
            <Button variant="ghost" size="sm" onClick={() => router.push("/crm")}>&larr; Back to Clients</Button>

            {/* Header */}
            <div className="flex items-start justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">{client.name}</h1>
                    <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground flex-wrap">
                        {client.email && <span>{client.email}</span>}
                        {client.phone && <span>{client.phone}</span>}
                    </div>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                    {canEdit && (
                        <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>Edit</Button>
                    )}
                    {isAdmin && (
                        <Button variant="ghost" size="sm" className="text-destructive hover:text-destructive" onClick={() => setDeleteOpen(true)}>
                            Delete
                        </Button>
                    )}
                </div>
            </div>

            {/* Tabs */}
            <Tabs defaultValue="overview" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="intake">Intake Forms</TabsTrigger>
                    <TabsTrigger value="agreement">Rep Agreement</TabsTrigger>
                </TabsList>

                {/* Tab 1: Overview */}
                <TabsContent value="overview" className="space-y-4">
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-medium">Client Information</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3 text-sm">
                                <InfoField label="First Name" value={client.first_name} />
                                <InfoField label="Last Name" value={client.last_name} />
                                <InfoField label="Email" value={client.email} />
                                <InfoField label="Phone" value={client.phone} />
                                <InfoField label="Mailing Address" value={client.mailing_address} />
                                <InfoField label="Home Address" value={client.home_address} />
                                <InfoField label="Referral Source" value={client.referral_source} />
                                <InfoField label="Intake Status" value={client.intake_status} />
                                <InfoField label="Last Contact" value={client.last_contact ? new Date(client.last_contact).toLocaleDateString() : undefined} />
                                <InfoField label="Rep Agreement" value={client.rep_agreement ? "Yes" : "No"} />
                            </div>

                            {client.tags && client.tags.length > 0 && (
                                <div className="mt-4 pt-3 border-t">
                                    <p className="text-muted-foreground text-xs mb-2">Tags</p>
                                    <div className="flex gap-1.5 flex-wrap">
                                        {client.tags.map((tag) => (
                                            <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {client.notes && (
                                <div className="mt-4 pt-3 border-t">
                                    <p className="text-muted-foreground text-xs mb-1">Notes</p>
                                    <p className="text-sm whitespace-pre-wrap">{client.notes}</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Linked Cases */}
                    <Card>
                        <CardHeader className="pb-2">
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-sm font-medium">Linked Cases</CardTitle>
                                {canEdit && (
                                    <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => setLinkOpen(true)}>
                                        Link Case
                                    </Button>
                                )}
                            </div>
                        </CardHeader>
                        <CardContent>
                            {linkedCases.length === 0 ? (
                                <p className="text-sm text-muted-foreground">No cases linked to this client.</p>
                            ) : (
                                <div className="space-y-2">
                                    {linkedCases.map((caseId) => (
                                        <div key={caseId} className="flex items-center justify-between rounded-md border px-3 py-2">
                                            <Badge variant="outline" className="text-xs cursor-pointer hover:bg-accent font-mono" onClick={() => router.push(`/cases/${caseId}`)}>
                                                {caseId.slice(0, 12)}...
                                            </Badge>
                                            {canEdit && (
                                                <Button variant="ghost" size="sm" className="h-6 text-[10px] px-2 text-destructive hover:text-destructive" onClick={() => setUnlinkTarget(caseId)}>
                                                    Unlink
                                                </Button>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Tab 2: Intake Forms */}
                <TabsContent value="intake">
                    <IntakeFormsTab clientId={clientId} />
                </TabsContent>

                {/* Tab 3: Rep Agreement */}
                <TabsContent value="agreement">
                    <RepAgreementTab clientId={clientId} hasAgreement={!!client.rep_agreement} />
                </TabsContent>
            </Tabs>

            {/* ---- Dialogs ---- */}
            {canEdit && client && (
                <EditClientDialog open={editOpen} onOpenChange={setEditOpen} client={client} onSave={(data) => updateClient.mutate(data)} isPending={updateClient.isPending} />
            )}

            <ConfirmDialog open={deleteOpen} onOpenChange={setDeleteOpen} title="Delete Client" description="This will permanently delete this client and all associated data. This cannot be undone." onConfirm={() => deleteClient.mutate()} isLoading={deleteClient.isPending} />

            <LinkCaseDialog open={linkOpen} onOpenChange={setLinkOpen} onLink={(id) => linkCase.mutate(id)} isPending={linkCase.isPending} />

            <AlertDialog open={!!unlinkTarget} onOpenChange={(open) => { if (!open) setUnlinkTarget(null); }}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Unlink Case</AlertDialogTitle>
                        <AlertDialogDescription>
                            Remove the link between this client and case <span className="font-mono">{unlinkTarget?.slice(0, 12)}...</span>? This does not delete the case.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={unlinkCase.isPending}>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={() => { if (unlinkTarget) unlinkCase.mutate(unlinkTarget); }} disabled={unlinkCase.isPending}>
                            {unlinkCase.isPending ? "Unlinking..." : "Unlink"}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
