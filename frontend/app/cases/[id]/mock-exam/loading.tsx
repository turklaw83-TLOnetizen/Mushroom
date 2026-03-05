// ---- Mock Exam Loading Skeleton -----------------------------------------
import { Skeleton } from "@/components/ui/skeleton";

export default function MockExamLoading() {
    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <Skeleton className="h-8 w-56" />
                <Skeleton className="h-9 w-32" />
            </div>
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
        </div>
    );
}
