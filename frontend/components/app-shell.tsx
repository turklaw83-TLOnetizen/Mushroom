// ---- App Shell ----------------------------------------------------------
// Conditionally renders sidebar and chrome based on route.
// Auth pages (/sign-in, /sign-up) get a clean layout without navigation.
"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { NotificationBell } from "@/components/notification-bell";
import { CommandPalette } from "@/components/command-palette";
import { ShortcutsPanel } from "@/components/shortcuts-panel";
import { ServiceWorkerRegistrar } from "@/components/sw-registrar";
import { UploadIndicator } from "@/components/upload-indicator";

const AUTH_ROUTES = ["/sign-in", "/sign-up"];

export function AppShell({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const isAuthPage = AUTH_ROUTES.some((r) => pathname.startsWith(r));

    if (isAuthPage) {
        // Clean layout for auth pages — no sidebar, no nav chrome
        return (
            <>
                {children}
                <ServiceWorkerRegistrar />
            </>
        );
    }

    // Full app layout with sidebar and navigation
    return (
        <>
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
            <ServiceWorkerRegistrar />
            <UploadIndicator />
        </>
    );
}
