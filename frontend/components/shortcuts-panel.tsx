// ---- Keyboard Shortcuts Help Panel --------------------------------------
// Press ? to show all available keyboard shortcuts.
"use client";

import { useState, useEffect } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

const shortcuts = [
    { keys: ["⌘", "K"], desc: "Open command palette" },
    { keys: ["?"], desc: "Show this help panel" },
    { keys: ["G", "D"], desc: "Go to Dashboard" },
    { keys: ["G", "S"], desc: "Go to Settings" },
    { keys: ["Esc"], desc: "Close dialog / deselect" },
    { keys: ["↑", "↓"], desc: "Navigate list items" },
    { keys: ["Enter"], desc: "Select / confirm" },
    { keys: ["⌘", "Z"], desc: "Undo last action" },
];

export function ShortcutsPanel() {
    const [open, setOpen] = useState(false);

    useEffect(() => {
        function handle(e: KeyboardEvent) {
            // Only trigger on ? when not in an input/textarea
            if (
                e.key === "?" &&
                !e.metaKey &&
                !e.ctrlKey &&
                !(e.target instanceof HTMLInputElement) &&
                !(e.target instanceof HTMLTextAreaElement)
            ) {
                e.preventDefault();
                setOpen(true);
            }
        }
        document.addEventListener("keydown", handle);
        return () => document.removeEventListener("keydown", handle);
    }, []);

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
