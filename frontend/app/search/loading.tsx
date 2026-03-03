// ---- Search Page Loading Skeleton ----------------------------------------
import { Skeleton } from "@/components/ui/skeleton";

export default function SearchLoading() {
    return (
        <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-6">
            {/* Header */}
            <div className="space-y-2">
                <Skeleton className="h-7 w-24" />
                <Skeleton className="h-4 w-64" />
            </div>

            {/* Search input */}
            <Skeleton className="h-12 w-full rounded-lg" />

            {/* Result sections */}
            <div className="space-y-6 pt-4">
                {/* Section header */}
                <div className="space-y-2">
                    <Skeleton className="h-4 w-32" />
                    {Array.from({ length: 3 }).map((_, i) => (
                        <Skeleton key={i} className="h-16 w-full rounded-lg" />
                    ))}
                </div>
                <div className="space-y-2">
                    <Skeleton className="h-4 w-28" />
                    {Array.from({ length: 2 }).map((_, i) => (
                        <Skeleton key={i} className="h-16 w-full rounded-lg" />
                    ))}
                </div>
            </div>
        </div>
    );
}
