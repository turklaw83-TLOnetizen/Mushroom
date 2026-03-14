// ---- Sidebar Component (Responsive) ------------------------------------
// Grouped navigation with collapsible sections and lucide-react icons.
"use client";

import { useEffect, memo } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserButton, useUser } from "@clerk/nextjs";
import {
    LayoutDashboard,
    Sun,
    CheckSquare,
    Calendar,
    Users,
    FileInput,
    Mail,
    MessageSquare,
    CreditCard,
    FileSearch,
    Scale,
    BarChart3,
    Workflow,
    Bell,
    Search,
    Globe,
    User,
    Settings,
    ShieldCheck,
    ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/stores/ui-store";
import { useCases, type CaseItem } from "@/hooks/use-cases";
import { useNavCounts } from "@/hooks/use-nav-counts";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "@/components/ui/collapsible";
import { ThemeToggle } from "@/components/theme-toggle";

// ---- Navigation structure ------------------------------------------------

interface NavSectionDef {
    title: string;
    items: {
        href: string;
        label: string;
        icon: React.ComponentType<{ className?: string }>;
    }[];
}

const navSections: NavSectionDef[] = [
    {
        title: "Core",
        items: [
            { href: "/", label: "Dashboard", icon: LayoutDashboard },
            { href: "/brief", label: "Morning Brief", icon: Sun },
            { href: "/tasks", label: "Tasks", icon: CheckSquare },
            { href: "/calendar", label: "Calendar", icon: Calendar },
        ],
    },
    {
        title: "Case Management",
        items: [
            { href: "/crm", label: "Clients", icon: Users },
            { href: "/intake", label: "Intake", icon: FileInput },
            { href: "/conflicts", label: "Conflicts", icon: Scale },
            { href: "/discovery", label: "Discovery", icon: FileSearch },
        ],
    },
    {
        title: "Communication",
        items: [
            { href: "/email", label: "Email", icon: Mail },
            { href: "/comms", label: "Comms", icon: MessageSquare },
            { href: "/notifications", label: "Notifications", icon: Bell },
        ],
    },
    {
        title: "Finance",
        items: [
            { href: "/payments", label: "Payments", icon: CreditCard },
            { href: "/analytics", label: "Analytics", icon: BarChart3 },
        ],
    },
    {
        title: "Tools",
        items: [
            { href: "/workflows", label: "Workflows", icon: Workflow },
            { href: "/search", label: "Search", icon: Search },
            { href: "/portal", label: "Client Portal", icon: Globe },
        ],
    },
    {
        title: "Account",
        items: [
            { href: "/profile", label: "Profile", icon: User },
            { href: "/settings", label: "Settings", icon: Settings },
            { href: "/admin", label: "Admin", icon: ShieldCheck },
        ],
    },
];

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
    const pinnedCaseIds = useUIStore((s) => s.pinnedCaseIds);
    const pinCase = useUIStore((s) => s.pinCase);
    const unpinCase = useUIStore((s) => s.unpinCase);
    const { data: casesData, isLoading } = useCases();
    const { data: navCounts } = useNavCounts();

    // Map item labels to their notification counts
    const badgeCounts: Record<string, number> = {
        Tasks: navCounts?.tasks ?? 0,
        Comms: navCounts?.comms ?? 0,
        Notifications: navCounts?.notifications ?? 0,
    };

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
                                useUIStore.getState().setCommandPaletteOpen(true);
                            }}
                            className="w-full flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent/50 transition-colors"
                        >
                            <Search className="h-3.5 w-3.5" />
                            <span className="flex-1 text-left">Search...</span>
                            <kbd className="text-[10px] bg-muted px-1.5 py-0.5 rounded font-mono">&#x2318;K</kbd>
                        </button>
                    </div>
                )}

                {/* Navigation — Collapsible Groups */}
                <nav className="flex-1 overflow-y-auto px-2 py-3">
                    <div className="space-y-2">
                        {navSections.map((section) => {
                            // Check if any item in this section is active
                            const sectionHasActive = section.items.some((item) =>
                                item.href === "/"
                                    ? pathname === "/"
                                    : pathname.startsWith(item.href),
                            );

                            if (!sidebarOpen) {
                                // Collapsed mode: just show icons, no section headers
                                return (
                                    <div key={section.title} className="space-y-1">
                                        {section.items.map((item) => {
                                            const Icon = item.icon;
                                            const isActive =
                                                item.href === "/"
                                                    ? pathname === "/"
                                                    : pathname.startsWith(item.href);
                                            const count = badgeCounts[item.label] ?? 0;
                                            return (
                                                <Tooltip key={item.href}>
                                                    <TooltipTrigger asChild>
                                                        <Link
                                                            href={item.href}
                                                            className={cn(
                                                                "relative flex items-center justify-center rounded-md p-2 transition-colors",
                                                                isActive
                                                                    ? "bg-primary/10 text-primary"
                                                                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                                                            )}
                                                        >
                                                            <Icon className="h-4 w-4" />
                                                            {count > 0 && (
                                                                <span className="absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-primary ring-2 ring-card" />
                                                            )}
                                                        </Link>
                                                    </TooltipTrigger>
                                                    <TooltipContent side="right" className="text-xs">
                                                        {item.label}
                                                        {count > 0 && ` (${count})`}
                                                    </TooltipContent>
                                                </Tooltip>
                                            );
                                        })}
                                    </div>
                                );
                            }

                            // Expanded mode: collapsible sections
                            return (
                                <Collapsible key={section.title} defaultOpen={true}>
                                    <CollapsibleTrigger className="flex w-full items-center gap-1.5 px-2 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wider hover:text-foreground transition-colors group">
                                        <ChevronDown className="h-3 w-3 transition-transform group-data-[state=closed]:-rotate-90" />
                                        {section.title}
                                        {sectionHasActive && (
                                            <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary" />
                                        )}
                                    </CollapsibleTrigger>
                                    <CollapsibleContent>
                                        <div className="space-y-0.5 mt-0.5">
                                            {section.items.map((item) => {
                                                const Icon = item.icon;
                                                const isActive =
                                                    item.href === "/"
                                                        ? pathname === "/"
                                                        : pathname.startsWith(item.href);
                                                const count = badgeCounts[item.label] ?? 0;
                                                return (
                                                    <Link
                                                        key={item.href}
                                                        href={item.href}
                                                        className={cn(
                                                            "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
                                                            isActive
                                                                ? "bg-primary/10 text-primary font-medium"
                                                                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                                                        )}
                                                    >
                                                        <Icon className="h-4 w-4 shrink-0" />
                                                        <span className="truncate">{item.label}</span>
                                                        {count > 0 && (
                                                            <span className="ml-auto text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-primary text-primary-foreground min-w-[18px] text-center">
                                                                {count > 99 ? "99+" : count}
                                                            </span>
                                                        )}
                                                    </Link>
                                                );
                                            })}
                                        </div>
                                    </CollapsibleContent>
                                </Collapsible>
                            );
                        })}
                    </div>

                    {sidebarOpen && (
                        <>
                            <Separator className="my-3" />
                            <div className="mb-2 px-2">
                                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                    Cases
                                </span>
                            </div>
                            <div className="space-y-0.5">
                                {isLoading ? (
                                    Array.from({ length: 3 }).map((_, i) => (
                                        <Skeleton key={i} className="h-8 w-full rounded-md" />
                                    ))
                                ) : casesData?.items?.length ? (
                                    (() => {
                                        const allCases = casesData.items.slice(0, 15);
                                        const pinned = allCases.filter((c: CaseItem) => pinnedCaseIds.includes(c.id));
                                        const unpinned = allCases.filter((c: CaseItem) => !pinnedCaseIds.includes(c.id));
                                        return (
                                            <>
                                                {pinned.map((c: CaseItem) => (
                                                    <CaseNavItem
                                                        key={c.id}
                                                        caseItem={c}
                                                        active={pathname.startsWith(`/cases/${c.id}`)}
                                                        isPinned={true}
                                                        onTogglePin={() => unpinCase(c.id)}
                                                    />
                                                ))}
                                                {pinned.length > 0 && unpinned.length > 0 && (
                                                    <Separator className="my-1" />
                                                )}
                                                {unpinned.map((c: CaseItem) => (
                                                    <CaseNavItem
                                                        key={c.id}
                                                        caseItem={c}
                                                        active={pathname.startsWith(`/cases/${c.id}`)}
                                                        isPinned={false}
                                                        onTogglePin={() => pinCase(c.id)}
                                                    />
                                                ))}
                                            </>
                                        );
                                    })()
                                ) : (
                                    <p className="px-2 text-xs text-muted-foreground">
                                        No cases yet
                                    </p>
                                )}
                            </div>
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

// ---- Case Nav Item with pin/unpin on hover ------------------------------

function CaseNavItem({
    caseItem,
    active,
    isPinned,
    onTogglePin,
}: {
    caseItem: CaseItem;
    active: boolean;
    isPinned: boolean;
    onTogglePin: () => void;
}) {
    return (
        <Link
            href={`/cases/${caseItem.id}`}
            className={cn(
                "group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
                active
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
            )}
        >
            {isPinned && <span className="text-xs shrink-0">&#x1F4CC;</span>}
            <span className="truncate flex-1">{caseItem.name}</span>
            {caseItem.phase && (
                <Badge variant="secondary" className="text-[10px] px-1.5 py-0 shrink-0">
                    {caseItem.phase}
                </Badge>
            )}
            <button
                onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onTogglePin();
                }}
                className="opacity-0 group-hover:opacity-100 transition-opacity text-xs shrink-0"
                title={isPinned ? "Unpin" : "Pin"}
            >
                {isPinned ? "&#x1F4CC;" : "&#x1F4CD;"}
            </button>
        </Link>
    );
}
