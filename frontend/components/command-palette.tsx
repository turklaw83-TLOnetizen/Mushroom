// ---- Command Palette (Cmd+K) ---------------------------------------------
// Searchable command palette with navigation, cases, and actions.
// Built from scratch using Dialog + Input — no cmdk dependency.
"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
    Dialog,
    DialogContent,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { useUIStore } from "@/lib/stores/ui-store";
import { useCases, type CaseItem } from "@/hooks/use-cases";
import {
    LayoutDashboard,
    Sun,
    CheckSquare,
    Calendar,
    Users,
    Search,
    Settings,
    Plus,
    Palette,
    PanelLeftClose,
    Briefcase,
} from "lucide-react";

// ---- Types ---------------------------------------------------------------

interface CommandItem {
    id: string;
    label: string;
    icon: React.ReactNode;
    category: "Navigation" | "Cases" | "Actions";
    onSelect: () => void;
}

// ---- Static navigation items ---------------------------------------------

function useNavigationItems(router: ReturnType<typeof useRouter>, close: () => void): CommandItem[] {
    return useMemo(() => [
        {
            id: "nav-dashboard",
            label: "Dashboard",
            icon: <LayoutDashboard className="h-4 w-4" />,
            category: "Navigation" as const,
            onSelect: () => { router.push("/"); close(); },
        },
        {
            id: "nav-brief",
            label: "Morning Brief",
            icon: <Sun className="h-4 w-4" />,
            category: "Navigation" as const,
            onSelect: () => { router.push("/brief"); close(); },
        },
        {
            id: "nav-tasks",
            label: "Tasks",
            icon: <CheckSquare className="h-4 w-4" />,
            category: "Navigation" as const,
            onSelect: () => { router.push("/tasks"); close(); },
        },
        {
            id: "nav-calendar",
            label: "Calendar",
            icon: <Calendar className="h-4 w-4" />,
            category: "Navigation" as const,
            onSelect: () => { router.push("/calendar"); close(); },
        },
        {
            id: "nav-clients",
            label: "Clients",
            icon: <Users className="h-4 w-4" />,
            category: "Navigation" as const,
            onSelect: () => { router.push("/crm"); close(); },
        },
        {
            id: "nav-settings",
            label: "Settings",
            icon: <Settings className="h-4 w-4" />,
            category: "Navigation" as const,
            onSelect: () => { router.push("/settings"); close(); },
        },
        {
            id: "nav-search",
            label: "Search",
            icon: <Search className="h-4 w-4" />,
            category: "Navigation" as const,
            onSelect: () => { router.push("/search"); close(); },
        },
    ], [router, close]);
}

// ---- Action items --------------------------------------------------------

function useActionItems(close: () => void): CommandItem[] {
    const setTheme = useUIStore((s) => s.setTheme);
    const theme = useUIStore((s) => s.theme);
    const toggleSidebar = useUIStore((s) => s.toggleSidebar);

    return useMemo(() => [
        {
            id: "action-new-case",
            label: "New Case",
            icon: <Plus className="h-4 w-4" />,
            category: "Actions" as const,
            onSelect: () => {
                window.dispatchEvent(new CustomEvent("mc:new-case"));
                close();
            },
        },
        {
            id: "action-toggle-theme",
            label: "Toggle Theme",
            icon: <Palette className="h-4 w-4" />,
            category: "Actions" as const,
            onSelect: () => {
                const next = theme === "dark" ? "light" : "dark";
                setTheme(next);
                document.documentElement.classList.toggle("dark", next === "dark");
                close();
            },
        },
        {
            id: "action-toggle-sidebar",
            label: "Toggle Sidebar",
            icon: <PanelLeftClose className="h-4 w-4" />,
            category: "Actions" as const,
            onSelect: () => {
                toggleSidebar();
                close();
            },
        },
    ], [close, setTheme, theme, toggleSidebar]);
}

// ---- Case items ----------------------------------------------------------

function useCaseItems(router: ReturnType<typeof useRouter>, close: () => void): CommandItem[] {
    const { data: casesData } = useCases(1, 50);

    return useMemo(() => {
        if (!casesData?.items?.length) return [];
        return casesData.items.map((c: CaseItem) => ({
            id: `case-${c.id}`,
            label: c.name,
            icon: <Briefcase className="h-4 w-4" />,
            category: "Cases" as const,
            onSelect: () => { router.push(`/cases/${c.id}`); close(); },
        }));
    }, [casesData, router, close]);
}

// ---- Category ordering ---------------------------------------------------

const CATEGORY_ORDER: CommandItem["category"][] = ["Navigation", "Cases", "Actions"];

// ---- Component -----------------------------------------------------------

export function CommandPalette() {
    const open = useUIStore((s) => s.commandPaletteOpen);
    const setOpen = useUIStore((s) => s.setCommandPaletteOpen);
    const [query, setQuery] = useState("");
    const [selectedIndex, setSelectedIndex] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);
    const listRef = useRef<HTMLDivElement>(null);
    const router = useRouter();

    const close = useCallback(() => {
        setOpen(false);
        setQuery("");
        setSelectedIndex(0);
    }, [setOpen]);

    const navigationItems = useNavigationItems(router, close);
    const caseItems = useCaseItems(router, close);
    const actionItems = useActionItems(close);

    // All items, filtered by query
    const allItems = useMemo(
        () => [...navigationItems, ...caseItems, ...actionItems],
        [navigationItems, caseItems, actionItems],
    );

    const filtered = useMemo(() => {
        if (!query.trim()) return allItems;
        const q = query.toLowerCase();
        return allItems.filter((item) => item.label.toLowerCase().includes(q));
    }, [allItems, query]);

    // Group filtered items by category
    const grouped = useMemo(() => {
        const groups: { category: string; items: CommandItem[] }[] = [];
        for (const cat of CATEGORY_ORDER) {
            const items = filtered.filter((item) => item.category === cat);
            if (items.length > 0) {
                groups.push({ category: cat, items });
            }
        }
        return groups;
    }, [filtered]);

    // Flat list of items (for keyboard navigation index)
    const flatItems = useMemo(
        () => grouped.flatMap((g) => g.items),
        [grouped],
    );

    // ---- Cmd+K global listener ------------------------------------------
    useEffect(() => {
        function onKeyDown(e: KeyboardEvent) {
            if ((e.metaKey || e.ctrlKey) && e.key === "k") {
                e.preventDefault();
                if (open) {
                    close();
                } else {
                    setOpen(true);
                    setQuery("");
                    setSelectedIndex(0);
                }
            }
        }
        document.addEventListener("keydown", onKeyDown);
        return () => document.removeEventListener("keydown", onKeyDown);
    }, [open, close, setOpen]);

    // Focus input when opened
    useEffect(() => {
        if (open) {
            // Small delay to ensure the dialog has rendered
            const t = setTimeout(() => inputRef.current?.focus(), 50);
            return () => clearTimeout(t);
        }
    }, [open]);

    // Clamp selectedIndex when filtered results change
    useEffect(() => {
        setSelectedIndex(0);
    }, [query]);

    // Scroll selected item into view
    useEffect(() => {
        if (!listRef.current) return;
        const el = listRef.current.querySelector(`[data-index="${selectedIndex}"]`);
        if (el) {
            el.scrollIntoView({ block: "nearest" });
        }
    }, [selectedIndex]);

    // ---- Input keyboard handler -----------------------------------------
    const onInputKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key === "ArrowDown") {
                e.preventDefault();
                setSelectedIndex((s) => Math.min(s + 1, flatItems.length - 1));
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setSelectedIndex((s) => Math.max(s - 1, 0));
            } else if (e.key === "Enter") {
                e.preventDefault();
                if (flatItems[selectedIndex]) {
                    flatItems[selectedIndex].onSelect();
                }
            }
        },
        [flatItems, selectedIndex],
    );

    return (
        <Dialog
            open={open}
            onOpenChange={(isOpen) => {
                if (!isOpen) close();
                else setOpen(true);
            }}
        >
            <DialogContent
                className="max-w-lg p-0 gap-0 overflow-hidden"
                showCloseButton={false}
                // Prevent Radix from auto-focusing the close button
                onOpenAutoFocus={(e) => e.preventDefault()}
            >
                {/* Search input */}
                <div className="flex items-center gap-3 px-4 py-3">
                    <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <input
                        ref={inputRef}
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={onInputKeyDown}
                        placeholder="Type a command or search..."
                        className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                    />
                    <kbd className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground font-mono">
                        ESC
                    </kbd>
                </div>

                <Separator />

                {/* Results */}
                <div ref={listRef} className="max-h-[400px] overflow-y-auto py-2">
                    {flatItems.length === 0 ? (
                        <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                            No results found
                        </div>
                    ) : (
                        grouped.map((group) => {
                            return (
                                <div key={group.category}>
                                    {/* Section header */}
                                    <div className="text-xs font-medium text-muted-foreground uppercase px-3 py-1.5">
                                        {group.category}
                                    </div>
                                    {/* Items */}
                                    {group.items.map((item) => {
                                        const globalIdx = flatItems.indexOf(item);
                                        return (
                                            <button
                                                key={item.id}
                                                data-index={globalIdx}
                                                className={`w-full flex items-center gap-3 px-3 py-2 text-sm rounded-md cursor-pointer transition-colors ${
                                                    globalIdx === selectedIndex
                                                        ? "bg-accent text-accent-foreground"
                                                        : "text-foreground hover:bg-accent"
                                                }`}
                                                onClick={() => item.onSelect()}
                                                onMouseEnter={() => setSelectedIndex(globalIdx)}
                                            >
                                                <span className="shrink-0 text-muted-foreground">
                                                    {item.icon}
                                                </span>
                                                <span className="truncate">{item.label}</span>
                                            </button>
                                        );
                                    })}
                                </div>
                            );
                        })
                    )}
                </div>

                {/* Footer hints */}
                <Separator />
                <div className="px-4 py-2 flex items-center gap-4 text-xs text-muted-foreground">
                    <span>
                        <kbd className="font-mono">&#8593;&#8595;</kbd> navigate
                    </span>
                    <span>
                        <kbd className="font-mono">&#x21B5;</kbd> select
                    </span>
                    <span>
                        <kbd className="font-mono">esc</kbd> close
                    </span>
                </div>
            </DialogContent>
        </Dialog>
    );
}
