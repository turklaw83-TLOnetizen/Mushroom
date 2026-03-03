// ---- Scrollable Tabs with Arrow Indicators ------------------------------
// Wraps tab navigation in a scroll container that shows left/right arrow
// buttons and gradient fade when content overflows.
"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface Tab {
    label: string;
    href: string;
}

interface ScrollableTabsProps {
    tabs: Tab[];
    basePath: string;
    activeHref: string;
    onPrefetch?: (href: string) => void;
}

export function ScrollableTabs({ tabs, basePath, activeHref, onPrefetch }: ScrollableTabsProps) {
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

            {/* Scrollable tabs */}
            <nav
                ref={scrollRef}
                className="flex gap-0 -mb-px overflow-x-auto scrollbar-none"
            >
                {tabs.map((tab) => {
                    const tabPath = `${basePath}${tab.href}`;
                    const isActive =
                        tab.href === ""
                            ? activeHref === basePath
                            : activeHref.startsWith(tabPath);

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
