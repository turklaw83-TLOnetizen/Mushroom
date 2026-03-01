"use client";

import { useUser } from "@clerk/nextjs";

const INITIAL_ADMIN_EMAIL = "daniel@turklaylaw.com";

export function useIsAdmin(): boolean {
    const { user } = useUser();
    return user?.primaryEmailAddress?.emailAddress?.toLowerCase() === INITIAL_ADMIN_EMAIL;
}

export function AdminGate({ children }: { children: React.ReactNode }) {
    const isAdmin = useIsAdmin();

    if (!isAdmin) {
        return (
            <div className="flex items-center justify-center min-h-[50vh]">
                <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-8 text-center max-w-md">
                    <div className="text-4xl mb-4">🔒</div>
                    <h2 className="text-xl font-bold text-white mb-2">Admin Access Required</h2>
                    <p className="text-white/60 text-sm">
                        This section requires admin privileges. Contact{" "}
                        <span className="text-indigo-400">{INITIAL_ADMIN_EMAIL}</span> for access.
                    </p>
                </div>
            </div>
        );
    }

    return <>{children}</>;
}

export function ApprovedUserGate({ children }: { children: React.ReactNode }) {
    const { user, isLoaded } = useUser();

    if (!isLoaded) return null;

    if (!user) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="rounded-xl border border-white/10 bg-gray-900 p-8 text-center max-w-md">
                    <div className="text-4xl mb-4">🔐</div>
                    <h2 className="text-xl font-bold text-white mb-2">Authentication Required</h2>
                    <p className="text-white/60 text-sm">Please sign in to continue.</p>
                </div>
            </div>
        );
    }

    return <>{children}</>;
}
