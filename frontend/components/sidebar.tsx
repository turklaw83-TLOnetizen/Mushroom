// ---- Sidebar Component (Responsive) ------------------------------------
"use client";

import { useEffect, memo } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserButton, useUser } from "@clerk/nextjs";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/stores/ui-store";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ThemeToggle } from "@/components/theme-toggle";

// Memoized user button — only re-renders when Clerk auth state actually changes
const StableUserButton = memo(function StableUserButton() {
    const { isLoaded, isSignedIn } = useUser();

    // Fixed-size container prevents layout shift during Clerk loading
    return (
        <div className="h-8 w-8 shrink-0">
            {isLoaded && isSignedIn ? (
                <UserButton
                    afterSignOutUrl="/sign-in"
                    appearance={{
                        elements: { avatarBox: "h-8 w-8" },
                    }}
                />
            ) : (
                <div className="h-8 w-8 rounded-full bg-white/10 animate-pulse" />
            )}
        </div>
    );
});

export function Sidebar() {
    const pathname = usePathname();
    const sidebarOpen = useUIStore((s) => s.sidebarOpen);
    const toggleSidebar = useUIStore((s) => s.toggleSidebar);
    const setSidebarOpen = useUIStore((s) => s.setSidebarOpen);

    // Auto-collapse on mobile
    useEffect(() => {
        const mq = window.matchMedia("(max-width: 768px)");
        const handler = (e: MediaQueryListEvent | MediaQueryList) => {
            if (e.matches) setSidebarOpen(false);
        };
        handler(mq);
        mq.addEventListener("change", handler);
        return () => mq.removeEventListener("change", handler);
    }, [setSidebarOpen]);

    // Close sidebar on navigation on mobile
    useEffect(() => {
        if (window.innerWidth < 768) {
            setSidebarOpen(false);
        }
    }, [pathname, setSidebarOpen]);

    return (
        <>
            {/* Mobile overlay */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 z-30 bg-black/50 md:hidden animate-in fade-in duration-200"
                    onClick={() => setSidebarOpen(false)}
                />
            )}

            {/* Mobile hamburger — 44px tap target, visible bg */}
            <Button
                variant="ghost"
                size="icon"
                onClick={toggleSidebar}
                aria-label="Toggle navigation"
                className="fixed top-3 left-3 z-40 h-11 w-11 md:hidden rounded-lg bg-card/80 backdrop-blur-sm border border-border shadow-sm"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 12h18M3 6h18M3 18h18" />
                </svg>
            </Button>

            <aside
                className={cn(
                    "flex h-screen flex-col border-r border-border bg-card transition-all duration-300 z-40",
                    // Desktop: normal flow
                    "md:relative md:translate-x-0",
                    sidebarOpen ? "md:w-72" : "md:w-16",
                    // Mobile: overlay
                    "fixed md:static",
                    sidebarOpen ? "w-72 translate-x-0" : "w-72 -translate-x-full md:w-16 md:translate-x-0",
                )}
            >
                {/* Header */}
                <div className="flex h-14 items-center justify-between px-4">
                    {sidebarOpen && (
                        <Link href="/" className="flex items-center gap-2">
                            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold text-sm">
                                MC
                            </div>
                            <span className="font-semibold text-sm tracking-tight">
                                Mushroom Cloud
                            </span>
                        </Link>
                    )}
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={toggleSidebar}
                        aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
                        className="h-8 w-8 shrink-0 hidden md:flex"
                    >
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            {sidebarOpen ? (
                                <path d="m15 18-6-6 6-6" />
                            ) : (
                                <path d="m9 18 6-6-6-6" />
                            )}
                        </svg>
                    </Button>
                </div>

                <Separator />

                {/* Cmd+K hint */}
                {sidebarOpen && (
                    <div className="px-3 py-2">
                        <button
                            onClick={() => {
                                window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }));
                            }}
                            className="w-full flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent/50 transition-colors"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="11" cy="11" r="8" />
                                <path d="m21 21-4.3-4.3" />
                            </svg>
                            <span className="flex-1 text-left">Search...</span>
                            <kbd className="text-[10px] bg-muted px-1.5 py-0.5 rounded font-mono">⌘K</kbd>
                        </button>
                    </div>
                )}

                {/* Navigation */}
                <nav className="flex-1 overflow-y-auto px-2 py-3">
                    <div className="space-y-1">
                        <NavItem href="/" label="Dashboard" icon="⚡" active={pathname === "/"} collapsed={!sidebarOpen} />
                        <NavItem href="/tasks" label="Tasks" icon="📋" active={pathname === "/tasks"} collapsed={!sidebarOpen} />
                        <NavItem href="/calendar" label="Calendar" icon="📅" active={pathname === "/calendar"} collapsed={!sidebarOpen} />
                        <NavItem href="/crm" label="Clients" icon="👥" active={pathname === "/crm"} collapsed={!sidebarOpen} />
                        <NavItem href="/email" label="Email" icon="📧" active={pathname === "/email"} collapsed={!sidebarOpen} />
                        <NavItem href="/conflicts" label="Conflicts" icon="⚖️" active={pathname === "/conflicts"} collapsed={!sidebarOpen} />
                        <NavItem href="/analytics" label="Analytics" icon="📊" active={pathname === "/analytics"} collapsed={!sidebarOpen} />
                        <NavItem href="/workflows" label="Workflows" icon="🔄" active={pathname === "/workflows"} collapsed={!sidebarOpen} />
                        <NavItem href="/notifications" label="Notifications" icon="🔔" active={pathname === "/notifications"} collapsed={!sidebarOpen} />
                        <NavItem href="/search" label="Search" icon="🔍" active={pathname === "/search"} collapsed={!sidebarOpen} />
                        <NavItem href="/portal" label="Client Portal" icon="🌐" active={pathname === "/portal"} collapsed={!sidebarOpen} />
                        <NavItem href="/profile" label="Profile" icon="👤" active={pathname === "/profile"} collapsed={!sidebarOpen} />
                        <NavItem href="/settings" label="Settings" icon="⚙️" active={pathname === "/settings"} collapsed={!sidebarOpen} />
                        <NavItem href="/admin" label="Admin" icon="🛡️" active={pathname === "/admin"} collapsed={!sidebarOpen} />
                    </div>

                    {sidebarOpen && (
                        <>
                            <Separator className="my-3" />
                            <div className="mb-2 px-2">
                                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                    Cases
                                </span>
                            </div>
                            <NavItem href="/" label="All Cases" icon="📁" active={false} collapsed={false} />
                        </>
                    )}
                </nav>

                <Separator />

                {/* User + Theme */}
                <div className="flex items-center gap-2 p-4">
                    <StableUserButton />
                    {sidebarOpen && (
                        <span className="text-sm text-muted-foreground truncate flex-1">
                            Account
                        </span>
                    )}
                    <ThemeToggle />
                </div>
            </aside>
        </>
    );
}

// ---- Nav Item with Tooltip for collapsed state --------------------------

function NavItem({
    href,
    label,
    icon,
    active,
    collapsed,
    badge,
}: {
    href: string;
    label: string;
    icon?: string;
    active: boolean;
    collapsed: boolean;
    badge?: string;
}) {
    const linkContent = (
        <Link
            href={href}
            className={cn(
                "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
                active
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                collapsed && "justify-center",
            )}
        >
            {icon && <span className="text-base">{icon}</span>}
            {!collapsed && (
                <>
                    <span className="truncate flex-1">{label}</span>
                    {badge && (
                        <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                            {badge}
                        </Badge>
                    )}
                </>
            )}
        </Link>
    );

    if (collapsed) {
        return (
            <Tooltip>
                <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
                <TooltipContent side="right" className="text-xs">
                    {label}
                </TooltipContent>
            </Tooltip>
        );
    }

    return linkContent;
}
