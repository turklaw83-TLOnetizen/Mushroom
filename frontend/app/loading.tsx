// ---- Dashboard Loading State --------------------------------------------
// Shows stats row skeleton + table skeleton during dashboard page navigation.
import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardLoading() {
    return (
        <div className="space-y-6 p-6">
            {/* Page title */}
            <Skeleton className="h-8 w-48" />

            {/* Stats row: 4 metric cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-24 rounded-lg" />
                ))}
            </div>

            {/* Table skeleton: header + rows */}
            <div className="space-y-3">
                <Skeleton className="h-10 w-full rounded-md" />
                {Array.from({ length: 8 }).map((_, i) => (
                    <Skeleton key={i} className="h-14 w-full rounded-md" />
                ))}
            </div>
        </div>
    );
}
