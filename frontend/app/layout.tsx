import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { dark } from "@clerk/themes";
import { Toaster } from "sonner";

import { initSentry } from "@/lib/sentry";
import { QueryProvider } from "@/lib/query-provider";
import { AppShell } from "@/components/app-shell";

initSentry();
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
        <head>
          <link rel="manifest" href="/manifest.json" />
          <meta name="theme-color" content="#6366f1" />
          <link rel="apple-touch-icon" href="/icon-192.png" />
        </head>
        <body className={`${inter.variable} font-sans antialiased`}>
          <QueryProvider>
            <AppShell>{children}</AppShell>
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
