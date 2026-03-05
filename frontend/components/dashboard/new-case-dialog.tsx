// ---- New Case Dialog ----------------------------------------------------
"use client";

import { useState, useMemo } from "react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { useClients, type ClientItem } from "@/hooks/use-clients";
import { AddClientDialog } from "./add-client-dialog";
import type { CreateCaseInput } from "@/hooks/use-cases";

// ---- Case type / subtype maps -------------------------------------------

const CASE_SUBTYPES: Record<string, { value: string; label: string }[]> = {
    criminal: [
        { value: "adult", label: "Adult" },
        { value: "juvenile", label: "Juvenile" },
    ],
    civil: [
        { value: "personal-injury", label: "Personal Injury" },
        { value: "divorce", label: "Divorce" },
        { value: "juvenile", label: "Juvenile" },
        { value: "other", label: "Other" },
    ],
};

// ---- Props --------------------------------------------------------------

interface NewCaseDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSubmit: (input: CreateCaseInput) => void;
    isLoading: boolean;
}

export function NewCaseDialog({
    open,
    onOpenChange,
    onSubmit,
    isLoading,
}: NewCaseDialogProps) {
    // Client selection
    const [clientSearch, setClientSearch] = useState("");
    const [selectedClient, setSelectedClient] = useState<{
        id: string;
        name: string;
    } | null>(null);
    const [addClientOpen, setAddClientOpen] = useState(false);

    // Case fields
    const [caseName, setCaseName] = useState("");
    const [caseType, setCaseType] = useState("criminal");
    const [caseSubtype, setCaseSubtype] = useState("");
    const [jurisdictionType, setJurisdictionType] = useState("");
    const [county, setCounty] = useState("");
    const [district, setDistrict] = useState("");
    const [docketNumber, setDocketNumber] = useState("");
    const [courtName, setCourtName] = useState("");
    const [dateOfIncident, setDateOfIncident] = useState("");
    const [charges, setCharges] = useState("");
    const [opposingCounsel, setOpposingCounsel] = useState("");

    // Fetch clients for picker
    const { data: clientData } = useClients(clientSearch);
    const clients = clientData?.items ?? [];

    // Filter clients by search text (client-side for responsiveness)
    const filteredClients = useMemo(() => {
        if (!clientSearch.trim()) return clients;
        const q = clientSearch.toLowerCase();
        return clients.filter(
            (c) =>
                c.name?.toLowerCase().includes(q) ||
                c.last_name?.toLowerCase().includes(q) ||
                c.first_name?.toLowerCase().includes(q)
        );
    }, [clients, clientSearch]);

    const resetForm = () => {
        setClientSearch("");
        setSelectedClient(null);
        setCaseName("");
        setCaseType("criminal");
        setCaseSubtype("");
        setJurisdictionType("");
        setCounty("");
        setDistrict("");
        setDocketNumber("");
        setCourtName("");
        setDateOfIncident("");
        setCharges("");
        setOpposingCounsel("");
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!caseName.trim()) return;

        const input: CreateCaseInput = {
            case_name: caseName.trim(),
            case_type: caseType,
            case_subcategory: caseSubtype || undefined,
            client_name: selectedClient?.name || undefined,
            client_id: selectedClient?.id || undefined,
            jurisdiction_type: jurisdictionType || undefined,
            jurisdiction:
                jurisdictionType === "state"
                    ? county.trim() || undefined
                    : jurisdictionType === "federal"
                    ? district.trim() || undefined
                    : undefined,
            county: jurisdictionType === "state" ? county.trim() || undefined : undefined,
            district:
                jurisdictionType === "federal"
                    ? district.trim() || undefined
                    : undefined,
            docket_number: docketNumber.trim() || undefined,
            court_name: courtName.trim() || undefined,
            date_of_incident: dateOfIncident || undefined,
            charges: caseType === "criminal" ? charges.trim() || undefined : undefined,
            opposing_counsel: opposingCounsel.trim() || undefined,
        };

        onSubmit(input);
        resetForm();
    };

    const subtypes = CASE_SUBTYPES[caseType] ?? [];

    return (
        <>
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>Create New Case</DialogTitle>
                        <DialogDescription>
                            Enter case details and client information.
                        </DialogDescription>
                    </DialogHeader>

                    <form onSubmit={handleSubmit} className="space-y-5">
                        {/* ---- Section: Client ---- */}
                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <label className="text-sm font-medium">Client</label>
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    className="h-7 text-xs gap-1"
                                    onClick={() => setAddClientOpen(true)}
                                >
                                    <span>+</span> Add New Client
                                </Button>
                            </div>

                            {selectedClient ? (
                                <div className="flex items-center gap-2 rounded-md border px-3 py-2 bg-muted/50">
                                    <span className="text-sm flex-1">
                                        {selectedClient.name}
                                    </span>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        className="h-6 px-2 text-xs"
                                        onClick={() => setSelectedClient(null)}
                                    >
                                        Change
                                    </Button>
                                </div>
                            ) : (
                                <div className="space-y-1">
                                    <Input
                                        placeholder="Search existing clients..."
                                        value={clientSearch}
                                        onChange={(e) => setClientSearch(e.target.value)}
                                    />
                                    {clientSearch.trim() && filteredClients.length > 0 && (
                                        <div className="rounded-md border bg-popover shadow-md max-h-36 overflow-y-auto">
                                            {filteredClients.slice(0, 8).map((c) => (
                                                <button
                                                    key={c.id}
                                                    type="button"
                                                    className="w-full text-left px-3 py-2 text-sm hover:bg-accent transition-colors"
                                                    onClick={() => {
                                                        setSelectedClient({
                                                            id: c.id,
                                                            name: c.name,
                                                        });
                                                        setClientSearch("");
                                                    }}
                                                >
                                                    <span className="font-medium">
                                                        {c.last_name}, {c.first_name}
                                                    </span>
                                                    {c.phone && (
                                                        <span className="text-muted-foreground ml-2">
                                                            {c.phone}
                                                        </span>
                                                    )}
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                    {clientSearch.trim() && filteredClients.length === 0 && (
                                        <p className="text-xs text-muted-foreground px-1">
                                            No clients found. Click &quot;+ Add New Client&quot; to create one.
                                        </p>
                                    )}
                                </div>
                            )}
                        </div>

                        <hr className="border-border" />

                        {/* ---- Section: Case Info ---- */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium">
                                Case Name <span className="text-destructive">*</span>
                            </label>
                            <Input
                                placeholder="e.g. State v. Johnson"
                                value={caseName}
                                onChange={(e) => setCaseName(e.target.value)}
                                required
                                autoFocus
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Case Type</label>
                                <Select
                                    value={caseType}
                                    onValueChange={(v) => {
                                        setCaseType(v);
                                        setCaseSubtype(""); // reset subtype on type change
                                    }}
                                >
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="criminal">Criminal</SelectItem>
                                        <SelectItem value="civil">Civil</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            {subtypes.length > 0 && (
                                <div className="space-y-2">
                                    <label className="text-sm font-medium">Subtype</label>
                                    <Select
                                        value={caseSubtype}
                                        onValueChange={setCaseSubtype}
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Select..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {subtypes.map((s) => (
                                                <SelectItem key={s.value} value={s.value}>
                                                    {s.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            )}
                        </div>

                        <hr className="border-border" />

                        {/* ---- Section: Jurisdiction ---- */}
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Jurisdiction</label>
                                <Select
                                    value={jurisdictionType}
                                    onValueChange={(v) => {
                                        setJurisdictionType(v);
                                        setCounty("");
                                        setDistrict("");
                                    }}
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="state">State</SelectItem>
                                        <SelectItem value="federal">Federal</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>

                            {jurisdictionType === "state" && (
                                <div className="space-y-2">
                                    <label className="text-sm font-medium">County</label>
                                    <Input
                                        placeholder="e.g. Davidson County"
                                        value={county}
                                        onChange={(e) => setCounty(e.target.value)}
                                    />
                                </div>
                            )}

                            {jurisdictionType === "federal" && (
                                <div className="space-y-2">
                                    <label className="text-sm font-medium">District</label>
                                    <Input
                                        placeholder="e.g. Middle District of TN"
                                        value={district}
                                        onChange={(e) => setDistrict(e.target.value)}
                                    />
                                </div>
                            )}
                        </div>

                        <hr className="border-border" />

                        {/* ---- Section: Case Details ---- */}
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">
                                    Case / Docket Number
                                </label>
                                <Input
                                    placeholder="e.g. 2026-CR-1234"
                                    value={docketNumber}
                                    onChange={(e) => setDocketNumber(e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Court Name</label>
                                <Input
                                    placeholder="e.g. Davidson County Criminal Court"
                                    value={courtName}
                                    onChange={(e) => setCourtName(e.target.value)}
                                />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">
                                    Date of Incident
                                </label>
                                <Input
                                    type="date"
                                    value={dateOfIncident}
                                    onChange={(e) => setDateOfIncident(e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">
                                    Opposing Counsel
                                </label>
                                <Input
                                    placeholder="e.g. ADA Smith"
                                    value={opposingCounsel}
                                    onChange={(e) => setOpposingCounsel(e.target.value)}
                                />
                            </div>
                        </div>

                        {/* Charges — only for criminal cases */}
                        {caseType === "criminal" && (
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Charges</label>
                                <textarea
                                    className="flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
                                    placeholder="e.g. Aggravated Assault (TCA 39-13-102)"
                                    value={charges}
                                    onChange={(e) => setCharges(e.target.value)}
                                    rows={2}
                                />
                            </div>
                        )}

                        <DialogFooter>
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => {
                                    resetForm();
                                    onOpenChange(false);
                                }}
                            >
                                Cancel
                            </Button>
                            <Button
                                type="submit"
                                disabled={isLoading || !caseName.trim()}
                            >
                                {isLoading ? "Creating..." : "Create Case"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* Nested Add Client dialog */}
            <AddClientDialog
                open={addClientOpen}
                onOpenChange={setAddClientOpen}
                onClientCreated={(client) => {
                    setSelectedClient(client);
                    setClientSearch("");
                }}
            />
        </>
    );
}
