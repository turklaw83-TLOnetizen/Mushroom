// ---- Case Loading State -------------------------------------------------
import { Skeleton } from "@/components/ui/skeleton";

export default function CaseLoading() {
    return (
        <div className="space-y-4 p-6">
            <div className="flex items-center gap-3">
                <Skeleton className="h-7 w-48" />
                <Skeleton className="h-6 w-20 rounded-full" />
            </div>
            <Skeleton className="h-4 w-64" />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
                {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-28 rounded-lg" />
                ))}
            </div>
        </div>
    );
}
