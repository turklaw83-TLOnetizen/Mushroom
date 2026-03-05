// ---- Workflows Page -----------------------------------------------------
// List, create, and trigger automation workflows.
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";

interface WorkflowStep {
    action: string;
    params?: Record<string, unknown>;
}

interface Workflow {
    id: string;
    name: string;
    description: string;
    trigger_event: string;
    steps: WorkflowStep[];
    created_at?: string;
}

interface WorkflowsResponse {
    items: Workflow[];
    total: number;
}

interface TriggerResponse {
    status: string;
    message?: string;
}

const triggerStatusColor: Record<string, string> = {
    success: "text-green-400 border-green-400/30 bg-green-400/10",
    pending: "text-amber-400 border-amber-400/30 bg-amber-400/10",
    failed: "text-red-400 border-red-400/30 bg-red-400/10",
    running: "text-blue-400 border-blue-400/30 bg-blue-400/10",
};

export default function WorkflowsPage() {
    const { getToken } = useAuth();
    const queryClient = useQueryClient();

    // Dialog states
    const [createOpen, setCreateOpen] = useState(false);
    const [triggerTarget, setTriggerTarget] = useState<Workflow | null>(null);

    // Create form state
    const [createForm, setCreateForm] = useState({
        name: "",
        description: "",
        trigger_event: "",
    });

    // Trigger form state
    const [triggerCaseId, setTriggerCaseId] = useState("");
    const [lastTriggerResult, setLastTriggerResult] = useState<TriggerResponse | null>(null);

    // Fetch workflows
    const { data, isLoading } = useQuery({
        queryKey: ["workflows"],
        queryFn: () => api.get<WorkflowsResponse>("/workflows", { getToken }),
    });

    // Create workflow mutation
    const createWorkflow = useMutation({
        mutationFn: (body: { name: string; description: string; trigger_event: string; steps: WorkflowStep[] }) =>
            api.post<Workflow>("/workflows", body, { getToken }),
        onSuccess: () => {
            toast.success("Workflow created");
            queryClient.invalidateQueries({ queryKey: ["workflows"] });
            setCreateOpen(false);
            setCreateForm({ name: "", description: "", trigger_event: "" });
        },
        onError: (err) => {
            toast.error("Failed to create workflow", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        },
    });

    // Trigger workflow mutation
    const triggerWorkflow = useMutation({
        mutationFn: (body: { case_id: string; workflow_id: string; params: Record<string, unknown> }) =>
            api.post<TriggerResponse>("/workflows/trigger", body, { getToken }),
        onSuccess: (result) => {
            setLastTriggerResult(result);
            toast.success("Workflow triggered", {
                description: result.message || `Status: ${result.status}`,
            });
        },
        onError: (err) => {
            toast.error("Failed to trigger workflow", {
                description: err instanceof Error ? err.message : "Unknown error",
            });
        },
    });

    const workflows = data?.items ?? [];

    const handleCreate = () => {
        if (!createForm.name.trim()) {
            toast.error("Name is required");
            return;
        }
        createWorkflow.mutate({
            name: createForm.name.trim(),
            description: createForm.description.trim(),
            trigger_event: createForm.trigger_event.trim(),
            steps: [],
        });
    };

    const handleTrigger = () => {
        if (!triggerTarget || !triggerCaseId.trim()) {
            toast.error("Case ID is required");
            return;
        }
        setLastTriggerResult(null);
        triggerWorkflow.mutate({
            case_id: triggerCaseId.trim(),
            workflow_id: triggerTarget.id,
            params: {},
        });
    };

    const closeTriggerDialog = () => {
        setTriggerTarget(null);
        setTriggerCaseId("");
        setLastTriggerResult(null);
    };

    return (
        <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Workflows</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        {data?.total ?? 0} workflow{(data?.total ?? 0) !== 1 ? "s" : ""}
                    </p>
                </div>
                <Button onClick={() => setCreateOpen(true)} className="gap-2">
                    <span>+</span> Create Workflow
                </Button>
            </div>

            {isLoading ? (
                <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-24 w-full rounded-lg" />
                    ))}
                </div>
            ) : workflows.length === 0 ? (
                <Card className="border-dashed">
                    <CardContent className="py-16 text-center text-muted-foreground">
                        No workflows yet. Create your first workflow to automate tasks.
                    </CardContent>
                </Card>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {workflows.map((workflow) => (
                        <Card key={workflow.id} className="hover:border-primary/30 transition-colors">
                            <CardHeader className="pb-2">
                                <div className="flex items-center justify-between">
                                    <CardTitle className="text-sm font-medium">
                                        {workflow.name}
                                    </CardTitle>
                                    {workflow.trigger_event && (
                                        <Badge variant="outline" className="text-[10px]">
                                            {workflow.trigger_event}
                                        </Badge>
                                    )}
                                </div>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {workflow.description && (
                                    <p className="text-xs text-muted-foreground line-clamp-2">
                                        {workflow.description}
                                    </p>
                                )}
                                {workflow.steps?.length > 0 && (
                                    <p className="text-xs text-muted-foreground">
                                        {workflow.steps.length} step{workflow.steps.length !== 1 ? "s" : ""}
                                    </p>
                                )}
                                <div className="flex justify-end">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => setTriggerTarget(workflow)}
                                    >
                                        Trigger
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Create Workflow Dialog */}
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Create Workflow</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-3">
                        <Input
                            placeholder="Workflow name *"
                            value={createForm.name}
                            onChange={(e) =>
                                setCreateForm({ ...createForm, name: e.target.value })
                            }
                        />
                        <Input
                            placeholder="Description"
                            value={createForm.description}
                            onChange={(e) =>
                                setCreateForm({ ...createForm, description: e.target.value })
                            }
                        />
                        <Input
                            placeholder="Trigger event (e.g. case_created, file_uploaded)"
                            value={createForm.trigger_event}
                            onChange={(e) =>
                                setCreateForm({ ...createForm, trigger_event: e.target.value })
                            }
                        />
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setCreateOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleCreate}
                            disabled={!createForm.name.trim() || createWorkflow.isPending}
                        >
                            {createWorkflow.isPending ? "Creating..." : "Create Workflow"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Trigger Workflow Dialog */}
            <Dialog open={!!triggerTarget} onOpenChange={(open) => !open && closeTriggerDialog()}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Trigger: {triggerTarget?.name}</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-3">
                        <Input
                            placeholder="Case ID *"
                            value={triggerCaseId}
                            onChange={(e) => setTriggerCaseId(e.target.value)}
                        />
                        {lastTriggerResult && (
                            <div className="flex items-center gap-2">
                                <Badge
                                    variant="outline"
                                    className={`text-xs ${triggerStatusColor[lastTriggerResult.status] || ""}`}
                                >
                                    {lastTriggerResult.status}
                                </Badge>
                                {lastTriggerResult.message && (
                                    <span className="text-xs text-muted-foreground">
                                        {lastTriggerResult.message}
                                    </span>
                                )}
                            </div>
                        )}
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={closeTriggerDialog}>
                            Close
                        </Button>
                        <Button
                            onClick={handleTrigger}
                            disabled={!triggerCaseId.trim() || triggerWorkflow.isPending}
                        >
                            {triggerWorkflow.isPending ? "Triggering..." : "Trigger Workflow"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
