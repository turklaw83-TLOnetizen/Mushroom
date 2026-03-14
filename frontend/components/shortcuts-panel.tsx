// ---- Keyboard Shortcuts Help Panel + Global Navigation Shortcuts ----------
// Press ? to show all available keyboard shortcuts.
// Implements G+X chord navigation (G then D/S/T/C within 1 second).
"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { useUIStore } from "@/lib/stores/ui-store";

const shortcuts = [
    { keys: ["\u2318", "K"], desc: "Open command palette" },
    { keys: ["?"], desc: "Show keyboard shortcuts" },
    { keys: ["G", "D"], desc: "Go to Dashboard" },
    { keys: ["G", "S"], desc: "Go to Settings" },
    { keys: ["G", "T"], desc: "Go to Tasks" },
    { keys: ["G", "C"], desc: "Go to Calendar" },
    { keys: ["Esc"], desc: "Close dialog / panel" },
];

function isInputTarget(e: KeyboardEvent): boolean {
    const tag = (e.target as HTMLElement)?.tagName;
    return (
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        tag === "SELECT" ||
        (e.target as HTMLElement)?.isContentEditable === true
    );
}

export function ShortcutsPanel() {
    const [open, setOpen] = useState(false);
    const router = useRouter();
    const setCommandPaletteOpen = useUIStore((s) => s.setCommandPaletteOpen);

    // G-chord state: when G is pressed, we wait up to 1s for the second key
    const pendingGRef = useRef(false);
    const gTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const clearGChord = useCallback(() => {
        pendingGRef.current = false;
        if (gTimerRef.current) {
            clearTimeout(gTimerRef.current);
            gTimerRef.current = null;
        }
    }, []);

    useEffect(() => {
        function handle(e: KeyboardEvent) {
            // Never intercept when user is typing in an input
            if (isInputTarget(e)) {
                // Clear any pending G chord if user starts typing in an input
                clearGChord();
                return;
            }

            // ---- Cmd/Ctrl+K: Open command palette ----
            if ((e.metaKey || e.ctrlKey) && e.key === "k") {
                // Don't handle here -- the CommandPalette component handles this.
                // This avoids double-toggling.
                return;
            }

            // ---- ? : Show shortcuts panel ----
            if (e.key === "?" && !e.metaKey && !e.ctrlKey) {
                e.preventDefault();
                setOpen(true);
                clearGChord();
                return;
            }

            // ---- Esc: Close any open dialog ----
            // Radix Dialog handles Esc natively, so we don't need to do
            // anything special here. This is just for completeness in case
            // we have custom panels in the future.

            // ---- G-chord navigation ----
            if (e.metaKey || e.ctrlKey || e.altKey) return;

            // Second key of G-chord
            if (pendingGRef.current) {
                clearGChord();
                const key = e.key.toLowerCase();
                switch (key) {
                    case "d":
                        e.preventDefault();
                        router.push("/");
                        return;
                    case "s":
                        e.preventDefault();
                        router.push("/settings");
                        return;
                    case "t":
                        e.preventDefault();
                        router.push("/tasks");
                        return;
                    case "c":
                        e.preventDefault();
                        router.push("/calendar");
                        return;
                    default:
                        // Not a valid chord second key -- ignore
                        return;
                }
            }

            // First key of G-chord
            if (e.key === "g" || e.key === "G") {
                // Don't prevent default -- just start the chord timer
                pendingGRef.current = true;
                gTimerRef.current = setTimeout(() => {
                    pendingGRef.current = false;
                    gTimerRef.current = null;
                }, 1000);
                return;
            }
        }

        document.addEventListener("keydown", handle);
        return () => {
            document.removeEventListener("keydown", handle);
            clearGChord();
        };
    }, [router, setCommandPaletteOpen, clearGChord]);

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogContent className="max-w-sm">
                <DialogHeader>
                    <DialogTitle>Keyboard Shortcuts</DialogTitle>
                </DialogHeader>
                <div className="space-y-1">
                    {shortcuts.map((s, i) => (
                        <div
                            key={i}
                            className="flex items-center justify-between py-2 border-b last:border-0"
                        >
                            <span className="text-sm text-muted-foreground">{s.desc}</span>
                            <div className="flex gap-1">
                                {s.keys.map((k, j) => (
                                    <kbd
                                        key={j}
                                        className="px-2 py-0.5 rounded bg-accent text-xs font-mono min-w-[24px] text-center"
                                    >
                                        {k}
                                    </kbd>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
                <p className="text-[11px] text-muted-foreground text-center mt-2">
                    Press <kbd className="px-1 py-0.5 rounded bg-accent text-[10px] font-mono">?</kbd> anytime to show this panel
                </p>
            </DialogContent>
        </Dialog>
    );
}
