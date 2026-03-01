// ---- useKeyboardShortcuts -----------------------------------------------
// Global keyboard shortcuts for case tab pages.
// Provides: n (new item), Escape (close panel), j/k (list navigation)
"use client";

import { useEffect, useCallback } from "react";

interface ShortcutHandlers {
    /** Called when "n" is pressed — opens create dialog */
    onNew?: () => void;
    /** Called when Escape is pressed — closes panel/dialog */
    onEscape?: () => void;
    /** Called when "j" is pressed — selects next item */
    onNext?: () => void;
    /** Called when "k" is pressed — selects previous item */
    onPrev?: () => void;
    /** Called when Enter is pressed — opens detail for selected */
    onOpen?: () => void;
    /** Called when "d" is pressed — opens delete dialog */
    onDelete?: () => void;
}

/**
 * Attaches global keyboard shortcuts. Ignores keypresses when
 * user is typing in an input, textarea, or select.
 *
 * @example
 * useKeyboardShortcuts({
 *   onNew: () => setDialogOpen(true),
 *   onEscape: () => { setDetailItem(null); setDeleteTarget(null); },
 * });
 */
export function useKeyboardShortcuts(handlers: ShortcutHandlers) {
    const handleKeyDown = useCallback(
        (e: KeyboardEvent) => {
            // Don't intercept when typing in form fields
            const tag = (e.target as HTMLElement).tagName;
            if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
            // Don't intercept when command/ctrl key is held (reserved for browser/OS)
            if (e.metaKey || e.ctrlKey) return;

            switch (e.key) {
                case "n":
                    e.preventDefault();
                    handlers.onNew?.();
                    break;
                case "Escape":
                    handlers.onEscape?.();
                    break;
                case "j":
                case "ArrowDown":
                    e.preventDefault();
                    handlers.onNext?.();
                    break;
                case "k":
                case "ArrowUp":
                    e.preventDefault();
                    handlers.onPrev?.();
                    break;
                case "Enter":
                    handlers.onOpen?.();
                    break;
                case "d":
                    handlers.onDelete?.();
                    break;
                default:
                    break;
            }
        },
        [handlers],
    );

    useEffect(() => {
        document.addEventListener("keydown", handleKeyDown);
        return () => document.removeEventListener("keydown", handleKeyDown);
    }, [handleKeyDown]);
}
