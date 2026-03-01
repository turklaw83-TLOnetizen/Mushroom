// ---- useRole Hook -------------------------------------------------------
// Reads the user's role from Clerk publicMetadata and provides
// role-checking helpers for conditional UI rendering.
"use client";

import { useUser } from "@clerk/nextjs";
import { useMemo } from "react";

export type UserRole = "admin" | "attorney" | "paralegal" | "viewer";

interface RoleInfo {
    role: UserRole;
    isAdmin: boolean;
    isAttorney: boolean;
    canEdit: boolean;    // admin or attorney
    canDelete: boolean;  // admin only
    isLoading: boolean;
}

export function useRole(): RoleInfo {
    const { user, isLoaded } = useUser();

    return useMemo(() => {
        if (!isLoaded || !user) {
            return {
                role: "viewer" as UserRole,
                isAdmin: false,
                isAttorney: false,
                canEdit: false,
                canDelete: false,
                isLoading: !isLoaded,
            };
        }

        const role = (user.publicMetadata?.role as UserRole) || "attorney";

        return {
            role,
            isAdmin: role === "admin",
            isAttorney: role === "attorney",
            canEdit: role === "admin" || role === "attorney",
            canDelete: role === "admin",
            isLoading: false,
        };
    }, [user, isLoaded]);
}
