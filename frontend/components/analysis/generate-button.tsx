// ---- Generate Button (On-Demand AI Generation) --------------------------
// Trigger button for on-demand AI content generation.
// Shows loading state and displays result inline when complete.
"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { MarkdownContent } from "./markdown-content";
import { ResultSection } from "./result-section";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface GenerateButtonProps {
    caseId: string;
    prepId: string | null;
    /** API path suffix after /generate/ (e.g., "witness-prep", "client-report") */
    endpoint: string;
    /** Display label */
    label: string;
    /** Icon emoji */
    icon?: string;
    /** Request body to send (e.g., { witness_name: "..." }) */
    body?: Record<string, unknown>;
    /** Key for extracting the result from the response (e.g., "witness_prep") */
    resultKey?: string;
    /** Optional existing content to display (avoids re-generation) */
    existingContent?: string | null;
    /** Empty state message */
    emptyMessage?: string;
    /** Callback after successful generation */
    onSuccess?: () => void;
}

export function GenerateButton({
    caseId,
    prepId,
    endpoint,
    label,
    icon = "✨",
    body = {},
    resultKey,
    existingContent,
    emptyMessage,
    onSuccess,
}: GenerateButtonProps) {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();
    const [generatedContent, setGeneratedContent] = useState<string | null>(null);

    const displayContent = generatedContent ?? existingContent ?? null;

    const mutation = useMutation({
        mutationFn: async () => {
            const data = await api.post<{ status: string; result: Record<string, unknown> }>(
                `/cases/${caseId}/preparations/${prepId}/generate/${endpoint}`,
                body,
                { getToken },
            );
            return data;
        },
        onSuccess: (data) => {
            // Extract result content
            const result = data.result;
            let content: string;

            if (resultKey && result[resultKey]) {
                content = typeof result[resultKey] === "string"
                    ? result[resultKey] as string
                    : JSON.stringify(result[resultKey], null, 2);
            } else {
                // Try common keys
                const firstKey = Object.keys(result)[0];
                const val = firstKey ? result[firstKey] : result;
                content = typeof val === "string" ? val : JSON.stringify(val, null, 2);
            }

            setGeneratedContent(content);

            // Invalidate prep state to refresh across tabs
            queryClient.invalidateQueries({
                queryKey: ["cases", caseId, "prep-state", prepId],
            });

            onSuccess?.();
        },
    });

    if (!prepId) return null;

    return (
        <div className="space-y-4">
            <ResultSection
                title={label}
                icon={icon}
                isEmpty={!displayContent}
                emptyMessage={emptyMessage || `Click Generate to create ${label.toLowerCase()}.`}
            >
                {displayContent && <MarkdownContent content={displayContent} />}
            </ResultSection>

            <div className="flex items-center gap-3">
                <Button
                    size="sm"
                    onClick={() => mutation.mutate()}
                    disabled={mutation.isPending || !prepId}
                    variant={displayContent ? "outline" : "default"}
                >
                    {mutation.isPending ? (
                        <span className="flex items-center gap-2">
                            <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                            Generating...
                        </span>
                    ) : displayContent ? (
                        "Regenerate"
                    ) : (
                        `Generate ${label}`
                    )}
                </Button>

                {mutation.isError && (
                    <p className="text-xs text-red-400">
                        Generation failed. Please try again.
                    </p>
                )}
            </div>
        </div>
    );
}

// ---- Generate With Options -----------------------------------------------
// Extended version with input fields for parameterized generation.

interface GenerateWithInputProps extends Omit<GenerateButtonProps, "body"> {
    /** Input fields to show before generation */
    fields: Array<{
        key: string;
        label: string;
        placeholder?: string;
        required?: boolean;
        type?: "text" | "select";
        options?: Array<{ value: string; label: string }>;
    }>;
}

export function GenerateWithInput({
    fields,
    ...buttonProps
}: GenerateWithInputProps) {
    const [values, setValues] = useState<Record<string, string>>(() => {
        const defaults: Record<string, string> = {};
        fields.forEach((f) => {
            if (f.type === "select" && f.options?.[0]) {
                defaults[f.key] = f.options[0].value;
            } else {
                defaults[f.key] = "";
            }
        });
        return defaults;
    });

    const requiredFilled = fields
        .filter((f) => f.required)
        .every((f) => values[f.key]?.trim());

    return (
        <div className="space-y-4">
            <Card className="bg-accent/20">
                <CardContent className="py-3 space-y-3">
                    {fields.map((field) => (
                        <div key={field.key}>
                            <label className="text-xs font-medium text-muted-foreground mb-1 block">
                                {field.label}
                                {field.required && <span className="text-red-400 ml-0.5">*</span>}
                            </label>
                            {field.type === "select" && field.options ? (
                                <select
                                    value={values[field.key] || ""}
                                    onChange={(e) =>
                                        setValues((prev) => ({ ...prev, [field.key]: e.target.value }))
                                    }
                                    className="w-full rounded-md border border-input bg-transparent px-3 py-1.5 text-sm"
                                >
                                    {field.options.map((opt) => (
                                        <option key={opt.value} value={opt.value}>
                                            {opt.label}
                                        </option>
                                    ))}
                                </select>
                            ) : (
                                <input
                                    type="text"
                                    value={values[field.key] || ""}
                                    onChange={(e) =>
                                        setValues((prev) => ({ ...prev, [field.key]: e.target.value }))
                                    }
                                    placeholder={field.placeholder}
                                    className="w-full rounded-md border border-input bg-transparent px-3 py-1.5 text-sm placeholder:text-muted-foreground"
                                />
                            )}
                        </div>
                    ))}
                </CardContent>
            </Card>

            <GenerateButton
                {...buttonProps}
                body={values}
            />
        </div>
    );
}
