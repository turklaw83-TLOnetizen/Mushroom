// ---- Tab Loading Skeleton -----------------------------------------------
// Reusable skeleton for case tab pages while data loads.
import { Skeleton } from "@/components/ui/skeleton";

export default function TabLoading() {
    return (
        <div className="p-6 space-y-6">
            {/* Header skeleton */}
            <div className="flex items-center justify-between">
                <div className="space-y-2">
                    <Skeleton className="h-6 w-48" />
                    <Skeleton className="h-4 w-32" />
                </div>
                <Skeleton className="h-9 w-28" />
            </div>
            {/* Table header */}
            <Skeleton className="h-10 w-full rounded-md" />
            {/* Table rows */}
            {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full rounded-md" />
            ))}
        </div>
    );
}
