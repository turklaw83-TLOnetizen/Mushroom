"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";

const COMMANDS = [
    { id: "dashboard", label: "Dashboard", icon: "⚡", path: "/" },
    { id: "tasks", label: "Task Board", icon: "📋", path: "/tasks" },
    { id: "crm", label: "Clients (CRM)", icon: "👥", path: "/crm" },
    { id: "email", label: "Email Queue", icon: "📧", path: "/email" },
    { id: "conflicts", label: "Conflict Checker", icon: "⚖️", path: "/conflicts" },
    { id: "analytics", label: "Analytics", icon: "📊", path: "/analytics" },
    { id: "portal", label: "Client Portal", icon: "🌐", path: "/portal" },
    { id: "profile", label: "Profile", icon: "👤", path: "/profile" },
    { id: "settings", label: "Settings", icon: "⚙️", path: "/settings" },
    { id: "admin", label: "Admin Dashboard", icon: "🛡️", path: "/admin" },
];

export function CommandPalette() {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    const [selected, setSelected] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);
    const router = useRouter();

    const filtered = COMMANDS.filter(
        (cmd) =>
            cmd.label.toLowerCase().includes(query.toLowerCase()) ||
            cmd.id.includes(query.toLowerCase())
    );

    useEffect(() => {
        function onKeyDown(e: KeyboardEvent) {
            if ((e.metaKey || e.ctrlKey) && e.key === "k") {
                e.preventDefault();
                setOpen((prev) => !prev);
                setQuery("");
                setSelected(0);
            }
            if (e.key === "Escape") setOpen(false);
        }
        document.addEventListener("keydown", onKeyDown);
        return () => document.removeEventListener("keydown", onKeyDown);
    }, []);

    useEffect(() => {
        if (open) inputRef.current?.focus();
    }, [open]);

    const onInputKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key === "ArrowDown") {
                e.preventDefault();
                setSelected((s) => Math.min(s + 1, filtered.length - 1));
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setSelected((s) => Math.max(s - 1, 0));
            } else if (e.key === "Enter" && filtered[selected]) {
                router.push(filtered[selected].path);
                setOpen(false);
            }
        },
        [filtered, selected, router]
    );

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[20vh]" onClick={() => setOpen(false)}>
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
            <div className="relative w-full max-w-lg rounded-xl border border-white/10 bg-gray-900 shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center gap-3 border-b border-white/10 px-4 py-3">
                    <span className="text-white/40 text-lg">🔍</span>
                    <input ref={inputRef} type="text" value={query} onChange={(e) => { setQuery(e.target.value); setSelected(0); }} onKeyDown={onInputKeyDown} placeholder="Search commands..." className="flex-1 bg-transparent text-white placeholder-white/40 outline-none text-sm" />
                    <kbd className="rounded bg-white/10 px-2 py-0.5 text-xs text-white/40 font-mono">ESC</kbd>
                </div>
                <div className="max-h-64 overflow-y-auto py-2">
                    {filtered.length === 0 ? (
                        <div className="px-4 py-8 text-center text-white/40 text-sm">No results found</div>
                    ) : (
                        filtered.map((cmd, i) => (
                            <button key={cmd.id} className={`w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors ${i === selected ? "bg-indigo-500/20 text-white" : "text-white/70 hover:bg-white/5"}`} onClick={() => { router.push(cmd.path); setOpen(false); }} onMouseEnter={() => setSelected(i)}>
                                <span className="text-base">{cmd.icon}</span>
                                <span>{cmd.label}</span>
                                <span className="ml-auto text-xs text-white/30">{cmd.path}</span>
                            </button>
                        ))
                    )}
                </div>
                <div className="border-t border-white/10 px-4 py-2 flex items-center gap-4 text-xs text-white/30">
                    <span>↑↓ navigate</span>
                    <span>↵ select</span>
                    <span>esc close</span>
                </div>
            </div>
        </div>
    );
}
