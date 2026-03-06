// ---- StatusBadge Component -----------------------------------------------
// Universal status badge. Replaces 15+ duplicated badge implementations.
"use client";

import { Badge } from "@/components/ui/badge";
import { getStatusColor, formatLabel, type StatusDomain } from "@/lib/constants";
import { cn } from "@/lib/utils";

interface StatusBadgeProps {
    /** The status value (e.g., "pending", "signed", "high") */
    status: string;
    /** The domain determines which color map to use */
    domain?: StatusDomain;
    /** Override the display label (defaults to formatted status) */
    label?: string;
    /** Additional className */
    className?: string;
    /** Badge size — "sm" uses smaller text */
    size?: "sm" | "default";
}

export function StatusBadge({
    status,
    domain = "generic",
    label,
    className,
    size = "default",
}: StatusBadgeProps) {
    const colorClasses = getStatusColor(status, domain);
    const displayLabel = label ?? formatLabel(status);

    return (
        <Badge
            variant="outline"
            className={cn(
                colorClasses,
                size === "sm" && "text-[10px] px-1.5 py-0",
                className,
            )}
        >
            {displayLabel}
        </Badge>
    );
}
