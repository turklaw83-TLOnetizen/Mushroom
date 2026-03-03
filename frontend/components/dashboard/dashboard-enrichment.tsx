// ---- Dashboard Enrichment Widgets ----------------------------------------
// Billing metrics, deadline urgency board, team workload, and deadline toasts.
"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

// ---- Types ----------------------------------------------------------------

interface BillingSummary {
  unbilled_hours: number;
  unbilled_amount: number;
  outstanding_invoices: number;
  monthly_revenue: number;
}

interface DeadlineItem {
  id?: string;
  label?: string;
  title?: string;
  case_name?: string;
  case_id?: string;
  date: string;
  category?: string;
}

interface StaffMember {
  id?: string;
  name: string;
  role?: string;
  active_cases?: number;
  case_count?: number;
  initials?: string;
}

// ---- Helpers --------------------------------------------------------------

function formatCurrency(value: number | undefined | null): string {
  if (value == null || isNaN(value)) return "\u2014";
  return `$${value.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function formatMetric(value: number | undefined | null): string {
  if (value == null || isNaN(value)) return "\u2014";
  return value.toLocaleString("en-US");
}

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function daysUntil(dateStr: string): number {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const target = new Date(dateStr);
  const targetDay = new Date(target.getFullYear(), target.getMonth(), target.getDate());
  return Math.floor((targetDay.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

function deadlineUrgencyClass(daysOut: number): string {
  if (daysOut <= 0) return "text-red-400 bg-red-500/10 border-red-500/20";
  if (daysOut === 1) return "text-orange-400 bg-orange-500/10 border-orange-500/20";
  if (daysOut <= 3) return "text-yellow-400 bg-yellow-500/10 border-yellow-500/20";
  return "text-blue-400 bg-blue-500/10 border-blue-500/20";
}

function deadlineUrgencyLabel(daysOut: number): string {
  if (daysOut < 0) return "Overdue";
  if (daysOut === 0) return "Today";
  if (daysOut === 1) return "Tomorrow";
  return `${daysOut} days`;
}

function formatDeadlineDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", weekday: "short" });
  } catch {
    return dateStr;
  }
}

// ---- 1. Billing Metrics Row -----------------------------------------------

export function BillingMetrics() {
  const { getToken } = useAuth();

  const { data, isLoading } = useQuery({
    queryKey: ["billing-summary"],
    queryFn: () =>
      api.get<BillingSummary>("/billing/summary", {
        getToken,
        noRetry: true,
      }),
    retry: false,
  });

  const metrics = [
    {
      label: "Unbilled Hours",
      value: data ? formatMetric(data.unbilled_hours) : "\u2014",
      color: "text-blue-400",
    },
    {
      label: "Unbilled Amount",
      value: data ? formatCurrency(data.unbilled_amount) : "\u2014",
      color: "text-emerald-400",
    },
    {
      label: "Outstanding Invoices",
      value: data ? formatMetric(data.outstanding_invoices) : "\u2014",
      color: "text-amber-400",
    },
    {
      label: "Monthly Revenue",
      value: data ? formatCurrency(data.monthly_revenue) : "\u2014",
      color: "text-purple-400",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {metrics.map((m) => (
        <Card key={m.label}>
          <CardContent className="pt-4 pb-3">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">
              {m.label}
            </p>
            {isLoading ? (
              <Skeleton className="h-8 w-20 mt-1" />
            ) : (
              <p className={`text-2xl font-bold mt-1 ${m.color}`}>{m.value}</p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ---- 2. Deadline Urgency Board --------------------------------------------

export function DeadlineUrgencyBoard() {
  const { getToken } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  // Try /deadlines/upcoming first, fall back to /cases/deadlines?days=14
  const { data: primaryData, isError: primaryError } = useQuery({
    queryKey: ["deadlines-upcoming"],
    queryFn: () =>
      api.get<{ items: DeadlineItem[]; count?: number }>("/deadlines/upcoming", {
        getToken,
        noRetry: true,
      }),
    retry: false,
  });

  const { data: fallbackData } = useQuery({
    queryKey: ["cases-deadlines-14"],
    queryFn: () =>
      api.get<{ items: DeadlineItem[]; count?: number }>("/cases/deadlines", {
        params: { days: 14 },
        getToken,
        noRetry: true,
      }),
    retry: false,
    enabled: primaryError,
  });

  const rawItems = primaryError
    ? fallbackData?.items ?? []
    : primaryData?.items ?? [];

  // Filter to next 14 days and sort by date
  const items = rawItems
    .filter((d) => {
      const days = daysUntil(d.date);
      return days >= -1 && days <= 14; // include overdue by 1 day
    })
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

  const count = items.length;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-sm font-medium">
              Upcoming Deadlines
            </CardTitle>
            {count > 0 && (
              <Badge variant="secondary" className="text-[10px]">
                {count}
              </Badge>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs text-muted-foreground"
            onClick={() => setCollapsed((prev) => !prev)}
          >
            {collapsed ? "Expand" : "Collapse"}
          </Button>
        </div>
      </CardHeader>
      {!collapsed && (
        <CardContent className="pt-0">
          {items.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No upcoming deadlines within 14 days
            </p>
          ) : (
            <div className="space-y-2">
              {items.map((item, idx) => {
                const days = daysUntil(item.date);
                const urgencyClass = deadlineUrgencyClass(days);
                const urgencyLabel = deadlineUrgencyLabel(days);

                return (
                  <div
                    key={item.id ?? `${item.date}-${idx}`}
                    className={`flex items-center justify-between rounded-lg border px-3 py-2 ${urgencyClass}`}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {item.label || item.title || "Deadline"}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        {item.case_name && (
                          <span className="text-xs opacity-75 truncate">
                            {item.case_name}
                          </span>
                        )}
                        {item.category && (
                          <Badge variant="outline" className="text-[10px] opacity-75">
                            {item.category}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0 ml-3">
                      <span className="text-xs opacity-75">
                        {formatDeadlineDate(item.date)}
                      </span>
                      <Badge
                        variant="outline"
                        className={`text-[10px] font-semibold ${urgencyClass}`}
                      >
                        {urgencyLabel}
                      </Badge>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}

// ---- 3. Team Workload Section ---------------------------------------------

export function TeamWorkload() {
  const { getToken } = useAuth();

  // Try /staff/workload first, fall back to /users/summary
  const { data: primaryData, isError: primaryError } = useQuery({
    queryKey: ["staff-workload"],
    queryFn: () =>
      api.get<{ items: StaffMember[] }>("/staff/workload", {
        getToken,
        noRetry: true,
      }),
    retry: false,
  });

  const { data: fallbackData, isError: fallbackError } = useQuery({
    queryKey: ["users-summary"],
    queryFn: () =>
      api.get<{ items: StaffMember[] }>("/users/summary", {
        getToken,
        noRetry: true,
      }),
    retry: false,
    enabled: primaryError,
  });

  // If both APIs error, don't render this section at all
  const bothFailed = primaryError && fallbackError;
  const staffMembers = primaryError
    ? fallbackData?.items ?? []
    : primaryData?.items ?? [];

  if (bothFailed || staffMembers.length === 0) {
    return null;
  }

  const displayMembers = staffMembers.slice(0, 6);

  return (
    <div>
      <h3 className="text-sm font-medium text-muted-foreground mb-3">
        Team Workload
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {displayMembers.map((member, idx) => {
          const initials = member.initials || getInitials(member.name);
          const caseCount = member.active_cases ?? member.case_count ?? 0;

          return (
            <Card key={member.id ?? `${member.name}-${idx}`} className="py-4">
              <CardContent className="flex flex-col items-center gap-2 px-3 py-0">
                <div className="w-10 h-10 rounded-full bg-primary/15 text-primary flex items-center justify-center text-sm font-bold">
                  {initials}
                </div>
                <div className="text-center min-w-0 w-full">
                  <p className="text-sm font-medium truncate">{member.name}</p>
                  {member.role && (
                    <p className="text-[10px] text-muted-foreground truncate">
                      {member.role}
                    </p>
                  )}
                </div>
                <Badge variant="secondary" className="text-[10px]">
                  {caseCount} {caseCount === 1 ? "case" : "cases"}
                </Badge>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

// ---- 4. Calendar Metrics Row -----------------------------------------------

interface CalendarSummary {
  total_events: number;
  upcoming: number;
  this_week: number;
  past_due: number;
}

export function CalendarMetrics() {
  const { getToken } = useAuth();

  const { data, isLoading } = useQuery({
    queryKey: ["calendar-summary"],
    queryFn: () =>
      api.get<CalendarSummary>("/calendar/summary", {
        getToken,
        noRetry: true,
      }),
    retry: false,
  });

  const metrics = [
    {
      label: "Total Events",
      value: data ? formatMetric(data.total_events) : "\u2014",
      color: "text-blue-400",
    },
    {
      label: "Upcoming",
      value: data ? formatMetric(data.upcoming) : "\u2014",
      color: "text-emerald-400",
    },
    {
      label: "This Week",
      value: data ? formatMetric(data.this_week) : "\u2014",
      color: "text-amber-400",
    },
    {
      label: "Past Due",
      value: data ? formatMetric(data.past_due) : "\u2014",
      color: "text-red-400",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {metrics.map((m) => (
        <Card key={m.label}>
          <CardContent className="pt-4 pb-3">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">
              {m.label}
            </p>
            {isLoading ? (
              <Skeleton className="h-8 w-20 mt-1" />
            ) : (
              <p className={`text-2xl font-bold mt-1 ${m.color}`}>{m.value}</p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ---- 5. Deadline Toast Notifications --------------------------------------

export function useDeadlineToasts() {
  const { getToken } = useAuth();
  const hasFired = useRef(false);

  // Reuse the same deadline query (shared cache key)
  const { data: primaryData, isError: primaryError } = useQuery({
    queryKey: ["deadlines-upcoming"],
    queryFn: () =>
      api.get<{ items: DeadlineItem[]; count?: number }>("/deadlines/upcoming", {
        getToken,
        noRetry: true,
      }),
    retry: false,
  });

  const { data: fallbackData } = useQuery({
    queryKey: ["cases-deadlines-14"],
    queryFn: () =>
      api.get<{ items: DeadlineItem[]; count?: number }>("/cases/deadlines", {
        params: { days: 14 },
        getToken,
        noRetry: true,
      }),
    retry: false,
    enabled: primaryError,
  });

  const rawItems = primaryError
    ? fallbackData?.items ?? []
    : primaryData?.items ?? [];

  useEffect(() => {
    if (hasFired.current) return;
    if (rawItems.length === 0) return;

    const urgent = rawItems
      .filter((d) => {
        const days = daysUntil(d.date);
        return days >= -1 && days <= 3;
      })
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
      .slice(0, 5);

    if (urgent.length === 0) return;

    hasFired.current = true;

    // Stagger toasts slightly for visual effect
    urgent.forEach((item, idx) => {
      const days = daysUntil(item.date);
      const label = item.label || item.title || "Deadline";
      const caseName = item.case_name ? ` \u2014 ${item.case_name}` : "";
      const urgencyText = deadlineUrgencyLabel(days);

      setTimeout(() => {
        if (days <= 0) {
          toast.error(`${urgencyText}: ${label}${caseName}`);
        } else {
          toast.warning(`Deadline in ${urgencyText}: ${label}${caseName}`);
        }
      }, idx * 300);
    });
  }, [rawItems]);
}
