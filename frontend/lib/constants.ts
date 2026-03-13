// ---- Shared Constants ----------------------------------------------------
// Consolidates status colors, type labels, and common UI constants.
// Replaces 15+ duplicated color maps scattered across pages.

// ---- Status Color Classes ------------------------------------------------
// These map status strings → Tailwind class strings for Badge components.
// Format: "bg-{color}/15 text-{color} border-{color}/30" for the custom outline variant.

/** E-Signature request statuses */
export const ESIGN_STATUS_COLORS: Record<string, string> = {
    pending: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    sent: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    viewed: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30",
    signed: "bg-green-500/15 text-green-400 border-green-500/30",
    declined: "bg-red-500/15 text-red-400 border-red-500/30",
    cancelled: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    expired: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    not_configured: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    error: "bg-red-500/15 text-red-400 border-red-500/30",
};

/** Discovery request statuses */
export const DISCOVERY_STATUS_COLORS: Record<string, string> = {
    draft: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    served: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    response_pending: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    response_received: "bg-green-500/15 text-green-400 border-green-500/30",
    deficient: "bg-red-500/15 text-red-400 border-red-500/30",
    motion_to_compel: "bg-red-500/15 text-red-300 border-red-500/30",
    complete: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
};

/** Communication queue statuses */
export const COMM_STATUS_COLORS: Record<string, string> = {
    pending: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    approved: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    sent: "bg-green-500/15 text-green-400 border-green-500/30",
    failed: "bg-red-500/15 text-red-400 border-red-500/30",
    dismissed: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
};

/** Invoice statuses */
export const INVOICE_STATUS_COLORS: Record<string, string> = {
    draft: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    sent: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    paid: "bg-green-500/15 text-green-400 border-green-500/30",
    overdue: "bg-red-500/15 text-red-400 border-red-500/30",
    partial: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    void: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
};

/** Payment plan health */
export const PLAN_HEALTH_COLORS: Record<string, string> = {
    on_track: "bg-green-500/15 text-green-400 border-green-500/30",
    ahead: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    behind: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    at_risk: "bg-red-500/15 text-red-400 border-red-500/30",
    completed: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    paused: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    cancelled: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
};

/** Task / generic priority */
export const PRIORITY_COLORS: Record<string, string> = {
    high: "bg-red-500/15 text-red-400 border-red-500/30",
    medium: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    low: "bg-green-500/15 text-green-400 border-green-500/30",
    critical: "bg-red-500/15 text-red-300 border-red-500/30",
};

/** Task status */
export const TASK_STATUS_COLORS: Record<string, string> = {
    pending: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    in_progress: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    completed: "bg-green-500/15 text-green-400 border-green-500/30",
    blocked: "bg-red-500/15 text-red-400 border-red-500/30",
    cancelled: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
};

/** Conflict severity */
export const SEVERITY_COLORS: Record<string, string> = {
    critical: "bg-red-500/15 text-red-300 border-red-500/30",
    high: "bg-red-500/15 text-red-400 border-red-500/30",
    medium: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    low: "bg-green-500/15 text-green-400 border-green-500/30",
    info: "bg-blue-500/15 text-blue-400 border-blue-500/30",
};

/** Witness types */
export const WITNESS_TYPE_COLORS: Record<string, string> = {
    State: "bg-red-500/15 text-red-400 border-red-500/30",
    Defense: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    Expert: "bg-purple-500/15 text-purple-400 border-purple-500/30",
    Character: "bg-green-500/15 text-green-400 border-green-500/30",
};

/** Payment feed transaction statuses */
export const FEED_TX_STATUS_COLORS: Record<string, string> = {
    unclassified: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    classified: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    recorded: "bg-green-500/15 text-green-400 border-green-500/30",
    dismissed: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
};

/** Scheduled payment statuses */
export const PAYMENT_STATUS_COLORS: Record<string, string> = {
    pending: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    paid: "bg-green-500/15 text-green-400 border-green-500/30",
    partial: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    overdue: "bg-red-500/15 text-red-400 border-red-500/30",
    waived: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
};

/** Stripe link / session statuses */
export const STRIPE_STATUS_COLORS: Record<string, string> = {
    active: "bg-green-500/15 text-green-400 border-green-500/30",
    paid: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    expired: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    pending: "bg-amber-500/15 text-amber-400 border-amber-500/30",
};

/** War Game difficulty levels */
export const WAR_GAME_DIFFICULTY_COLORS: Record<string, string> = {
    standard: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    aggressive: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    ruthless: "bg-red-500/15 text-red-400 border-red-500/30",
};

/** War Game verdict outcomes */
export const VERDICT_COLORS: Record<string, string> = {
    favorable: "bg-green-500/15 text-green-400 border-green-500/30",
    unfavorable: "bg-red-500/15 text-red-400 border-red-500/30",
    mixed: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    not_guilty: "bg-green-500/15 text-green-400 border-green-500/30",
    guilty: "bg-red-500/15 text-red-400 border-red-500/30",
    hung: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    not_liable: "bg-green-500/15 text-green-400 border-green-500/30",
    liable: "bg-red-500/15 text-red-400 border-red-500/30",
};

/** Vulnerability / issue severity badges */
export const SEVERITY_BADGE_COLORS: Record<string, string> = {
    critical: "bg-red-500/15 text-red-400 border-red-500/30",
    high: "bg-orange-500/15 text-orange-400 border-orange-500/30",
    medium: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    low: "bg-blue-500/15 text-blue-400 border-blue-500/30",
};

/** Predictive case score ranges */
export const SCORE_RANGE_COLORS: Record<string, string> = {
    excellent: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    good: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    fair: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    poor: "bg-red-500/15 text-red-400 border-red-500/30",
};

/** Portal invoice statuses */
export const PORTAL_INVOICE_COLORS: Record<string, string> = {
    paid: "bg-green-500/15 text-green-400 border-green-500/30",
    unpaid: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    sent: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    overdue: "bg-red-500/15 text-red-400 border-red-500/30",
    partial: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    draft: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
};

/** Contradiction severity */
export const CONTRADICTION_SEVERITY_COLORS: Record<string, string> = {
    critical: "bg-red-500/15 text-red-400 border-red-500/30",
    significant: "bg-orange-500/15 text-orange-400 border-orange-500/30",
    minor: "bg-blue-500/15 text-blue-400 border-blue-500/30",
};

/** Contradiction categories */
export const CONTRADICTION_CATEGORY_COLORS: Record<string, string> = {
    factual: "bg-red-500/15 text-red-400 border-red-500/30",
    temporal: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    identity: "bg-purple-500/15 text-purple-400 border-purple-500/30",
    quantity: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    sequence: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30",
    omission: "bg-gray-500/15 text-gray-400 border-gray-500/30",
};

/** Detection confidence levels */
export const CONFIDENCE_COLORS: Record<string, string> = {
    high: "bg-green-500/15 text-green-400 border-green-500/30",
    medium: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    low: "bg-red-500/15 text-red-400 border-red-500/30",
};

/** Document relationship types */
export const RELATIONSHIP_COLORS: Record<string, string> = {
    contradicts: "bg-red-500/15 text-red-400 border-red-500/30",
    supports: "bg-green-500/15 text-green-400 border-green-500/30",
    supplements: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    mixed: "bg-amber-500/15 text-amber-400 border-amber-500/30",
};

/** Generic fallback — maps common status words to badge classes */
export const GENERIC_STATUS_COLORS: Record<string, string> = {
    // Positive
    active: "bg-green-500/15 text-green-400 border-green-500/30",
    success: "bg-green-500/15 text-green-400 border-green-500/30",
    complete: "bg-green-500/15 text-green-400 border-green-500/30",
    completed: "bg-green-500/15 text-green-400 border-green-500/30",
    signed: "bg-green-500/15 text-green-400 border-green-500/30",
    paid: "bg-green-500/15 text-green-400 border-green-500/30",
    resolved: "bg-green-500/15 text-green-400 border-green-500/30",
    approved: "bg-green-500/15 text-green-400 border-green-500/30",
    // Warning
    pending: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    in_progress: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    partial: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    draft: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    // Negative
    failed: "bg-red-500/15 text-red-400 border-red-500/30",
    error: "bg-red-500/15 text-red-400 border-red-500/30",
    declined: "bg-red-500/15 text-red-400 border-red-500/30",
    overdue: "bg-red-500/15 text-red-400 border-red-500/30",
    blocked: "bg-red-500/15 text-red-400 border-red-500/30",
    // Neutral
    cancelled: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    expired: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    dismissed: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    archived: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    void: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
    inactive: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
};

// ---- Helper: get status colors by domain --------------------------------

export type StatusDomain =
    | "esign" | "discovery" | "comm" | "invoice" | "plan_health"
    | "priority" | "task" | "severity" | "witness" | "feed_tx"
    | "payment" | "stripe" | "generic";

const DOMAIN_MAP: Record<StatusDomain, Record<string, string>> = {
    esign: ESIGN_STATUS_COLORS,
    discovery: DISCOVERY_STATUS_COLORS,
    comm: COMM_STATUS_COLORS,
    invoice: INVOICE_STATUS_COLORS,
    plan_health: PLAN_HEALTH_COLORS,
    priority: PRIORITY_COLORS,
    task: TASK_STATUS_COLORS,
    severity: SEVERITY_COLORS,
    witness: WITNESS_TYPE_COLORS,
    feed_tx: FEED_TX_STATUS_COLORS,
    payment: PAYMENT_STATUS_COLORS,
    stripe: STRIPE_STATUS_COLORS,
    generic: GENERIC_STATUS_COLORS,
};

/**
 * Get the CSS classes for a status value within a domain.
 * Falls back to GENERIC_STATUS_COLORS, then to a neutral gray.
 */
export function getStatusColor(status: string, domain: StatusDomain = "generic"): string {
    const map = DOMAIN_MAP[domain];
    return map[status] ?? GENERIC_STATUS_COLORS[status] ?? "bg-zinc-500/15 text-zinc-400 border-zinc-500/30";
}

// ---- Common Label Formatters --------------------------------------------

/** Formats snake_case or kebab-case to Title Case */
export function formatLabel(value: string): string {
    return value
        .replace(/[_-]/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Format ISO date string to readable date */
export function formatDate(iso: string | null | undefined): string {
    if (!iso) return "\u2014";
    try {
        return new Date(iso).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    } catch {
        return iso;
    }
}

/** Format ISO date to relative time (e.g., "2 hours ago") */
export function formatRelativeTime(iso: string | null | undefined): string {
    if (!iso) return "\u2014";
    try {
        const date = new Date(iso);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        if (diffMins < 1) return "just now";
        if (diffMins < 60) return `${diffMins}m ago`;
        const diffHours = Math.floor(diffMins / 60);
        if (diffHours < 24) return `${diffHours}h ago`;
        const diffDays = Math.floor(diffHours / 24);
        if (diffDays < 30) return `${diffDays}d ago`;
        return formatDate(iso);
    } catch {
        return iso;
    }
}

/** Format byte count to human readable (e.g., 1.5 MB) */
export function formatBytes(bytes: number): string {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(i > 0 ? 1 : 0)} ${sizes[i]}`;
}

/** Format currency value (USD) */
export function formatCurrency(amount: number): string {
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 2,
    }).format(amount);
}
