// ---- Client Combobox ----------------------------------------------------
// Searchable dropdown for selecting an existing CRM client or adding a new one.
// No external dependencies — built with Input + absolute-positioned dropdown.
"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { useClients, clientDisplayName, type ClientItem } from "@/hooks/use-clients";

interface ClientComboboxProps {
    value: string;
    onChange: (name: string) => void;
    placeholder?: string;
}

export function ClientCombobox({
    value,
    onChange,
    placeholder = "Search clients or type a new name...",
}: ClientComboboxProps) {
    const { data, isLoading } = useClients();
    const clients = data?.items ?? [];

    const [open, setOpen] = useState(false);
    const [highlightIndex, setHighlightIndex] = useState(-1);
    const containerRef = useRef<HTMLDivElement>(null);
    const listRef = useRef<HTMLDivElement>(null);

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
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
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

    // ---- Select a client from the list ----
    const selectClient = useCallback(
        (client: ClientItem) => {
            onChange(clientDisplayName(client));
            setOpen(false);
            setHighlightIndex(-1);
        },
        [onChange],
    );

    // ---- "+ Add New" action — just close the dropdown, keep typed text ----
    const selectAddNew = useCallback(() => {
        setOpen(false);
        setHighlightIndex(-1);
        // value stays as whatever is typed
    }, []);

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
                    selectAddNew();
                } else if (highlightIndex > 0) {
                    selectClient(filtered[highlightIndex - 1]);
                } else {
                    // Nothing highlighted — close
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
                        className={`flex items-center gap-2 px-3 py-2 cursor-pointer text-sm transition-colors ${
                            highlightIndex === 0
                                ? "bg-accent text-accent-foreground"
                                : "hover:bg-accent/50"
                        }`}
                        onMouseDown={(e) => {
                            e.preventDefault(); // prevent input blur
                            selectAddNew();
                        }}
                        onMouseEnter={() => setHighlightIndex(0)}
                    >
                        <span className="text-primary font-medium">+</span>
                        <span className="font-medium">
                            {value.trim()
                                ? `Add "${value.trim()}" as new client`
                                : "Add New Client"}
                        </span>
                    </div>

                    {/* Separator */}
                    {filtered.length > 0 && (
                        <div className="border-t border-border" />
                    )}

                    {/* Loading state */}
                    {isLoading && (
                        <div className="px-3 py-2 text-sm text-muted-foreground">
                            Loading clients...
                        </div>
                    )}

                    {/* Client list */}
                    {!isLoading && filtered.length === 0 && clients.length > 0 && query && (
                        <div className="px-3 py-2 text-sm text-muted-foreground">
                            No matching clients
                        </div>
                    )}

                    {filtered.map((client, idx) => {
                        const itemIndex = idx + 1; // +1 because "Add New" is index 0
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
    );
}
