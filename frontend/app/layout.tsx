import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { dark } from "@clerk/themes";
import { Toaster } from "sonner";

import { QueryProvider } from "@/lib/query-provider";
import { Sidebar } from "@/components/sidebar";
import { CommandPalette } from "@/components/command-palette";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { NotificationBell } from "@/components/notification-bell";
import { ShortcutsPanel } from "@/components/shortcuts-panel";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Project Mushroom Cloud",
  description: "Legal Intelligence Suite",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider
      appearance={{
        baseTheme: dark,
        variables: {
          colorPrimary: "#6366f1",
        },
      }}
    >
      <html lang="en" className="dark">
        <body className={`${inter.variable} font-sans antialiased`}>
          <QueryProvider>
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
            <Toaster
              theme="dark"
              position="bottom-right"
              toastOptions={{
                className: "border-border",
              }}
            />
          </QueryProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
