// ---- Scrollable Tabs with Arrow Indicators + Grouped Dropdowns ----------
// Wraps tab navigation in a scroll container that shows left/right arrow
// buttons and gradient fade when content overflows. Supports dropdown groups
// for organizing many tabs into a compact tab bar.
"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
    DropdownMenu,
    DropdownMenuTrigger,
    DropdownMenuContent,
    DropdownMenuItem,
} from "@/components/ui/dropdown-menu";

export interface Tab {
    label: string;
    href: string;
}

export interface TabGroup {
    label: string;
    tabs: Tab[];
}

interface ScrollableTabsProps {
    tabs: Tab[];
    groups?: TabGroup[];
    basePath: string;
    activeHref: string;
    onPrefetch?: (href: string) => void;
}

export function ScrollableTabs({ tabs, groups, basePath, activeHref, onPrefetch }: ScrollableTabsProps) {
    const router = useRouter();
    const scrollRef = useRef<HTMLDivElement>(null);
    const [canScrollLeft, setCanScrollLeft] = useState(false);
    const [canScrollRight, setCanScrollRight] = useState(false);

    const checkScroll = useCallback(() => {
        const el = scrollRef.current;
        if (!el) return;
        setCanScrollLeft(el.scrollLeft > 4);
        setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
    }, []);

    useEffect(() => {
        checkScroll();
        const el = scrollRef.current;
        if (!el) return;
        el.addEventListener("scroll", checkScroll, { passive: true });
        const ro = new ResizeObserver(checkScroll);
        ro.observe(el);
        return () => {
            el.removeEventListener("scroll", checkScroll);
            ro.disconnect();
        };
    }, [checkScroll]);

    const scroll = (direction: "left" | "right") => {
        const el = scrollRef.current;
        if (!el) return;
        el.scrollBy({ left: direction === "left" ? -200 : 200, behavior: "smooth" });
    };

    /** Check if a tab href is active */
    const isTabActive = (tabHref: string) => {
        const tabPath = `${basePath}${tabHref}`;
        return tabHref === ""
            ? activeHref === basePath
            : activeHref.startsWith(tabPath);
    };

    /** Check if any tab within a group is active */
    const isGroupActive = (group: TabGroup) =>
        group.tabs.some((tab) => isTabActive(tab.href));

    /** Navigate between tabs with Left/Right arrow keys */
    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
            // Don't intercept if the user is typing in a form element
            const tag = (e.target as HTMLElement).tagName;
            if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

            e.preventDefault();

            // Build a flat list of all navigable tab hrefs (primary + grouped)
            const allHrefs = [
                ...tabs.map((t) => t.href),
                ...(groups?.flatMap((g) => g.tabs.map((t) => t.href)) || []),
            ];

            const currentIdx = allHrefs.findIndex((href) => isTabActive(href));
            if (currentIdx === -1) return;

            const nextIdx =
                e.key === "ArrowRight"
                    ? Math.min(currentIdx + 1, allHrefs.length - 1)
                    : Math.max(currentIdx - 1, 0);

            if (nextIdx !== currentIdx) {
                router.push(`${basePath}${allHrefs[nextIdx]}`);
            }
        },
        // isTabActive is stable (depends on basePath + activeHref captured in closure)
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [tabs, groups, basePath, activeHref, router],
    );

    return (
        <div className="relative">
            {/* Left arrow */}
            {canScrollLeft && (
                <div className="absolute left-0 top-0 bottom-0 z-10 flex items-center">
                    <div className="w-10 h-full bg-gradient-to-r from-card/90 to-transparent flex items-center pl-0.5">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 rounded-full bg-muted/80 hover:bg-muted shadow-sm"
                            onClick={() => scroll("left")}
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
                        </Button>
                    </div>
                </div>
            )}

            {/* Scrollable tabs — focusable for keyboard arrow navigation */}
            <nav
                ref={scrollRef}
                tabIndex={0}
                onKeyDown={handleKeyDown}
                className="flex gap-0 -mb-px overflow-x-auto scrollbar-none outline-none focus-visible:ring-1 focus-visible:ring-primary/40 rounded-sm"
            >
                {/* Primary tabs */}
                {tabs.map((tab) => {
                    const tabPath = `${basePath}${tab.href}`;
                    const isActive = isTabActive(tab.href);

                    return (
                        <Link
                            key={tab.href}
                            href={tabPath}
                            onMouseEnter={() => onPrefetch?.(tab.href)}
                            className={cn(
                                "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap shrink-0",
                                isActive
                                    ? "border-primary text-primary"
                                    : "border-transparent text-muted-foreground hover:text-foreground hover:border-border",
                            )}
                        >
                            {tab.label}
                        </Link>
                    );
                })}

                {/* Dropdown groups */}
                {groups?.map((group) => {
                    const groupActive = isGroupActive(group);
                    // Find the active child tab label for display
                    const activeChild = groupActive
                        ? group.tabs.find((t) => isTabActive(t.href))
                        : null;

                    return (
                        <DropdownMenu key={group.label}>
                            <DropdownMenuTrigger asChild>
                                <button
                                    className={cn(
                                        "flex items-center gap-1 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap shrink-0 outline-none",
                                        groupActive
                                            ? "border-primary text-primary"
                                            : "border-transparent text-muted-foreground hover:text-foreground hover:border-border",
                                    )}
                                >
                                    {activeChild ? activeChild.label : group.label}
                                    <ChevronDown className="h-3.5 w-3.5 opacity-60" />
                                </button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="start" className="min-w-[180px]">
                                {group.tabs.map((tab) => {
                                    const tabPath = `${basePath}${tab.href}`;
                                    const isActive = isTabActive(tab.href);

                                    return (
                                        <DropdownMenuItem key={tab.href} asChild>
                                            <Link
                                                href={tabPath}
                                                onMouseEnter={() => onPrefetch?.(tab.href)}
                                                className={cn(
                                                    "w-full cursor-pointer",
                                                    isActive && "bg-accent font-medium",
                                                )}
                                            >
                                                {tab.label}
                                            </Link>
                                        </DropdownMenuItem>
                                    );
                                })}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    );
                })}
            </nav>

            {/* Right arrow */}
            {canScrollRight && (
                <div className="absolute right-0 top-0 bottom-0 z-10 flex items-center">
                    <div className="w-10 h-full bg-gradient-to-l from-card/90 to-transparent flex items-center justify-end pr-0.5">
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 rounded-full bg-muted/80 hover:bg-muted shadow-sm"
                            onClick={() => scroll("right")}
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m9 18 6-6-6-6"/></svg>
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}
