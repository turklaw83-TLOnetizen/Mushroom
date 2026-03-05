// ---- Shared API Types ---------------------------------------------------
// Canonical TypeScript types for API responses. Keep in sync with backend
// Pydantic models (api/models.py).

// ---- Case ----
export interface Case {
    id: string;
    name: string;
    description: string;
    status: "active" | "archived";
    case_type: string;
    case_category: string;
    case_subcategory: string;
    client_name: string;
    assigned_to: string[];
    created_at: string;
    last_updated: string;
    jurisdiction?: string;
}

export interface CaseListResponse {
    items: Case[];
    total: number;
}

// ---- Preparation ----
export interface Preparation {
    id: string;
    type: string;
    name: string;
    created_at?: string;
    last_updated?: string;
}

// ---- Witness ----
export interface Witness {
    id: string;
    name: string;
    type: "State" | "Defense" | "Expert" | "Character";
    role: string;
    relationship: string;
    contact_info: string;
    deposition_date?: string;
    notes: string;
    credibility_score?: number;
}

// ---- Evidence ----
export interface Evidence {
    id: string;
    name: string;
    type: string;
    description: string;
    source: string;
    date_obtained?: string;
    location?: string;
    chain_of_custody?: string;
    admissibility_notes?: string;
    tags: string[];
}

// ---- Calendar Event ----
export interface CalendarEvent {
    id: string;
    title: string;
    type: "hearing" | "deposition" | "meeting" | "deadline" | "trial" | "other";
    date: string;
    time?: string;
    end_date?: string;
    location?: string;
    description?: string;
    reminder_days?: number;
}

// ---- Billing ----
export interface TimeEntry {
    id: string;
    date: string;
    hours: number;
    rate: number;
    description: string;
    attorney: string;
    billable: boolean;
}

export interface Expense {
    id: string;
    date: string;
    amount: number;
    category: string;
    description: string;
    receipt_path?: string;
}

// ---- Analysis ----
export interface AnalysisProgress {
    status: "idle" | "running" | "complete" | "error" | "stopping";
    progress: number;
    current_module: string;
    module_description?: string;
    error: string;
    elapsed_seconds?: number;
    completed_modules?: string[];
    total_modules?: number;
    tokens_used?: number;
}

// ---- Worker Status ----
export interface WorkerStatus {
    analysis: { status: string; progress?: number; current_module?: string; error?: string };
    ingestion: { status: string; progress?: number; error?: string };
    ocr: { status: string; progress?: number; error?: string };
}

// ---- API Response Wrappers ----
export interface ListResponse<T> {
    items: T[];
    total?: number;
}

export interface ErrorResponse {
    error: string;
    detail: string;
    request_id?: string;
}

// ---- File ----
export interface CaseFile {
    filename: string;
    size_bytes: number;
    uploaded_at: string;
    mime_type?: string;
    tags: string[];
    page_count?: number;
}

export interface FileItem {
    filename: string;
    size: number;
    tags: string[];
    uploaded_at?: string;
    ocr_status?: string;
}

// ---- Client (CRM) ----
export interface Client {
    id: string;
    name: string;
    email: string;
    phone: string;
    company: string;
    cases: string[];
    created_at: string;
}

// ---- Task ----
export interface Task {
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

// ---- Evidence Item (case-level) ----
export interface EvidenceItem {
    id: string;
    description: string;
    type: string;
    source: string;
    foundation: string;
    tags: string[];
}

// ---- User ----
export interface UserItem {
    id: string;
    name: string;
    initials: string;
    role: string;
    email: string;
    active: boolean;
}

// ---- Health / Admin ----
export interface HealthData {
    status: string;
    database: string;
    version: string;
    uptime_seconds?: number;
    latency_ms?: number;
}

export interface TeamStats {
    total_users: number;
    active_users: number;
    admins: number;
    attorneys: number;
    paralegals: number;
}
