// ---- Smart Intake Wizard Page --------------------------------------------
// Step-by-step client intake wizard. Top-level route (not a case sub-page).
// Flow: Select Template -> Dynamic Steps -> Summary -> Create Client (+Case)
"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { routes } from "@/lib/api-routes";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { IntakeField, IntakeStep, IntakeSession } from "@/types/api";

// ---- Template definitions -----------------------------------------------

interface TemplateOption {
    key: string;
    label: string;
    description: string;
    icon: string;
    color: string;
}

const TEMPLATES: TemplateOption[] = [
    {
        key: "general",
        label: "General Intake",
        description: "Standard client intake form for any matter type. Covers personal information, case details, and initial consultation notes.",
        icon: "G",
        color: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    },
    {
        key: "criminal",
        label: "Criminal Defense",
        description: "Criminal defense intake with charges, arrest details, bond information, and prior record sections.",
        icon: "C",
        color: "bg-red-500/15 text-red-400 border-red-500/30",
    },
    {
        key: "civil",
        label: "Civil Litigation",
        description: "Civil case intake covering claims, damages, opposing parties, and statute of limitations details.",
        icon: "L",
        color: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    },
    {
        key: "family",
        label: "Family Law",
        description: "Family law intake including marriage details, children, property, and support considerations.",
        icon: "F",
        color: "bg-purple-500/15 text-purple-400 border-purple-500/30",
    },
];

// ---- Wizard state types -------------------------------------------------

type WizardPhase = "template" | "steps" | "summary" | "complete";

interface StepData {
    step: number;
    title: string;
    responses: Record<string, string>;
}

// ---- Dynamic Field Renderer ---------------------------------------------

function FieldRenderer({
    field,
    value,
    onChange,
    error,
}: {
    field: IntakeField;
    value: string;
    onChange: (val: string) => void;
    error?: string;
}) {
    const id = `field-${field.name}`;

    return (
        <div className="space-y-1.5">
            <Label htmlFor={id} className="text-sm font-medium">
                {field.label}
                {field.required && <span className="text-red-400 ml-1">*</span>}
            </Label>

            {field.type === "textarea" ? (
                <Textarea
                    id={id}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    placeholder={field.placeholder || ""}
                    rows={4}
                    className={cn(error && "border-red-500")}
                />
            ) : field.type === "select" ? (
                <Select value={value} onValueChange={onChange}>
                    <SelectTrigger id={id} className={cn(error && "border-red-500")}>
                        <SelectValue placeholder={field.placeholder || `Select ${field.label.toLowerCase()}`} />
                    </SelectTrigger>
                    <SelectContent>
                        {(field.options || []).map((opt) => (
                            <SelectItem key={opt} value={opt}>
                                {opt}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            ) : (
                <Input
                    id={id}
                    type={field.type === "email" ? "email" : field.type === "tel" ? "tel" : field.type === "date" ? "date" : "text"}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    placeholder={field.placeholder || ""}
                    className={cn(error && "border-red-500")}
                />
            )}

            {error && <p className="text-xs text-red-400">{error}</p>}
        </div>
    );
}

// ---- Step Progress Indicator --------------------------------------------

function StepIndicator({
    currentStep,
    totalSteps,
    stepTitles,
}: {
    currentStep: number;
    totalSteps: number;
    stepTitles: string[];
}) {
    return (
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
            {Array.from({ length: totalSteps }).map((_, i) => {
                const stepNum = i + 1;
                const isActive = stepNum === currentStep;
                const isComplete = stepNum < currentStep;

                return (
                    <div key={i} className="flex items-center gap-2 shrink-0">
                        <div className={cn(
                            "flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-colors",
                            isActive
                                ? "bg-primary text-primary-foreground"
                                : isComplete
                                    ? "bg-emerald-500/20 text-emerald-400"
                                    : "bg-muted text-muted-foreground",
                        )}>
                            {isComplete ? "\u2713" : stepNum}
                        </div>
                        <span className={cn(
                            "text-xs hidden sm:inline",
                            isActive ? "text-foreground font-medium" : "text-muted-foreground",
                        )}>
                            {stepTitles[i] || `Step ${stepNum}`}
                        </span>
                        {i < totalSteps - 1 && (
                            <div className={cn(
                                "w-6 h-px",
                                isComplete ? "bg-emerald-500/50" : "bg-border",
                            )} />
                        )}
                    </div>
                );
            })}
        </div>
    );
}

// ---- Template Selection View --------------------------------------------

function TemplateSelector({
    onSelect,
}: {
    onSelect: (template: string) => void;
}) {
    return (
        <div className="space-y-6">
            <div className="text-center">
                <h2 className="text-2xl font-bold tracking-tight">Smart Intake Wizard</h2>
                <p className="text-sm text-muted-foreground mt-2">
                    Select an intake template to begin the client onboarding process.
                </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl mx-auto">
                {TEMPLATES.map((tmpl) => (
                    <Card
                        key={tmpl.key}
                        className="hover:border-primary/30 transition-colors cursor-pointer group"
                        onClick={() => onSelect(tmpl.key)}
                    >
                        <CardHeader className="pb-2">
                            <div className="flex items-center gap-3">
                                <div className={cn(
                                    "flex h-10 w-10 items-center justify-center rounded-lg text-sm font-bold",
                                    tmpl.color,
                                )}>
                                    {tmpl.icon}
                                </div>
                                <CardTitle className="text-base group-hover:text-primary transition-colors">
                                    {tmpl.label}
                                </CardTitle>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <p className="text-xs text-muted-foreground">{tmpl.description}</p>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
}

// ---- Summary View -------------------------------------------------------

function SummaryView({
    allSteps,
    createCase,
    setCreateCase,
    onEdit,
    onComplete,
    isSubmitting,
}: {
    allSteps: StepData[];
    createCase: boolean;
    setCreateCase: (v: boolean) => void;
    onEdit: (step: number) => void;
    onComplete: () => void;
    isSubmitting: boolean;
}) {
    return (
        <div className="space-y-6 max-w-3xl mx-auto">
            <div className="text-center">
                <h2 className="text-xl font-bold tracking-tight">Review Intake Information</h2>
                <p className="text-sm text-muted-foreground mt-1">
                    Review all collected information before creating the client record.
                </p>
            </div>

            {allSteps.map((step) => (
                <Card key={step.step}>
                    <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                            <CardTitle className="text-sm font-medium">{step.title}</CardTitle>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="text-xs"
                                onClick={() => onEdit(step.step)}
                            >
                                Edit
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            {Object.entries(step.responses).map(([key, val]) => (
                                <div key={key}>
                                    <p className="text-xs text-muted-foreground capitalize">
                                        {key.replace(/_/g, " ")}
                                    </p>
                                    <p className="text-sm mt-0.5">
                                        {val || <span className="text-muted-foreground italic">Not provided</span>}
                                    </p>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            ))}

            <Separator />

            {/* Create options */}
            <Card>
                <CardContent className="py-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-sm font-medium">Also create a case?</p>
                            <p className="text-xs text-muted-foreground mt-0.5">
                                Auto-create a case record linked to this client
                            </p>
                        </div>
                        <Button
                            variant={createCase ? "default" : "outline"}
                            size="sm"
                            onClick={() => setCreateCase(!createCase)}
                        >
                            {createCase ? "Yes, create case" : "Client only"}
                        </Button>
                    </div>
                </CardContent>
            </Card>

            <div className="flex justify-center gap-3">
                <Button
                    onClick={onComplete}
                    disabled={isSubmitting}
                    size="lg"
                >
                    {isSubmitting
                        ? "Creating..."
                        : createCase
                            ? "Create Client + Case"
                            : "Create Client"
                    }
                </Button>
            </div>
        </div>
    );
}

// ---- Completion View ----------------------------------------------------

function CompletionView({
    result,
}: {
    result: { client_id?: string; case_id?: string; status?: string } | null;
}) {
    const router = useRouter();

    return (
        <div className="max-w-md mx-auto text-center space-y-6 py-12">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/20 mx-auto">
                <span className="text-2xl text-emerald-400 font-bold">\u2713</span>
            </div>
            <div>
                <h2 className="text-xl font-bold">Intake Complete</h2>
                <p className="text-sm text-muted-foreground mt-2">
                    Client record has been created successfully.
                </p>
            </div>

            <div className="flex flex-col gap-2">
                {result?.client_id && (
                    <Button
                        variant="outline"
                        onClick={() => router.push(`/crm/${result.client_id}`)}
                    >
                        View Client Record
                    </Button>
                )}
                {result?.case_id && (
                    <Button
                        variant="outline"
                        onClick={() => router.push(`/cases/${result.case_id}`)}
                    >
                        Open Case
                    </Button>
                )}
                <Button
                    variant="ghost"
                    onClick={() => router.push("/intake")}
                >
                    Start New Intake
                </Button>
                <Button
                    variant="ghost"
                    onClick={() => router.push("/crm")}
                >
                    Back to Clients
                </Button>
            </div>
        </div>
    );
}

// ---- Main Page ----------------------------------------------------------

export default function IntakePage() {
    const { getToken } = useAuth();
    const router = useRouter();

    // Wizard state
    const [phase, setPhase] = useState<WizardPhase>("template");
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [currentStep, setCurrentStep] = useState<IntakeStep | null>(null);
    const [allSteps, setAllSteps] = useState<StepData[]>([]);
    const [formValues, setFormValues] = useState<Record<string, string>>({});
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [createCase, setCreateCase] = useState(false);
    const [completeResult, setCompleteResult] = useState<Record<string, unknown> | null>(null);
    const [stepTitles, setStepTitles] = useState<string[]>([]);

    // Start intake session
    const startMutation = useMutation({
        mutationFn: (template: string) =>
            api.post<{ session_id: string; current_step: IntakeStep }>(
                routes.intake.start,
                { template },
                { getToken },
            ),
        onSuccess: (data) => {
            setSessionId(data.session_id);
            setCurrentStep(data.current_step);
            setFormValues({});
            setFormErrors({});
            setStepTitles([data.current_step.title]);
            setPhase("steps");
        },
        onError: () => toast.error("Failed to start intake session"),
    });

    // Submit step
    const stepMutation = useMutation({
        mutationFn: (responses: Record<string, string>) =>
            api.post<IntakeStep & { complete?: boolean; summary?: Record<string, unknown> }>(
                routes.intake.step(sessionId!),
                { responses },
                { getToken },
            ),
        onSuccess: (data) => {
            // Save current step data
            const stepData: StepData = {
                step: currentStep!.step,
                title: currentStep!.title,
                responses: { ...formValues },
            };

            const updatedSteps = [...allSteps];
            const existingIdx = updatedSteps.findIndex((s) => s.step === stepData.step);
            if (existingIdx >= 0) {
                updatedSteps[existingIdx] = stepData;
            } else {
                updatedSteps.push(stepData);
            }
            setAllSteps(updatedSteps);

            if (data.complete) {
                // All steps done -- go to summary
                setPhase("summary");
            } else {
                // Move to next step
                setCurrentStep(data);
                setFormValues({});
                setFormErrors({});
                setStepTitles((prev) => {
                    const titles = [...prev];
                    if (titles.length < data.step) {
                        titles.push(data.title);
                    }
                    return titles;
                });
            }
        },
        onError: () => toast.error("Failed to submit step"),
    });

    // Complete intake
    const completeMutation = useMutation({
        mutationFn: () =>
            api.post<{ client_id?: string; case_id?: string; status?: string }>(
                routes.intake.complete(sessionId!),
                { create_case: createCase },
                { getToken },
            ),
        onSuccess: (data) => {
            setCompleteResult(data as Record<string, unknown>);
            setPhase("complete");
            toast.success("Intake completed successfully");
        },
        onError: () => toast.error("Failed to complete intake"),
    });

    // Handle field value change
    const handleFieldChange = useCallback((name: string, value: string) => {
        setFormValues((prev) => ({ ...prev, [name]: value }));
        setFormErrors((prev) => {
            const next = { ...prev };
            delete next[name];
            return next;
        });
    }, []);

    // Validate and submit current step
    const handleNext = useCallback(() => {
        if (!currentStep) return;

        // Validate required fields
        const errors: Record<string, string> = {};
        for (const field of currentStep.fields) {
            if (field.required && !formValues[field.name]?.trim()) {
                errors[field.name] = `${field.label} is required`;
            }
            if (field.type === "email" && formValues[field.name]?.trim()) {
                const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRe.test(formValues[field.name])) {
                    errors[field.name] = "Please enter a valid email address";
                }
            }
        }

        if (Object.keys(errors).length > 0) {
            setFormErrors(errors);
            return;
        }

        stepMutation.mutate(formValues);
    }, [currentStep, formValues, stepMutation]);

    // Go back to previous step
    const handleBack = useCallback(() => {
        if (!currentStep || currentStep.step <= 1) {
            setPhase("template");
            setSessionId(null);
            setCurrentStep(null);
            setAllSteps([]);
            setStepTitles([]);
            return;
        }

        // Restore previous step data from allSteps
        const prevStep = allSteps.find((s) => s.step === currentStep.step - 1);
        if (prevStep) {
            setFormValues(prevStep.responses);
            setCurrentStep({
                step: prevStep.step,
                title: prevStep.title,
                fields: currentStep.fields, // We don't have the previous fields cached
            });
        }
    }, [currentStep, allSteps]);

    // Edit a specific step from summary
    const handleEditStep = useCallback(
        (stepNum: number) => {
            const step = allSteps.find((s) => s.step === stepNum);
            if (step) {
                setFormValues(step.responses);
                setCurrentStep({
                    step: step.step,
                    title: step.title,
                    fields: [], // Fields will need to be re-fetched from API
                });
                setPhase("steps");
            }
        },
        [allSteps],
    );

    return (
        <div className="p-6 md:p-8 max-w-4xl mx-auto space-y-6">
            {/* Template Selection */}
            {phase === "template" && (
                <TemplateSelector
                    onSelect={(template) => startMutation.mutate(template)}
                />
            )}

            {/* Loading initial template */}
            {startMutation.isPending && (
                <div className="max-w-3xl mx-auto space-y-4">
                    <Skeleton className="h-8 w-48 mx-auto" />
                    <Skeleton className="h-48 w-full" />
                </div>
            )}

            {/* Step-by-step form */}
            {phase === "steps" && currentStep && (
                <div className="max-w-3xl mx-auto space-y-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <h2 className="text-xl font-bold tracking-tight">Smart Intake Wizard</h2>
                            <p className="text-sm text-muted-foreground mt-1">
                                Step {currentStep.step}: {currentStep.title}
                            </p>
                        </div>
                        <Badge variant="outline" className="text-xs">
                            Step {currentStep.step}{stepTitles.length > 0 ? ` of ${stepTitles.length}+` : ""}
                        </Badge>
                    </div>

                    {/* Step progress */}
                    {stepTitles.length > 1 && (
                        <StepIndicator
                            currentStep={currentStep.step}
                            totalSteps={stepTitles.length}
                            stepTitles={stepTitles}
                        />
                    )}

                    {/* Form fields */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base">{currentStep.title}</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {currentStep.fields.length > 0 ? (
                                currentStep.fields.map((field) => (
                                    <FieldRenderer
                                        key={field.name}
                                        field={field}
                                        value={formValues[field.name] || ""}
                                        onChange={(val) => handleFieldChange(field.name, val)}
                                        error={formErrors[field.name]}
                                    />
                                ))
                            ) : (
                                <p className="text-sm text-muted-foreground italic">
                                    No additional fields for this step. Click Next to continue.
                                </p>
                            )}
                        </CardContent>
                    </Card>

                    {/* Navigation buttons */}
                    <div className="flex justify-between">
                        <Button
                            variant="outline"
                            onClick={handleBack}
                            disabled={stepMutation.isPending}
                        >
                            {currentStep.step <= 1 ? "Cancel" : "Back"}
                        </Button>
                        <Button
                            onClick={handleNext}
                            disabled={stepMutation.isPending}
                        >
                            {stepMutation.isPending ? "Saving..." : "Next"}
                        </Button>
                    </div>
                </div>
            )}

            {/* Summary */}
            {phase === "summary" && (
                <SummaryView
                    allSteps={allSteps}
                    createCase={createCase}
                    setCreateCase={setCreateCase}
                    onEdit={handleEditStep}
                    onComplete={() => completeMutation.mutate()}
                    isSubmitting={completeMutation.isPending}
                />
            )}

            {/* Completion */}
            {phase === "complete" && (
                <CompletionView
                    result={completeResult as { client_id?: string; case_id?: string; status?: string } | null}
                />
            )}
        </div>
    );
}
