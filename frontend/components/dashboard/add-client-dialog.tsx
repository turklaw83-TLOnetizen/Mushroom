// ---- Add New Client Dialog -----------------------------------------------
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
import { useCreateClient, type ClientItem } from "@/hooks/use-clients";
import { toast } from "sonner";

interface AddClientDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onClientCreated: (client: { id: string; name: string }) => void;
}

export function AddClientDialog({
    open,
    onOpenChange,
    onClientCreated,
}: AddClientDialogProps) {
    const [lastName, setLastName] = useState("");
    const [firstName, setFirstName] = useState("");
    const [middleInitial, setMiddleInitial] = useState("");
    const [phone, setPhone] = useState("");
    const [email, setEmail] = useState("");
    const [mailingAddress, setMailingAddress] = useState("");

    const createClient = useCreateClient();

    const resetForm = () => {
        setLastName("");
        setFirstName("");
        setMiddleInitial("");
        setPhone("");
        setEmail("");
        setMailingAddress("");
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!lastName.trim() || !firstName.trim()) return;

        try {
            const displayName = middleInitial.trim()
                ? `${firstName.trim()} ${middleInitial.trim()}. ${lastName.trim()}`
                : `${firstName.trim()} ${lastName.trim()}`;

            const result = await createClient.mutateAsync({
                first_name: firstName.trim(),
                last_name: lastName.trim(),
                name: displayName,
                phone: phone.trim(),
                email: email.trim(),
                mailing_address: mailingAddress.trim(),
            });

            toast.success("Client created", { description: displayName });
            onClientCreated({ id: result.id, name: displayName });
            resetForm();
            onOpenChange(false);
        } catch (err) {
            toast.error("Failed to create client", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Add New Client</DialogTitle>
                    <DialogDescription>
                        Enter client contact information.
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                            <label className="text-sm font-medium">
                                Last Name <span className="text-destructive">*</span>
                            </label>
                            <Input
                                placeholder="Johnson"
                                value={lastName}
                                onChange={(e) => setLastName(e.target.value)}
                                required
                                autoFocus
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-sm font-medium">
                                First Name <span className="text-destructive">*</span>
                            </label>
                            <Input
                                placeholder="John"
                                value={firstName}
                                onChange={(e) => setFirstName(e.target.value)}
                                required
                            />
                        </div>
                    </div>

                    <div className="space-y-1">
                        <label className="text-sm font-medium">Middle Initial</label>
                        <Input
                            placeholder="M"
                            value={middleInitial}
                            onChange={(e) => setMiddleInitial(e.target.value.slice(0, 2))}
                            className="w-20"
                        />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                            <label className="text-sm font-medium">Phone</label>
                            <Input
                                placeholder="(555) 123-4567"
                                value={phone}
                                onChange={(e) => setPhone(e.target.value)}
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-sm font-medium">Email</label>
                            <Input
                                type="email"
                                placeholder="john@example.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                            />
                        </div>
                    </div>

                    <div className="space-y-1">
                        <label className="text-sm font-medium">Mailing Address</label>
                        <Input
                            placeholder="123 Main St, Nashville, TN 37203"
                            value={mailingAddress}
                            onChange={(e) => setMailingAddress(e.target.value)}
                        />
                    </div>

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
                            disabled={
                                createClient.isPending ||
                                !lastName.trim() ||
                                !firstName.trim()
                            }
                        >
                            {createClient.isPending ? "Adding..." : "Add Client"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
