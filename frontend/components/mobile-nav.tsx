// ---- Mobile Navigation (Phase 23) ------------------------------------------
"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
    { label: "Dashboard", href: "/", icon: "home" },
    { label: "Cases", href: "/cases", icon: "briefcase" },
    { label: "Calendar", href: "/calendar", icon: "calendar" },
    { label: "CRM", href: "/crm", icon: "users" },
    { label: "More", href: "#more", icon: "menu" },
];

const MORE_ITEMS = [
    { label: "AI Tools", href: "/ai-tools" },
    { label: "Admin", href: "/admin/tenants" },
    { label: "Settings", href: "/settings" },
];

const ICONS: Record<string, React.ReactNode> = {
    home: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
            <polyline points="9 22 9 12 15 12 15 22" />
        </svg>
    ),
    briefcase: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect width="20" height="14" x="2" y="7" rx="2" ry="2" />
            <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
        </svg>
    ),
    calendar: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect width="18" height="18" x="3" y="4" rx="2" ry="2" />
            <line x1="16" x2="16" y1="2" y2="6" />
            <line x1="8" x2="8" y1="2" y2="6" />
            <line x1="3" x2="21" y1="10" y2="10" />
        </svg>
    ),
    users: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
    ),
    menu: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="1" />
            <circle cx="12" cy="5" r="1" />
            <circle cx="12" cy="19" r="1" />
        </svg>
    ),
};

export function MobileNav() {
    const pathname = usePathname();
    const [showMore, setShowMore] = useState(false);

    return (
        <>
            {/* Bottom Navigation Bar — only visible on mobile */}
            <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 border-t border-border bg-card/95 backdrop-blur-sm safe-area-bottom">
                <div className="flex justify-around items-center h-14">
                    {NAV_ITEMS.map((item) => {
                        const isActive =
                            item.href === "/"
                                ? pathname === "/"
                                : item.href !== "#more" && pathname.startsWith(item.href);
                        const isMore = item.href === "#more";

                        return (
                            <button
                                key={item.label}
                                onClick={() => {
                                    if (isMore) {
                                        setShowMore(!showMore);
                                    } else {
                                        setShowMore(false);
                                    }
                                }}
                                className={cn(
                                    "flex flex-col items-center justify-center w-full h-full gap-0.5 transition-colors",
                                    isActive
                                        ? "text-primary"
                                        : "text-muted-foreground",
                                )}
                            >
                                {isMore ? (
                                    <>
                                        {ICONS[item.icon]}
                                        <span className="text-[10px]">{item.label}</span>
                                    </>
                                ) : (
                                    <Link
                                        href={item.href}
                                        className="flex flex-col items-center justify-center w-full h-full gap-0.5"
                                    >
                                        {ICONS[item.icon]}
                                        <span className="text-[10px]">{item.label}</span>
                                    </Link>
                                )}
                            </button>
                        );
                    })}
                </div>
            </nav>

            {/* More Menu Overlay */}
            {showMore && (
                <>
                    <div
                        className="md:hidden fixed inset-0 bg-black/50 z-30"
                        onClick={() => setShowMore(false)}
                    />
                    <div className="md:hidden fixed bottom-14 inset-x-4 z-40 rounded-xl border border-border bg-card shadow-2xl overflow-hidden animate-in slide-in-from-bottom-4">
                        {MORE_ITEMS.map((item) => (
                            <Link
                                key={item.label}
                                href={item.href}
                                onClick={() => setShowMore(false)}
                                className="flex items-center px-4 py-3 text-sm hover:bg-accent/50 transition-colors border-b border-border last:border-0"
                            >
                                {item.label}
                            </Link>
                        ))}
                    </div>
                </>
            )}
        </>
    );
}
