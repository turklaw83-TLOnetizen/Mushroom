// ---- Case Loading State -------------------------------------------------
// Shows header bar + tab bar skeleton + content area during case page navigation.
import { Skeleton } from "@/components/ui/skeleton";

export default function CaseLoading() {
    return (
        <div className="space-y-6 p-6">
            {/* Header bar: case title + status badge */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Skeleton className="h-7 w-56" />
                    <Skeleton className="h-6 w-20 rounded-full" />
                </div>
                <Skeleton className="h-9 w-28" />
            </div>

            {/* Tab bar skeleton */}
            <div className="flex gap-2 border-b border-border pb-2">
                {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-8 w-24 rounded-md" />
                ))}
            </div>

            {/* Content area skeleton */}
            <div className="space-y-3">
                <Skeleton className="h-5 w-40" />
                {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full rounded-lg" />
                ))}
            </div>
        </div>
    );
}
