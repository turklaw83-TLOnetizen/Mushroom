// ---- Mock Exam Error Boundary -------------------------------------------
"use client";

import { TabErrorFallback } from "@/components/shared/tab-error";

export default function MockExamError({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    return <TabErrorFallback error={error} reset={reset} tabName="Mock Exam" />;
}
