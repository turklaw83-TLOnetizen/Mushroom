"use client";
import { TabErrorFallback } from "@/components/shared/tab-error";
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
    return <TabErrorFallback error={error} reset={reset} tabName="Timeline" />;
}
