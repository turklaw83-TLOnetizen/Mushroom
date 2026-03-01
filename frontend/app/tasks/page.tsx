// ---- Tasks Page ---------------------------------------------------------
// Cross-case task board view.
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";

interface Task {
    id: string;
    title: string;
    description: string;
    status: string;
    priority: string;
    due_date: string;
    assigned_to: string;
    case_id?: string;
    case_name?: string;
}

const priorityColor: Record<string, string> = {
    high: "text-red-400 border-red-400/30",
    medium: "text-amber-400 border-amber-400/30",
    low: "text-green-400 border-green-400/30",
};

const statusColumns = ["pending", "in_progress", "completed"];
const statusLabels: Record<string, string> = {
    pending: "📋 To Do",
    in_progress: "🔄 In Progress",
    completed: "✅ Done",
};

export default function TasksPage() {
    const { getToken } = useAuth();
    const [search, setSearch] = useState("");

    // Fetch tasks across all cases via notifications (which aggregates tasks)
    const { data, isLoading } = useQuery({
        queryKey: ["all-tasks"],
        queryFn: () => api.get<{ items: Task[] }>("/notifications", { getToken }),
    });

    const allTasks: Task[] = data?.items ?? [];
    const filtered = search
        ? allTasks.filter((t) =>
            t.title?.toLowerCase().includes(search.toLowerCase()) ||
            t.case_name?.toLowerCase().includes(search.toLowerCase()),
        )
        : allTasks;

    return (
        <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight">Task Board</h1>
                <p className="text-sm text-muted-foreground mt-1">
                    All tasks across cases
                </p>
            </div>

            <Input
                placeholder="Search tasks..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="max-w-md"
            />

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
                                                                📅 {task.due_date}
                                                            </span>
                                                        )}
                                                        {task.case_name && (
                                                            <Badge variant="outline" className="text-[10px]">
                                                                {task.case_name}
                                                            </Badge>
                                                        )}
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
        </div>
    );
}
