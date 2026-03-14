// ---- Quick-Add Floating Action Button ------------------------------------
// Persistent FAB (bottom-right) for quickly adding items without navigating.
// Also supports Cmd+N keyboard shortcut.
"use client";

import { useState, useEffect, useRef } from "react";
import { usePathname, useParams, useRouter } from "next/navigation";
import { Plus, Briefcase, Users, Clock, CheckSquare } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface QuickAction {
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    shortcut: string;
    action: () => void;
}

export function QuickAddFab() {
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);
    const pathname = usePathname();
    const params = useParams();
    const router = useRouter();
    const caseId = params.id as string | undefined;

    // Don't show on auth pages
    const isAuthPage = pathname.startsWith("/sign-");
    if (isAuthPage) return null;

    const actions: QuickAction[] = [
        {
            label: "New Case",
            icon: Briefcase,
            shortcut: "C",
            action: () => {
                // Dispatch custom event that NewCaseDialog listens for
                window.dispatchEvent(new CustomEvent("quick-add:new-case"));
                setOpen(false);
            },
        },
        ...(caseId
            ? [
                {
                    label: "Add Witness",
                    icon: Users,
                    shortcut: "W",
                    action: () => {
                        router.push(`/cases/${caseId}/witnesses?action=add`);
                        setOpen(false);
                    },
                },
                {
                    label: "Add Time Entry",
                    icon: Clock,
                    shortcut: "T",
                    action: () => {
                        router.push(`/cases/${caseId}/billing?action=add-time`);
                        setOpen(false);
                    },
                },
            ]
            : []),
        {
            label: "Add Task",
            icon: CheckSquare,
            shortcut: "K",
            action: () => {
                router.push("/tasks?action=add");
                setOpen(false);
            },
        },
    ];

    // Cmd+N to toggle FAB open
    useEffect(() => {
        function handleKey(e: KeyboardEvent) {
            if (
                (e.metaKey || e.ctrlKey) &&
                e.key === "n" &&
                !(e.target instanceof HTMLInputElement) &&
                !(e.target instanceof HTMLTextAreaElement)
            ) {
                e.preventDefault();
                setOpen((prev) => !prev);
            }
        }
        document.addEventListener("keydown", handleKey);
        return () => document.removeEventListener("keydown", handleKey);
    }, []);

    // Click outside to close
    useEffect(() => {
        function handle(e: MouseEvent) {
            if (ref.current && !ref.current.contains(e.target as Node)) {
                setOpen(false);
            }
        }
        if (open) document.addEventListener("mousedown", handle);
        return () => document.removeEventListener("mousedown", handle);
    }, [open]);

    return (
        <div ref={ref} className="fixed bottom-6 right-6 z-50 flex flex-col-reverse items-end gap-2">
            {/* Action items (shown when open) */}
            {open && (
                <div className="flex flex-col-reverse gap-1.5 mb-2 animate-in fade-in slide-in-from-bottom-3 duration-200">
                    {actions.map((a) => {
                        const Icon = a.icon;
                        return (
                            <button
                                key={a.label}
                                onClick={a.action}
                                className="flex items-center gap-3 rounded-full bg-card border shadow-lg px-4 py-2.5 text-sm font-medium hover:bg-accent transition-colors whitespace-nowrap"
                            >
                                <Icon className="h-4 w-4 text-primary" />
                                {a.label}
                                <kbd className="text-[10px] bg-muted px-1.5 py-0.5 rounded font-mono ml-1">
                                    {a.shortcut}
                                </kbd>
                            </button>
                        );
                    })}
                </div>
            )}

            {/* FAB button */}
            <Button
                size="icon"
                className={cn(
                    "h-14 w-14 rounded-full shadow-xl transition-transform duration-200",
                    open && "rotate-45",
                )}
                onClick={() => setOpen(!open)}
                aria-label="Quick add"
            >
                <Plus className="h-6 w-6" />
            </Button>
        </div>
    );
}
