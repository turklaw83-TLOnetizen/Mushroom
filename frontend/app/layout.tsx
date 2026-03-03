import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { QueryProvider } from "@/lib/query-provider";
import { ThemeAwareClerk } from "@/components/theme-aware-clerk";
import { ThemeAwareToaster } from "@/components/theme-aware-toaster";
import { AppShell } from "@/components/app-shell";
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
        <html lang="en" suppressHydrationWarning>
            <head>
                {/* Inline script to set theme class before React hydrates (prevents flash) */}
                <script
                    dangerouslySetInnerHTML={{
                        __html: `
              try {
                var stored = JSON.parse(localStorage.getItem('mc-ui-store') || '{}');
                var theme = (stored.state && stored.state.theme) || 'dark';
                document.documentElement.classList.toggle('dark', theme === 'dark');
              } catch(e) {
                document.documentElement.classList.add('dark');
              }
            `,
                    }}
                />
            </head>
            <body className={`${inter.variable} font-sans antialiased`}>
                <ThemeAwareClerk>
                    <QueryProvider>
                        <AppShell>{children}</AppShell>
                        <ThemeAwareToaster />
                    </QueryProvider>
                </ThemeAwareClerk>
            </body>
        </html>
    );
}
