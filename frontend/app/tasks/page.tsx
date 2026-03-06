// ---- Tasks Page ---------------------------------------------------------
// Cross-case task board with full CRUD: create, edit, complete, delete.
"use client";

import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { toast } from "sonner";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import type { Task, Case } from "@/types/api";

// ---- Constants ----------------------------------------------------------

const priorityColor: Record<string, string> = {
    high: "text-red-400 border-red-400/30",
    medium: "text-amber-400 border-amber-400/30",
    low: "text-green-400 border-green-400/30",
};

const statusColumns = ["pending", "in_progress", "completed"] as const;
const statusLabels: Record<string, string> = {
    pending: "To Do",
    in_progress: "In Progress",
    completed: "Done",
};

type FilterTab = "all" | "my" | "high" | "medium" | "low";

const EMPTY_FORM = {
    case_id: "",
    title: "",
    description: "",
    assigned_to: "",
    due_date: "",
    priority: "medium",
    category: "",
};

// ---- Component ----------------------------------------------------------

export default function TasksPage() {
    const { getToken, userId } = useAuth();
    const queryClient = useQueryClient();

    const [search, setSearch] = useState("");
    const [filterTab, setFilterTab] = useState<FilterTab>("all");
    const [addOpen, setAddOpen] = useState(false);
    const [editOpen, setEditOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<Task | null>(null);
    const [form, setForm] = useState(EMPTY_FORM);
    const [editingTask, setEditingTask] = useState<Task | null>(null);

    // ---- Queries --------------------------------------------------------

    const { data: tasksData, isLoading, error } = useQuery({
        queryKey: ["all-tasks"],
        queryFn: () => api.get<{ items: Task[] }>("/tasks", { getToken }),
    });

    const { data: casesData } = useQuery({
        queryKey: ["cases-list"],
        queryFn: () => api.get<{ items: Case[] }>("/cases", { getToken }),
    });

    const allTasks: Task[] = tasksData?.items ?? [];
    const cases: Case[] = casesData?.items ?? [];

    // ---- Mutations ------------------------------------------------------

    const createMutation = useMutation({
        mutationFn: (payload: typeof EMPTY_FORM) => {
            const { case_id, ...body } = payload;
            return api.post(`/cases/${case_id}/tasks`, body, { getToken });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["all-tasks"] });
            toast.success("Task created");
            setAddOpen(false);
            setForm(EMPTY_FORM);
        },
        onError: (err: Error) => {
            toast.error(`Failed to create task: ${err.message}`);
        },
    });

    const updateMutation = useMutation({
        mutationFn: ({ caseId, taskId, body }: { caseId: string; taskId: string; body: Record<string, unknown> }) =>
            api.put(`/cases/${caseId}/tasks/${taskId}`, body, { getToken }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["all-tasks"] });
            toast.success("Task updated");
            setEditOpen(false);
            setEditingTask(null);
        },
        onError: (err: Error) => {
            toast.error(`Failed to update task: ${err.message}`);
        },
    });

    const completeMutation = useMutation({
        mutationFn: ({ caseId, taskId }: { caseId: string; taskId: string }) =>
            api.post(`/cases/${caseId}/tasks/${taskId}/complete`, undefined, { getToken }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["all-tasks"] });
            toast.success("Task completed");
        },
        onError: (err: Error) => {
            toast.error(`Failed to complete task: ${err.message}`);
        },
    });

    const deleteMutation = useMutation({
        mutationFn: ({ caseId, taskId }: { caseId: string; taskId: string }) =>
            api.delete(`/cases/${caseId}/tasks/${taskId}`, { getToken }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["all-tasks"] });
            toast.success("Task deleted");
            setDeleteTarget(null);
        },
        onError: (err: Error) => {
            toast.error(`Failed to delete task: ${err.message}`);
        },
    });

    // ---- Helpers --------------------------------------------------------

    const updateForm = useCallback(
        (field: string, value: string) => setForm((prev) => ({ ...prev, [field]: value })),
        [],
    );

    const openEdit = useCallback((task: Task) => {
        setEditingTask(task);
        setForm({
            case_id: task.case_id || "",
            title: task.title,
            description: task.description || "",
            assigned_to: task.assigned_to || "",
            due_date: task.due_date || "",
            priority: task.priority || "medium",
            category: task.category || "",
        });
        setEditOpen(true);
    }, []);

    const handleCreate = useCallback(() => {
        if (!form.case_id) {
            toast.error("Please select a case");
            return;
        }
        if (!form.title.trim()) {
            toast.error("Title is required");
            return;
        }
        createMutation.mutate(form);
    }, [form, createMutation]);

    const handleUpdate = useCallback(() => {
        if (!editingTask?.case_id || !editingTask?.id) return;
        updateMutation.mutate({
            caseId: editingTask.case_id,
            taskId: editingTask.id,
            body: {
                title: form.title,
                description: form.description,
                assigned_to: form.assigned_to,
                due_date: form.due_date,
                priority: form.priority,
                category: form.category,
            },
        });
    }, [editingTask, form, updateMutation]);

    // ---- Filtering ------------------------------------------------------

    let filtered = allTasks;

    if (search) {
        const q = search.toLowerCase();
        filtered = filtered.filter(
            (t) =>
                t.title?.toLowerCase().includes(q) ||
                t.case_name?.toLowerCase().includes(q) ||
                t.description?.toLowerCase().includes(q),
        );
    }

    if (filterTab === "my") {
        filtered = filtered.filter((t) => t.assigned_to === userId);
    } else if (filterTab === "high" || filterTab === "medium" || filterTab === "low") {
        filtered = filtered.filter((t) => t.priority === filterTab);
    }

    // ---- Render ---------------------------------------------------------

    const filterTabs: { key: FilterTab; label: string }[] = [
        { key: "all", label: "All" },
        { key: "my", label: "My Tasks" },
        { key: "high", label: "High" },
        { key: "medium", label: "Medium" },
        { key: "low", label: "Low" },
    ];

    return (
        <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between flex-wrap gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Task Board</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        All tasks across cases
                    </p>
                </div>
                <Dialog open={addOpen} onOpenChange={(open) => { setAddOpen(open); if (!open) setForm(EMPTY_FORM); }}>
                    <DialogTrigger asChild>
                        <Button size="sm">+ Add Task</Button>
                    </DialogTrigger>
                    <DialogContent className="sm:max-w-lg">
                        <DialogHeader>
                            <DialogTitle>New Task</DialogTitle>
                            <DialogDescription>Create a task and assign it to a case.</DialogDescription>
                        </DialogHeader>
                        <div className="space-y-3 py-2">
                            <div>
                                <label className="text-xs font-medium text-muted-foreground">Case *</label>
                                <Select value={form.case_id} onValueChange={(v) => updateForm("case_id", v)}>
                                    <SelectTrigger className="mt-1"><SelectValue placeholder="Select a case" /></SelectTrigger>
                                    <SelectContent>
                                        {cases.map((c) => (
                                            <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div>
                                <label className="text-xs font-medium text-muted-foreground">Title *</label>
                                <Input className="mt-1" value={form.title} onChange={(e) => updateForm("title", e.target.value)} placeholder="Task title" />
                            </div>
                            <div>
                                <label className="text-xs font-medium text-muted-foreground">Description</label>
                                <Textarea className="mt-1" value={form.description} onChange={(e) => updateForm("description", e.target.value)} placeholder="Optional details" rows={3} />
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-medium text-muted-foreground">Assigned To</label>
                                    <Input className="mt-1" value={form.assigned_to} onChange={(e) => updateForm("assigned_to", e.target.value)} placeholder="Name or ID" />
                                </div>
                                <div>
                                    <label className="text-xs font-medium text-muted-foreground">Due Date</label>
                                    <Input className="mt-1" type="date" value={form.due_date} onChange={(e) => updateForm("due_date", e.target.value)} />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-medium text-muted-foreground">Priority</label>
                                    <Select value={form.priority} onValueChange={(v) => updateForm("priority", v)}>
                                        <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="high">High</SelectItem>
                                            <SelectItem value="medium">Medium</SelectItem>
                                            <SelectItem value="low">Low</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div>
                                    <label className="text-xs font-medium text-muted-foreground">Category</label>
                                    <Input className="mt-1" value={form.category} onChange={(e) => updateForm("category", e.target.value)} placeholder="e.g. Filing, Research" />
                                </div>
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
                            <Button onClick={handleCreate} disabled={createMutation.isPending}>
                                {createMutation.isPending ? "Creating..." : "Create Task"}
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>

            {/* Search + filter tabs */}
            <div className="flex items-center gap-4 flex-wrap">
                <Input
                    placeholder="Search tasks..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="max-w-md"
                />
                <div className="flex items-center gap-1">
                    {filterTabs.map((tab) => (
                        <Button
                            key={tab.key}
                            variant={filterTab === tab.key ? "default" : "ghost"}
                            size="sm"
                            onClick={() => setFilterTab(tab.key)}
                            className="text-xs"
                        >
                            {tab.label}
                        </Button>
                    ))}
                </div>
            </div>

            {/* Kanban columns */}
            {isLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {statusColumns.map((col) => (
                        <div key={col} className="space-y-3">
                            <Skeleton className="h-8 w-32" />
                            {Array.from({ length: 3 }).map((_, i) => (
                                <Skeleton key={i} className="h-28 w-full rounded-lg" />
                            ))}
                        </div>
                    ))}
                </div>
            ) : error ? (
                <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
                    Failed to load tasks: {error instanceof Error ? error.message : "Unknown error"}
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {statusColumns.map((status) => {
                        const columnTasks = filtered.filter((t) => (t.status || "pending") === status);
                        return (
                            <div key={status}>
                                <div className="flex items-center gap-2 mb-3">
                                    <h2 className="text-sm font-semibold">
                                        {statusLabels[status] || status}
                                    </h2>
                                    <Badge variant="secondary" className="text-[10px]">
                                        {columnTasks.length}
                                    </Badge>
                                </div>
                                <div className="space-y-2">
                                    {columnTasks.length === 0 ? (
                                        <p className="text-xs text-muted-foreground text-center py-8">
                                            No tasks
                                        </p>
                                    ) : (
                                        columnTasks.map((task) => (
                                            <Card key={task.id} className="hover:border-primary/30 transition-colors">
                                                <CardContent className="pt-3 pb-2 space-y-1.5">
                                                    <p className="text-sm font-medium leading-tight">
                                                        {task.title}
                                                    </p>
                                                    {task.description && (
                                                        <p className="text-xs text-muted-foreground line-clamp-2">
                                                            {task.description}
                                                        </p>
                                                    )}
                                                    <div className="flex items-center gap-2 flex-wrap">
                                                        {task.priority && (
                                                            <Badge
                                                                variant="outline"
                                                                className={`text-[10px] ${priorityColor[task.priority] || ""}`}
                                                            >
                                                                {task.priority}
                                                            </Badge>
                                                        )}
                                                        {task.due_date && (
                                                            <span className="text-[10px] text-muted-foreground">
                                                                Due {task.due_date}
                                                            </span>
                                                        )}
                                                        {task.case_name && (
                                                            <Badge variant="outline" className="text-[10px]">
                                                                {task.case_name}
                                                            </Badge>
                                                        )}
                                                    </div>
                                                    {/* Action buttons */}
                                                    <div className="flex items-center gap-1 pt-1">
                                                        {status !== "completed" && (
                                                            <Button
                                                                variant="ghost"
                                                                size="sm"
                                                                className="h-6 px-2 text-[10px]"
                                                                disabled={completeMutation.isPending}
                                                                onClick={() =>
                                                                    task.case_id &&
                                                                    completeMutation.mutate({ caseId: task.case_id, taskId: task.id })
                                                                }
                                                            >
                                                                Complete
                                                            </Button>
                                                        )}
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            className="h-6 px-2 text-[10px]"
                                                            onClick={() => openEdit(task)}
                                                        >
                                                            Edit
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            className="h-6 px-2 text-[10px] text-destructive hover:text-destructive"
                                                            onClick={() => setDeleteTarget(task)}
                                                        >
                                                            Delete
                                                        </Button>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Edit dialog */}
            <Dialog open={editOpen} onOpenChange={(open) => { setEditOpen(open); if (!open) { setEditingTask(null); setForm(EMPTY_FORM); } }}>
                <DialogContent className="sm:max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Edit Task</DialogTitle>
                        <DialogDescription>Update task details.</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-3 py-2">
                        <div>
                            <label className="text-xs font-medium text-muted-foreground">Title</label>
                            <Input className="mt-1" value={form.title} onChange={(e) => updateForm("title", e.target.value)} />
                        </div>
                        <div>
                            <label className="text-xs font-medium text-muted-foreground">Description</label>
                            <Textarea className="mt-1" value={form.description} onChange={(e) => updateForm("description", e.target.value)} rows={3} />
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="text-xs font-medium text-muted-foreground">Assigned To</label>
                                <Input className="mt-1" value={form.assigned_to} onChange={(e) => updateForm("assigned_to", e.target.value)} />
                            </div>
                            <div>
                                <label className="text-xs font-medium text-muted-foreground">Due Date</label>
                                <Input className="mt-1" type="date" value={form.due_date} onChange={(e) => updateForm("due_date", e.target.value)} />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="text-xs font-medium text-muted-foreground">Priority</label>
                                <Select value={form.priority} onValueChange={(v) => updateForm("priority", v)}>
                                    <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="high">High</SelectItem>
                                        <SelectItem value="medium">Medium</SelectItem>
                                        <SelectItem value="low">Low</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div>
                                <label className="text-xs font-medium text-muted-foreground">Category</label>
                                <Input className="mt-1" value={form.category} onChange={(e) => updateForm("category", e.target.value)} />
                            </div>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button>
                        <Button onClick={handleUpdate} disabled={updateMutation.isPending}>
                            {updateMutation.isPending ? "Saving..." : "Save Changes"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete confirmation */}
            <AlertDialog open={!!deleteTarget} onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Delete Task</AlertDialogTitle>
                        <AlertDialogDescription>
                            Are you sure you want to delete &quot;{deleteTarget?.title}&quot;? This action cannot be undone.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={() =>
                                deleteTarget?.case_id &&
                                deleteMutation.mutate({ caseId: deleteTarget.case_id, taskId: deleteTarget.id })
                            }
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            {deleteMutation.isPending ? "Deleting..." : "Delete"}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
