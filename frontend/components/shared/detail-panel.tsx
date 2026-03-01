// ---- Detail Panel Component ---------------------------------------------
// Expandable detail/edit view for list items (witnesses, evidence, documents).
"use client";

import { useState, type ReactNode } from "react";
import { useForm, type FieldValues, type DefaultValues, type Path } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { type ZodType } from "zod";
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetFooter,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface DetailField<T extends FieldValues> {
    name: Path<T>;
    label: string;
    type?: "text" | "textarea" | "number" | "select" | "readonly";
    placeholder?: string;
    options?: { value: string; label: string }[];
}

interface DetailPanelProps<T extends FieldValues> {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title: string;
    description?: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    schema: ZodType<any>;
    values: T;
    fields: DetailField<T>[];
    onSave: (data: T) => void | Promise<void>;
    onDelete?: () => void | Promise<void>;
    readOnly?: boolean;
    isLoading?: boolean;
    children?: ReactNode;
}

export function DetailPanel<T extends FieldValues>({
    open,
    onOpenChange,
    title,
    description,
    schema,
    values,
    fields,
    onSave,
    onDelete,
    readOnly = false,
    isLoading = false,
}: DetailPanelProps<T>) {
    const [isEditing, setIsEditing] = useState(false);

    const form = useForm<T>({
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        resolver: zodResolver(schema as any) as any,
        defaultValues: values as DefaultValues<T>,
    });

    const handleSave = form.handleSubmit(async (data) => {
        await onSave(data);
        setIsEditing(false);
    });

    // Reset form when values change
    const handleOpenChange = (newOpen: boolean) => {
        if (newOpen) {
            form.reset(values as DefaultValues<T>);
            setIsEditing(false);
        }
        onOpenChange(newOpen);
    };

    return (
        <Sheet open={open} onOpenChange={handleOpenChange}>
            <SheetContent className="sm:max-w-md overflow-y-auto">
                <SheetHeader>
                    <SheetTitle>{title}</SheetTitle>
                    {description && <SheetDescription>{description}</SheetDescription>}
                </SheetHeader>

                <form onSubmit={handleSave} className="space-y-4 py-4">
                    {fields.map((field) => {
                        const error = form.formState.errors[field.name];
                        const isReadonlyField = field.type === "readonly" || (!isEditing && !readOnly);

                        return (
                            <div key={String(field.name)} className="space-y-1.5">
                                <label className="text-sm font-medium text-muted-foreground">
                                    {field.label}
                                </label>

                                {isReadonlyField || readOnly ? (
                                    <p className="text-sm py-1">
                                        {String(values[field.name] ?? "—")}
                                    </p>
                                ) : field.type === "textarea" ? (
                                    <textarea
                                        {...form.register(field.name)}
                                        placeholder={field.placeholder}
                                        rows={4}
                                        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
                                    />
                                ) : field.type === "select" ? (
                                    <select
                                        {...form.register(field.name)}
                                        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                                    >
                                        {field.options?.map((opt) => (
                                            <option key={opt.value} value={opt.value}>
                                                {opt.label}
                                            </option>
                                        ))}
                                    </select>
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
                                    />
                                )}

                                {error && (
                                    <p className="text-xs text-destructive">{error.message as string}</p>
                                )}
                            </div>
                        );
                    })}

                    <SheetFooter className="gap-2 pt-4">
                        {!readOnly && !isEditing && (
                            <Button type="button" variant="outline" onClick={() => setIsEditing(true)}>
                                Edit
                            </Button>
                        )}
                        {isEditing && (
                            <>
                                <Button type="button" variant="outline" onClick={() => {
                                    form.reset(values as DefaultValues<T>);
                                    setIsEditing(false);
                                }}>
                                    Cancel
                                </Button>
                                <Button type="submit" disabled={isLoading}>
                                    {isLoading ? "Saving..." : "Save"}
                                </Button>
                            </>
                        )}
                        {onDelete && !isEditing && (
                            <Button
                                type="button"
                                variant="destructive"
                                size="sm"
                                onClick={onDelete}
                                disabled={isLoading}
                            >
                                Delete
                            </Button>
                        )}
                    </SheetFooter>
                </form>
            </SheetContent>
        </Sheet>
    );
}
