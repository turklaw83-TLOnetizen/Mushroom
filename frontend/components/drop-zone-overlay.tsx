"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, usePathname } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

export function DropZoneOverlay() {
    const [isDragging, setIsDragging] = useState(false);
    const params = useParams();
    const pathname = usePathname();
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const caseId = params.id as string | undefined;

    // Only active on case pages
    const isOnCasePage = pathname.startsWith("/cases/") && !!caseId;

    const handleDragEnter = useCallback((e: DragEvent) => {
        e.preventDefault();
        if (!isOnCasePage) return;
        if (e.dataTransfer?.types?.includes("Files")) {
            setIsDragging(true);
        }
    }, [isOnCasePage]);

    const handleDragLeave = useCallback((e: DragEvent) => {
        e.preventDefault();
        // Only hide if leaving the window
        if (e.relatedTarget === null) {
            setIsDragging(false);
        }
    }, []);

    const handleDragOver = useCallback((e: DragEvent) => {
        e.preventDefault();
    }, []);

    const handleDrop = useCallback(async (e: DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        if (!isOnCasePage || !e.dataTransfer?.files?.length) return;

        const files = Array.from(e.dataTransfer.files);
        toast.info(`Uploading ${files.length} file${files.length > 1 ? "s" : ""}...`);

        try {
            const formData = new FormData();
            for (const file of files) {
                formData.append("files", file);
            }
            const token = await getToken();
            const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
            // Read CSRF token from cookie
            const csrfMatch = document.cookie.match(/(?:^|;\s*)mc-csrf=([^;]*)/);
            const csrfToken = csrfMatch ? decodeURIComponent(csrfMatch[1]) : "";
            const headers: Record<string, string> = {};
            if (token) headers["Authorization"] = `Bearer ${token}`;
            if (csrfToken) headers["X-CSRF-Token"] = csrfToken;

            const response = await fetch(`${baseUrl}/api/v1/cases/${caseId}/files`, {
                method: "POST",
                headers,
                credentials: "include",
                body: formData,
            });

            if (!response.ok) {
                throw new Error(`Upload failed (${response.status})`);
            }

            toast.success(`Uploaded ${files.length} file${files.length > 1 ? "s" : ""}`);
        } catch {
            toast.error("Failed to upload files");
        }
        queryClient.invalidateQueries({ queryKey: ["files", caseId] });
    }, [isOnCasePage, caseId, getToken, queryClient]);

    useEffect(() => {
        document.addEventListener("dragenter", handleDragEnter);
        document.addEventListener("dragleave", handleDragLeave);
        document.addEventListener("dragover", handleDragOver);
        document.addEventListener("drop", handleDrop);
        return () => {
            document.removeEventListener("dragenter", handleDragEnter);
            document.removeEventListener("dragleave", handleDragLeave);
            document.removeEventListener("dragover", handleDragOver);
            document.removeEventListener("drop", handleDrop);
        };
    }, [handleDragEnter, handleDragLeave, handleDragOver, handleDrop]);

    if (!isDragging) return null;

    return (
        <div className="fixed inset-0 z-[100] bg-primary/10 backdrop-blur-sm flex items-center justify-center pointer-events-none">
            <div className="bg-card border-2 border-dashed border-primary rounded-2xl p-12 text-center shadow-2xl">
                <div className="text-5xl mb-4">{"\uD83D\uDCC2"}</div>
                <p className="text-lg font-semibold">Drop files to upload</p>
                <p className="text-sm text-muted-foreground mt-1">
                    Files will be added to this case&apos;s library
                </p>
            </div>
        </div>
    );
}
