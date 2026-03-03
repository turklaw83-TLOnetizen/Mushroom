// ---- New Case Dialog ----------------------------------------------------
"use client";

import { useState } from "react";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface NewCaseDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSubmit: (input: {
        case_name: string;
        description?: string;
        case_type?: string;
        case_category?: string;
        client_name?: string;
        jurisdiction?: string;
    }) => void;
    isLoading: boolean;
}

export function NewCaseDialog({
    open,
    onOpenChange,
    onSubmit,
    isLoading,
}: NewCaseDialogProps) {
    const [name, setName] = useState("");
    const [client, setClient] = useState("");
    const [category, setCategory] = useState("");
    const [caseType, setCaseType] = useState("criminal");
    const [jurisdiction, setJurisdiction] = useState("");

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!name.trim()) return;
        onSubmit({
            case_name: name.trim(),
            client_name: client.trim() || undefined,
            case_category: category.trim() || undefined,
            case_type: caseType,
            jurisdiction: jurisdiction.trim() || undefined,
        });
        // Reset form
        setName("");
        setClient("");
        setCategory("");
        setCaseType("criminal");
        setJurisdiction("");
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Create New Case</DialogTitle>
                    <DialogDescription>
                        Enter the basic information for the new case.
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="space-y-2">
                        <label className="text-sm font-medium">
                            Case Name <span className="text-destructive">*</span>
                        </label>
                        <Input
                            placeholder="e.g. State v. Johnson"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            required
                            autoFocus
                        />
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-medium">Client Name</label>
                        <Input
                            placeholder="e.g. John Johnson"
                            value={client}
                            onChange={(e) => setClient(e.target.value)}
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Type</label>
                            <Select value={caseType} onValueChange={setCaseType}>
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="criminal">Criminal</SelectItem>
                                    <SelectItem value="civil">Civil</SelectItem>
                                    <SelectItem value="family">Family</SelectItem>
                                    <SelectItem value="other">Other</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Jurisdiction</label>
                            <Input
                                placeholder="e.g. Tennessee"
                                value={jurisdiction}
                                onChange={(e) => setJurisdiction(e.target.value)}
                            />
                        </div>
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-medium">Category</label>
                        <Input
                            placeholder="e.g. DUI, Assault, Contract Dispute"
                            value={category}
                            onChange={(e) => setCategory(e.target.value)}
                        />
                    </div>

                    <DialogFooter>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                        >
                            Cancel
                        </Button>
                        <Button type="submit" disabled={isLoading || !name.trim()}>
                            {isLoading ? "Creating..." : "Create Case"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
