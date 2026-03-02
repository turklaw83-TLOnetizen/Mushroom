// ---- Client Combobox ----------------------------------------------------
// Searchable dropdown for selecting an existing CRM client.
// "+ Add New Client" opens a dialog to create a real client in the CRM.
"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
    useClients,
    useCreateClient,
    clientDisplayName,
    type ClientItem,
} from "@/hooks/use-clients";

// ---- Props ---------------------------------------------------------------

interface ClientComboboxProps {
    value: string;
    onChange: (name: string) => void;
    placeholder?: string;
}

// ---- Component -----------------------------------------------------------

export function ClientCombobox({
    value,
    onChange,
    placeholder = "Search clients or type a new name...",
}: ClientComboboxProps) {
    const { data, isLoading } = useClients();
    const createClient = useCreateClient();
    const clients = data?.items ?? [];

    const [open, setOpen] = useState(false);
    const [highlightIndex, setHighlightIndex] = useState(-1);
    const [addDialogOpen, setAddDialogOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);
    const listRef = useRef<HTMLDivElement>(null);

    // ---- "Add New Client" form state ----
    const [newFirst, setNewFirst] = useState("");
    const [newMiddle, setNewMiddle] = useState("");
    const [newLast, setNewLast] = useState("");
    const [newSuffix, setNewSuffix] = useState("");
    const [newPhone, setNewPhone] = useState("");
    const [newEmail, setNewEmail] = useState("");
    const [newAddress, setNewAddress] = useState("");

    // ---- Filter clients by typed text ----
    const query = value.toLowerCase().trim();
    const filtered = query
        ? clients.filter((c) => {
              const display = clientDisplayName(c).toLowerCase();
              const email = (c.email ?? "").toLowerCase();
              const phone = (c.phone ?? "").toLowerCase();
              return (
                  display.includes(query) ||
                  email.includes(query) ||
                  phone.includes(query)
              );
          })
        : clients;

    // Total items = "+ Add New" row + filtered clients
    const totalItems = filtered.length + 1;

    // ---- Close on outside click ----
    useEffect(() => {
        function handleClick(e: MouseEvent) {
            if (
                containerRef.current &&
                !containerRef.current.contains(e.target as Node)
            ) {
                setOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClick);
        return () => document.removeEventListener("mousedown", handleClick);
    }, []);

    // ---- Scroll highlighted item into view ----
    useEffect(() => {
        if (highlightIndex >= 0 && listRef.current) {
            const items = listRef.current.querySelectorAll("[data-combobox-item]");
            items[highlightIndex]?.scrollIntoView({ block: "nearest" });
        }
    }, [highlightIndex]);

    // ---- Select an existing client from the list ----
    const selectClient = useCallback(
        (client: ClientItem) => {
            onChange(clientDisplayName(client));
            setOpen(false);
            setHighlightIndex(-1);
        },
        [onChange],
    );

    // ---- Open the "Add New Client" dialog ----
    const openAddDialog = useCallback(() => {
        setOpen(false);
        setHighlightIndex(-1);

        // Pre-fill first name from whatever the user typed
        const typed = value.trim();
        if (typed) {
            const parts = typed.split(/\s+/);
            setNewFirst(parts[0] || "");
            setNewLast(parts.slice(1).join(" ") || "");
        } else {
            setNewFirst("");
            setNewLast("");
        }
        setNewMiddle("");
        setNewSuffix("");
        setNewPhone("");
        setNewEmail("");
        setNewAddress("");
        setAddDialogOpen(true);
    }, [value]);

    // ---- Submit the "Add New Client" form ----
    const handleCreateClient = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newFirst.trim() && !newLast.trim()) return;

        try {
            await createClient.mutateAsync({
                first_name: newFirst.trim(),
                last_name: newLast.trim(),
                middle_name: newMiddle.trim(),
                suffix: newSuffix.trim(),
                phone: newPhone.trim(),
                email: newEmail.trim(),
                home_address: newAddress.trim(),
            });

            // Build display name for the case form
            const parts = [newFirst.trim(), newMiddle.trim(), newLast.trim()].filter(Boolean);
            let display = parts.join(" ");
            if (newSuffix.trim()) display += `, ${newSuffix.trim()}`;
            onChange(display);
            setAddDialogOpen(false);
        } catch {
            // Error is handled by React Query — toast could be added here
        }
    };

    // ---- Keyboard navigation ----
    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (!open) {
            if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                setOpen(true);
                setHighlightIndex(0);
                e.preventDefault();
            }
            return;
        }

        switch (e.key) {
            case "ArrowDown":
                e.preventDefault();
                setHighlightIndex((prev) => (prev + 1) % totalItems);
                break;
            case "ArrowUp":
                e.preventDefault();
                setHighlightIndex((prev) => (prev - 1 + totalItems) % totalItems);
                break;
            case "Enter":
                e.preventDefault();
                if (highlightIndex === 0) {
                    openAddDialog();
                } else if (highlightIndex > 0) {
                    selectClient(filtered[highlightIndex - 1]);
                } else {
                    setOpen(false);
                }
                break;
            case "Escape":
                e.preventDefault();
                setOpen(false);
                setHighlightIndex(-1);
                break;
        }
    };

    return (
        <>
            {/* ---- Combobox input + dropdown ---- */}
            <div ref={containerRef} className="relative">
                <Input
                    value={value}
                    onChange={(e) => {
                        onChange(e.target.value);
                        setOpen(true);
                        setHighlightIndex(-1);
                    }}
                    onFocus={() => setOpen(true)}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    autoComplete="off"
                />

                {open && (
                    <div
                        ref={listRef}
                        className="absolute z-50 mt-1 w-full max-h-56 overflow-y-auto rounded-md border border-border bg-popover shadow-lg"
                    >
                        {/* "+ Add New Client" — always first */}
                        <div
                            data-combobox-item
                            className={`flex items-center gap-2 px-3 py-2.5 cursor-pointer text-sm transition-colors ${
                                highlightIndex === 0
                                    ? "bg-accent text-accent-foreground"
                                    : "hover:bg-accent/50"
                            }`}
                            onMouseDown={(e) => {
                                e.preventDefault();
                                openAddDialog();
                            }}
                            onMouseEnter={() => setHighlightIndex(0)}
                        >
                            <span className="flex items-center justify-center w-5 h-5 rounded-full bg-primary text-primary-foreground text-xs font-bold">
                                +
                            </span>
                            <span className="font-medium">Add New Client</span>
                        </div>

                        {/* Separator */}
                        {filtered.length > 0 && (
                            <div className="border-t border-border" />
                        )}

                        {/* Loading */}
                        {isLoading && (
                            <div className="px-3 py-2 text-sm text-muted-foreground">
                                Loading clients...
                            </div>
                        )}

                        {/* No results */}
                        {!isLoading && filtered.length === 0 && clients.length > 0 && query && (
                            <div className="px-3 py-2 text-sm text-muted-foreground">
                                No matching clients
                            </div>
                        )}

                        {/* Client list */}
                        {filtered.map((client, idx) => {
                            const itemIndex = idx + 1;
                            const display = clientDisplayName(client);
                            const secondary = client.email || client.phone || "";
                            return (
                                <div
                                    key={client.id}
                                    data-combobox-item
                                    className={`flex flex-col px-3 py-2 cursor-pointer text-sm transition-colors ${
                                        highlightIndex === itemIndex
                                            ? "bg-accent text-accent-foreground"
                                            : "hover:bg-accent/50"
                                    }`}
                                    onMouseDown={(e) => {
                                        e.preventDefault();
                                        selectClient(client);
                                    }}
                                    onMouseEnter={() => setHighlightIndex(itemIndex)}
                                >
                                    <span className="font-medium">{display}</span>
                                    {secondary && (
                                        <span className="text-xs text-muted-foreground truncate">
                                            {secondary}
                                        </span>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* ---- "Add New Client" Dialog ---- */}
            <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
                <DialogContent className="sm:max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Add New Client</DialogTitle>
                        <DialogDescription>
                            Enter the client&apos;s information. Only Last Name
                            is required — all other fields are optional.
                        </DialogDescription>
                    </DialogHeader>

                    <form onSubmit={handleCreateClient} className="space-y-4">
                        {/* Name row */}
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1">
                                <label className="text-sm font-medium">
                                    Last Name{" "}
                                    <span className="text-destructive">*</span>
                                </label>
                                <Input
                                    value={newLast}
                                    onChange={(e) => setNewLast(e.target.value)}
                                    placeholder="Last name"
                                    required
                                    autoFocus
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-sm font-medium">
                                    First Name
                                </label>
                                <Input
                                    value={newFirst}
                                    onChange={(e) => setNewFirst(e.target.value)}
                                    placeholder="First name"
                                />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1">
                                <label className="text-sm font-medium">
                                    Middle Name
                                </label>
                                <Input
                                    value={newMiddle}
                                    onChange={(e) => setNewMiddle(e.target.value)}
                                    placeholder="Middle name"
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-sm font-medium">
                                    Suffix
                                </label>
                                <Input
                                    value={newSuffix}
                                    onChange={(e) => setNewSuffix(e.target.value)}
                                    placeholder="e.g. Jr., Sr., III"
                                />
                            </div>
                        </div>

                        {/* Contact info */}
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1">
                                <label className="text-sm font-medium">
                                    Cell Phone
                                </label>
                                <Input
                                    value={newPhone}
                                    onChange={(e) => setNewPhone(e.target.value)}
                                    placeholder="(615) 555-1234"
                                    type="tel"
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-sm font-medium">
                                    Email
                                </label>
                                <Input
                                    value={newEmail}
                                    onChange={(e) => setNewEmail(e.target.value)}
                                    placeholder="email@example.com"
                                    type="email"
                                />
                            </div>
                        </div>

                        {/* Address */}
                        <div className="space-y-1">
                            <label className="text-sm font-medium">
                                Home Address
                            </label>
                            <Input
                                value={newAddress}
                                onChange={(e) => setNewAddress(e.target.value)}
                                placeholder="123 Main St, Nashville, TN 37201"
                            />
                        </div>

                        <DialogFooter>
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setAddDialogOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button
                                type="submit"
                                disabled={
                                    createClient.isPending ||
                                    !newLast.trim()
                                }
                            >
                                {createClient.isPending
                                    ? "Creating..."
                                    : "Add Client"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>
        </>
    );
}
