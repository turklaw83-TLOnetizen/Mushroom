// ---- FormDialog Component (zod v4 compatible) ---------------------------
// Reusable form dialog powered by react-hook-form + zod.
"use client";

import { type ReactNode, useEffect, useRef } from "react";
import { useForm, type DefaultValues, type Path, type FieldValues } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { type ZodType } from "zod";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

// ---- Field Config -------------------------------------------------------

export interface FieldConfig<T extends FieldValues> {
    name: Path<T>;
    label: string;
    type?: "text" | "number" | "textarea" | "select";
    placeholder?: string;
    required?: boolean;
    options?: { value: string; label: string }[];
}

// ---- Component ----------------------------------------------------------

interface FormDialogProps<T extends FieldValues> {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title: string;
    description?: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    schema: ZodType<any>;
    defaultValues: DefaultValues<T>;
    fields: FieldConfig<T>[];
    onSubmit: (data: T) => void | Promise<void>;
    submitLabel?: string;
    isLoading?: boolean;
    children?: ReactNode;
}

export function FormDialog<T extends FieldValues>({
    open,
    onOpenChange,
    title,
    description,
    schema,
    defaultValues,
    fields,
    onSubmit,
    submitLabel = "Save",
    isLoading = false,
}: FormDialogProps<T>) {
    const form = useForm<T>({
        // zod v4 has incompatible _input types with @hookform/resolvers
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        resolver: zodResolver(schema as any) as any,
        defaultValues,
    });
    const firstInputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);

    // Reset form and autofocus when dialog opens
    useEffect(() => {
        if (open) {
            form.reset(defaultValues);
            // Delay to ensure DOM is mounted
            const timer = setTimeout(() => firstInputRef.current?.focus(), 100);
            return () => clearTimeout(timer);
        }
    }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleSubmit = form.handleSubmit(async (data) => {
        await onSubmit(data);
        form.reset();
    });

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>{title}</DialogTitle>
                    {description && <DialogDescription>{description}</DialogDescription>}
                </DialogHeader>

                <form onSubmit={handleSubmit} className="space-y-4">
                    {fields.map((field, fieldIndex) => {
                        const error = form.formState.errors[field.name];
                        return (
                            <div key={String(field.name)} className="space-y-1.5">
                                <label className="text-sm font-medium">
                                    {field.label}
                                    {field.required && (
                                        <span className="text-destructive ml-0.5">*</span>
                                    )}
                                </label>

                                {field.type === "select" ? (
                                    <Select
                                        value={form.watch(field.name) as string}
                                        onValueChange={(val) => form.setValue(field.name, val as never)}
                                    >
                                        <SelectTrigger>
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {field.options?.map((opt) => (
                                                <SelectItem key={opt.value} value={opt.value}>
                                                    {opt.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                ) : field.type === "textarea" ? (
                                    <textarea
                                        {...form.register(field.name)}
                                        placeholder={field.placeholder}
                                        rows={3}
                                        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
                                    />
                                ) : field.type === "number" ? (
                                    <Input
                                        type="number"
                                        step="any"
                                        {...form.register(field.name, { valueAsNumber: true })}
                                        placeholder={field.placeholder}
                                    />
                                ) : (
                                    <Input
                                        {...form.register(field.name)}
                                        placeholder={field.placeholder}
                                        ref={(el) => {
                                            // Set ref for first text input for autofocus
                                            if (fieldIndex === 0 && field.type !== "select") {
                                                firstInputRef.current = el;
                                            }
                                            // Forward react-hook-form ref
                                            const { ref } = form.register(field.name);
                                            if (typeof ref === "function") ref(el);
                                        }}
                                    />
                                )}

                                {error && (
                                    <p className="text-xs text-destructive">
                                        {error.message as string}
                                    </p>
                                )}
                            </div>
                        );
                    })}

                    <DialogFooter>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                        >
                            Cancel
                        </Button>
                        <Button type="submit" disabled={isLoading}>
                            {isLoading ? "Saving..." : submitLabel}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
