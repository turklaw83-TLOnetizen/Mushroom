// ---- User Profile Page --------------------------------------------------
// User preferences, role info, and session management.
"use client";

import { useUser } from "@clerk/nextjs";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export default function ProfilePage() {
    const { user, isLoaded } = useUser();

    if (!isLoaded) {
        return (
            <div className="p-6 md:p-8 max-w-3xl mx-auto space-y-6">
                <Skeleton className="h-8 w-48" />
                <Skeleton className="h-40 w-full rounded-lg" />
                <Skeleton className="h-40 w-full rounded-lg" />
            </div>
        );
    }

    return (
        <div className="p-6 md:p-8 max-w-3xl mx-auto space-y-6">
            <h1 className="text-2xl font-bold tracking-tight">Profile</h1>

            {/* User Info */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Account</CardTitle>
                    <CardDescription>Your Clerk account details</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                    <div className="flex items-center gap-4">
                        {user?.imageUrl && (
                            <img
                                src={user.imageUrl}
                                alt="Avatar"
                                className="h-16 w-16 rounded-full border"
                            />
                        )}
                        <div>
                            <p className="font-medium">
                                {user?.fullName || user?.firstName || "User"}
                            </p>
                            <p className="text-sm text-muted-foreground">
                                {user?.primaryEmailAddress?.emailAddress}
                            </p>
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-sm pt-2">
                        <div>
                            <p className="text-muted-foreground text-xs">User ID</p>
                            <p className="font-mono text-xs">{user?.id}</p>
                        </div>
                        <div>
                            <p className="text-muted-foreground text-xs">Created</p>
                            <p className="font-mono text-xs">
                                {user?.createdAt ? new Date(user.createdAt).toLocaleDateString() : "—"}
                            </p>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Role & Permissions */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Role & Permissions</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex items-center gap-2">
                        <Badge className="text-xs">
                            {(user?.publicMetadata as Record<string, string>)?.role || "attorney"}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                            Set by organization admin
                        </span>
                    </div>
                    <div className="mt-4 grid grid-cols-2 gap-2">
                        {["View Cases", "Edit Cases", "Run Analysis", "Export Documents", "Manage Billing", "Admin Access"].map((perm) => (
                            <div key={perm} className="flex items-center gap-2 text-xs">
                                <span className="text-green-400" aria-hidden="true">✓</span>
                                <span>{perm}</span>
                            </div>
                        ))}
                    </div>
                </CardContent>
            </Card>

            {/* Sessions */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Active Sessions</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex items-center gap-3 py-2">
                        <span className="text-lg" aria-hidden="true">🖥️</span>
                        <div>
                            <p className="text-sm font-medium">Current Session</p>
                            <p className="text-xs text-muted-foreground">
                                {typeof window !== "undefined" ? window.navigator.userAgent.split(" ").slice(-2).join(" ") : "Browser"}
                            </p>
                        </div>
                        <Badge variant="outline" className="ml-auto text-[10px] text-green-400">
                            Active
                        </Badge>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
