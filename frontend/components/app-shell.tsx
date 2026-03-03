// ---- App Shell ----------------------------------------------------------
// Conditionally renders sidebar + chrome for app routes, or bare layout
// for auth routes (sign-in, sign-up). Prevents sidebar API calls on auth pages.
"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { NotificationBell } from "@/components/notification-bell";
import { CommandPalette } from "@/components/command-palette";
import { ShortcutsPanel } from "@/components/shortcuts-panel";
import { TooltipProvider } from "@/components/ui/tooltip";

const AUTH_ROUTES = ["/sign-in", "/sign-up"];

export function AppShell({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const isAuthPage = AUTH_ROUTES.some((r) => pathname.startsWith(r));

    if (isAuthPage) {
        return <>{children}</>;
    }

    return (
        <TooltipProvider delayDuration={0}>
            <div className="flex h-screen overflow-hidden bg-background text-foreground">
                <Sidebar />
                <main className="flex-1 overflow-y-auto flex flex-col">
                    <div className="flex items-center justify-between">
                        <Breadcrumbs />
                        <div className="pr-4">
                            <NotificationBell />
                        </div>
                    </div>
                    <div className="flex-1">{children}</div>
                </main>
            </div>
            <CommandPalette />
            <ShortcutsPanel />
        </TooltipProvider>
    );
}
