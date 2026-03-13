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
    pinned?: boolean;
}

// ---- Client (CRM) ----
export interface RepAgreement {
    filename: string;
    uploaded_at: string;
    uploaded_by: string;
    size_bytes: number;
}

export interface Client {
    id: string;
    name: string;
    email: string;
    phone: string;
    company: string;
    cases: string[];
    created_at: string;
    rep_agreement?: RepAgreement | null;
}

// ---- Payment Plan ----
export interface ScheduledPayment {
    id: string;
    due_date: string;
    amount: number;
    type: "down_payment" | "recurring" | "final";
    status: "pending" | "paid" | "partial" | "overdue" | "waived";
    paid_amount: number;
    paid_date: string | null;
    late_fee_applied: number;
}

export interface PaymentRecord {
    id: string;
    date: string;
    amount: number;
    method: string;
    payer_name: string;
    note: string;
    scheduled_payment_id: string | null;
    recorded_by: string;
    recorded_at: string;
}

export interface PaymentPlan {
    id: string;
    client_id: string;
    client_name: string;
    total_amount: number;
    down_payment: number;
    recurring_amount: number;
    frequency: "weekly" | "biweekly" | "monthly";
    start_date: string;
    end_date: string;
    status: "active" | "completed" | "paused" | "cancelled";
    late_fee_amount: number;
    late_fee_grace_days: number;
    notes: string;
    created_at: string;
    updated_at: string;
    scheduled_payments: ScheduledPayment[];
    payments: PaymentRecord[];
    history: Array<{ timestamp: string; action: string; details: string; user: string }>;
    health?: "on_track" | "behind" | "at_risk" | "ahead" | "completed" | "paused" | "cancelled";
}

export interface PaymentPlanStatus {
    plan_id: string;
    total_amount: number;
    total_paid: number;
    remaining: number;
    next_due_date: string | null;
    next_due_amount: number;
    status: "on_track" | "behind" | "ahead" | "completed" | "paused" | "cancelled" | "no_plan";
    overdue_amount: number;
    overdue_count: number;
    payments_made: number;
    payments_remaining: number;
    percent_complete: number;
}

export interface PaymentPlanSummary {
    plan_id: string;
    client_id: string;
    client_name: string;
    total_amount: number;
    total_paid: number;
    remaining: number;
    next_due_date?: string | null;
    status: string;
    overdue_amount?: number;
    created_at?: string;
    start_date?: string;
    frequency?: string;
    notes?: string;
}

export interface AROverview {
    total_plans: number;
    active_plans: number;
    total_receivable: number;
    total_collected: number;
    total_overdue: number;
    overdue_count: number;
    plans: PaymentPlanSummary[];
}

export interface RevenueOverview {
    total_plans: number;
    total_revenue: number;
    completed_revenue: number;
    active_revenue: number;
    total_outstanding: number;
    plans: PaymentPlanSummary[];
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
    category: string;
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

// ---- Client Communications ----
export interface CommQueueItem {
    id: string;
    client_id: string;
    case_id: string;
    trigger_type: string;
    trigger_id: string;
    channel: string;
    subject: string;
    body_html: string;
    body_sms: string;
    status: "pending" | "approved" | "sent" | "failed" | "dismissed";
    priority: string;
    scheduled_for: string;
    created_at: string;
    reviewed_at: string | null;
    reviewed_by: string | null;
    sent_at: string | null;
    send_result: string | null;
    dismissed_reason: string;
    metadata: {
        client_name?: string;
        client_email?: string;
        client_phone?: string;
        case_name?: string;
        amount_due?: number;
        due_date?: string;
        event_title?: string;
    };
}

export interface CommTemplate {
    id: string;
    name: string;
    trigger_type: string;
    channel: string;
    subject_template: string;
    body_template: string;
    sms_template: string;
    ai_enhance: boolean;
    active: boolean;
    created_at: string;
    updated_at?: string;
}

export interface CommLogEntry {
    id: string;
    comm_id: string;
    client_id: string;
    case_id: string;
    channel: string;
    subject: string;
    body: string;
    sent_at: string;
    sent_to: string;
    status: string;
    trigger_type: string;
    approved_by: string;
}

export interface CommSettings {
    triggers: Record<string, {
        active: boolean;
        days_before?: number[];
        days_after?: number[];
        days_after_intake?: number[];
        use_event_reminder_days?: boolean;
        channels: string[];
    }>;
    firm_name: string;
    default_sender_name: string;
    updated_at?: string | null;
}

export interface CommQueueStats {
    pending: number;
    approved: number;
    sent: number;
    failed: number;
    dismissed: number;
}

// ---- Payment Feed ----
export interface FeedTransaction {
    id: string;
    platform: string;
    date: string;
    amount: number;
    sender: string;
    note: string;
    type: string;
    source?: "csv" | "email";
    status: "unclassified" | "classified" | "recorded" | "dismissed";
    suggested_client_id: string | null;
    suggested_plan_id: string | null;
    suggested_client_name?: string;
    confidence: number;
    classification_reason: string;
    imported_at: string;
    recorded_payment_id?: string;
    dismissed_reason?: string;
}

// ---- Stripe ----
export interface StripePaymentLink {
    id: string;
    stripe_link_id: string;
    url: string;
    client_id: string;
    plan_id: string;
    client_name: string;
    amount_cents: number;
    amount: number;
    description: string;
    status: "active" | "paid" | "expired";
    created_at: string;
    paid_at: string | null;
    payment_intent_id: string | null;
}

export interface StripeCheckoutSession {
    id: string;
    stripe_session_id: string;
    url: string;
    client_id: string;
    plan_id: string;
    client_name: string;
    amount_cents: number;
    amount: number;
    description: string;
    status: "pending" | "paid" | "expired";
    created_at: string;
    paid_at: string | null;
    payment_intent_id: string | null;
}

export interface StripeConfig {
    configured: boolean;
    public_key: string;
    webhook_configured: boolean;
    base_url: string;
}

// ---- Discovery Command Center ----
export interface DiscoveryItem {
    number: number;
    text: string;
    response: string;
    objection: string;
    status: "pending" | "answered" | "objected" | "supplemented";
}

export interface DiscoveryRequest {
    id: string;
    direction: "outbound" | "inbound";
    request_type: "interrogatories" | "rfp" | "rfa";
    title: string;
    served_on: string;
    served_by: string;
    date_served: string;
    response_due: string;
    status: "draft" | "served" | "response_pending" | "response_received" | "deficient" | "motion_to_compel" | "complete";
    items: DiscoveryItem[];
    notes: string;
    created_at: string;
    updated_at: string;
    ai_drafted: boolean;
    targeting: Record<string, unknown>;
}

export interface ProductionSet {
    id: string;
    title: string;
    case_id: string;
    bates_prefix: string;
    documents: Array<{
        filename: string;
        bates_range: string;
        description: string;
        page_count: number;
    }>;
    produced_to: string;
    date_produced: string;
    status: "preparing" | "produced" | "supplemented";
    created_at: string;
    updated_at: string;
}

export interface PrivilegeEntry {
    id: string;
    document: string;
    bates_number: string;
    privilege_type: "attorney-client" | "work_product" | "joint_defense" | "other";
    description: string;
    date: string;
    from_party: string;
    to_party: string;
    subject: string;
    basis: string;
    created_at: string;
}

export interface DiscoverySummary {
    total_requests: number;
    outbound: number;
    inbound: number;
    by_type: Record<string, number>;
    by_status: Record<string, number>;
    overdue: number;
    total_items: number;
    items_pending: number;
    items_answered: number;
    production_sets: number;
    privilege_entries: number;
}

export interface DiscoveryData {
    civil: boolean;
    case_type: string;
    requests: DiscoveryRequest[];
    production_sets: ProductionSet[];
    privilege_log: PrivilegeEntry[];
    summary: DiscoverySummary;
}

export interface DraftResultItem {
    number: number;
    text: string;
    targeting_rationale: string;
}

export interface CrossCaseDiscoveryItem {
    case_id: string;
    case_name: string;
    case_type: string;
    request_id: string;
    direction: string;
    request_type: string;
    title: string;
    status: string;
    date_served: string;
    response_due: string;
    is_overdue: boolean;
    days_until_due: number | null;
    item_count: number;
}

// ---- Major Document Drafter ----
export interface DocOutlineSection {
    section_num: string;
    title: string;
    description: string;
    estimated_pages: number;
    instructions?: string;
}

export interface DocOutline {
    document_title: string;
    outline: DocOutlineSection[];
}

export interface DraftedSection extends DocOutlineSection {
    content: string;
    citations_used: DocCitation[];
}

export interface DocCitation {
    case_name: string;
    citation: string;
    holding: string;
    relevance: string;
    source: string;
}

export interface BriefReview {
    overall_score: number;
    grade: string;
    issues: Array<{
        category: string;
        severity: string;
        section: string;
        description: string;
        fix: string;
    }>;
    strengths: string[];
    suggestions: string[];
}

export interface OpponentAnalysis {
    opponent_arguments: Array<{
        number: number;
        argument: string;
        section_ref: string;
        strength: string;
    }>;
    opponent_citations: Array<{
        case_name: string;
        citation: string;
        purpose: string;
    }>;
    counter_arguments: Array<{
        opposing_arg_number: number;
        counter: string;
        supporting_evidence: string;
        supporting_law: string;
    }>;
    weaknesses: string[];
    response_strategy: string;
}

export interface CitationVerification {
    verified: Array<{
        case_name: string;
        citation: string;
        exists: boolean;
        citation_correct: boolean;
        holding_accurate: boolean;
        still_good_law: boolean;
        confidence: number;
        notes: string;
    }>;
    flagged: Array<{
        case_name: string;
        citation: string;
        exists: boolean;
        citation_correct: boolean;
        holding_accurate: boolean;
        still_good_law: boolean;
        confidence: number;
        notes: string;
    }>;
    summary: string;
}

export interface MajorDraft {
    id: string;
    title: string;
    doc_type: string;
    doc_subtype: string;
    outline: DocOutlineSection[];
    sections: DraftedSection[];
    citation_library: DocCitation[];
    review_results?: BriefReview;
    attorney_info?: Record<string, string>;
    config?: Record<string, string>;
    created_at: string;
    updated_at: string;
}

export const DOC_TYPES: Record<string, string[]> = {
    "Appellate Brief": ["Opening Brief", "Reply Brief", "Amicus Brief"],
    "Post-Conviction Relief": ["PCR Petition", "Habeas Corpus", "Coram Nobis"],
    "Civil Complaint": ["Initial Complaint", "Amended Complaint", "Counterclaim", "Third-Party Complaint"],
    "Appellate Motion": ["Motion for Extension", "Motion to Stay", "Motion for Rehearing"],
    "Major Motion": ["Motion for Summary Judgment", "Motion to Dismiss", "Motion for New Trial"],
    "Custom Document": [],
};

// ---- Argument Forge ----
export interface LegalIssue {
    id: string;
    title: string;
    description: string;
    frameworks: string[];
    priority: "high" | "medium" | "low";
}

export interface ForgeArgument {
    framework: string;
    thesis: string;
    reasoning: string;
    supporting_law: string;
    supporting_facts: string;
    strength: number;
}

export interface OppositionArgument {
    responding_to: number;
    position: string;
    reasoning: string;
    legal_basis: string;
    strength: number;
}

export interface CounterMatrixEntry {
    our_argument: string;
    their_counter: string;
    our_rebuttal: string;
    net_advantage: "ours" | "theirs" | "neutral";
    confidence: number;
}

export interface OralSegment {
    topic: string;
    duration_minutes: number;
    key_points: string[];
    transitions: string;
}

export interface ScoredArgument {
    argument: string;
    win_probability: number;
    risk_factors: string[];
    recommendation: string;
}

export interface ArgumentSession {
    id: string;
    name: string;
    created_at: string;
    issues?: LegalIssue[];
    arguments?: ForgeArgument[];
    opposition?: OppositionArgument[];
    counter_matrix?: CounterMatrixEntry[];
    oral_prep?: OralSegment[];
    scores?: ScoredArgument[];
    overall_confidence?: number;
}

// ---- Ethical Compliance ----
export interface ComplianceDashboard {
    overdue_deadlines: Array<Record<string, unknown>>;
    upcoming_deadlines: Array<Record<string, unknown>>;
    communication_gaps: Array<{
        case_id: string;
        case_name: string;
        last_contact: string | null;
        days_since: number | null;
        urgency: string;
        status: string;
    }>;
    missing_fee_agreements: Array<Record<string, unknown>>;
    prospective_count: number;
    score: number;
    total_issues: number;
}

export interface SmartConflictMatch {
    name: string;
    matched_name: string;
    source: string;
    current_role?: string;
    other_case?: string;
    other_case_id?: string;
    other_role?: string;
    severity: string;
    match_type: string;
    confidence: number;
    explanation: string;
}

export interface SmartConflictResult {
    conflicts: SmartConflictMatch[];
    prospective_hits: SmartConflictMatch[];
    cases_scanned: number;
    entities_checked: number;
}

export interface ProspectiveClient {
    id: string;
    name: string;
    subject: string;
    disclosed_info: string;
    date: string;
    notes: string;
    declined_reason: string;
    created_at: string;
}

export interface FeeAgreementData {
    fee_type: string;
    rate: string;
    retainer: string;
    scope: string;
    signed: boolean;
    signed_date: string;
    created_at?: string;
}

export interface SupervisionEntry {
    id: string;
    task: string;
    assignee: string;
    supervisor: string;
    status: string;
    date: string;
    notes: string;
}

// ---- Legal Research ---------------------------------------------------------

export interface LexisQuery {
  search_string: string;
  description: string;
  filters: {
    jurisdiction?: string;
    date_range?: string;
    court_level?: string;
  };
  case_relevance: string;
}

export interface LexisAnalysisCase {
  citation: string;
  court?: string;
  year?: string;
  holding: string;
  relevant_facts: string;
  favorability: "FAVORABLE" | "UNFAVORABLE" | "NEUTRAL";
  strategic_use: string;
  key_quotes: string[];
  strength: "HIGH" | "MEDIUM" | "LOW";
}

export interface LexisAnalysisResult {
  cases: LexisAnalysisCase[];
  summary: string;
  recommended_next_searches: string[];
  _parse_error?: boolean;
}

// ---- Contradiction Matrix ---------------------------------------------------

export interface ContradictionFinding {
  id: number;
  category: "factual" | "temporal" | "identity" | "quantity" | "sequence" | "omission";
  doc_a_says: string;
  doc_b_says: string;
  severity: "critical" | "significant" | "minor";
  impeachment_value: "high" | "medium" | "low";
  explanation: string;
  suggested_question: string;
}

export interface DocumentComparison {
  doc_a: string;
  doc_b: string;
  relationship: "contradicts" | "supports" | "supplements" | "mixed";
  contradictions: ContradictionFinding[];
  timeline_discrepancies: { event: string; doc_a_time: string; doc_b_time: string; gap: string; significance: string }[];
  omissions: { present_in: string; missing_from: string; detail: string; significance: string }[];
  corroborations: { fact: string; significance: string }[];
}

export interface ContradictionMatrix {
  generated_at: string;
  document_count: number;
  pairs_compared: number;
  total_contradictions: number;
  critical_findings: number;
  matrix: DocumentComparison[];
  by_severity: { critical: ContradictionFinding[]; significant: ContradictionFinding[]; minor: ContradictionFinding[] };
  by_document: Record<string, { contradictions_found: number; most_contradicted_by: string }>;
  by_entity: Record<string, { doc_a: string; doc_b: string; what_they_disagree_on: string }[]>;
  executive_summary: string;
  impeachment_priorities: { rank: number; target_document: string; against_document?: string; contradiction_id?: number; why: string }[];
  investigation_leads: { lead: string; based_on: string; priority: string }[];
}

// ---- Redaction ---------------------------------------------------------------

export interface RedactionFinding {
  category: string;
  text: string;
  start: number;
  end: number;
  context: string;
  confidence: "high" | "medium" | "low";
  source: "regex" | "llm";
}

export interface RedactionReport {
  id: string;
  case_id?: string;
  scan_type?: string;
  scanned_at?: string;
  saved_at?: string;
  categories?: string[];
  filename?: string;
  files?: Record<string, {
    findings_count: number;
    summary: Record<string, number>;
    findings?: RedactionFinding[];
  }>;
  per_file_summary?: Record<string, { findings_count: number; summary: Record<string, number> }>;
  total_findings?: number;
  total_redactions?: number;
  summary?: Record<string, number>;
  by_category?: Record<string, number>;
  findings?: RedactionFinding[];
  redaction_log?: {
    document: string;
    total_redactions: number;
    entries: { id: number; category: string; basis: string; description: string }[];
  };
}

export interface RedactionCategory {
  key: string;
  label: string;
  has_pattern: boolean;
  requires_llm: boolean;
  default: boolean;
}

// ---- War Game ---------------------------------------------------------------

export interface WarGameRound {
  type: "theory" | "evidence" | "witnesses" | "elements" | "jury";
  status: "pending" | "attacking" | "awaiting_response" | "evaluating" | "completed";
  attack: string | null;
  response: string | null;
  evaluation: {
    score: number;
    strengths: string[];
    vulnerabilities: string[];
    rulings?: { item: string; ruling: "admitted" | "excluded"; reasoning: string }[];
    witness_scores?: { name: string; credibility: number; vulnerabilities: string[] }[];
    element_coverage?: { charge: string; element: string; covered: boolean; gap: string }[];
  } | null;
}

export interface WarGameReport {
  overall_score: number;
  verdict: string;
  executive_summary?: string;
  round_scores: { type: string; score: number }[];
  vulnerabilities: {
    rank: number;
    severity: "critical" | "high" | "medium" | "low";
    area: string;
    description: string;
    exploit_scenario: string;
    mitigation: string;
  }[];
  contingency_cards: {
    trigger: string;
    response: string;
    authority: string;
    evidence_to_cite: string;
    risk_level: "low" | "medium" | "high";
  }[];
  juror_verdicts: { juror: string; vote: string; reasoning: string }[];
}

export interface WarGameSession {
  id: string;
  case_id?: string;
  prep_id?: string;
  difficulty: "standard" | "aggressive" | "ruthless";
  status: "active" | "completed";
  created_at: string;
  updated_at: string;
  rounds: WarGameRound[];
  report: WarGameReport | null;
  current_round: number;
}

// ---- Predictive Case Score ----
export interface PredictiveScoreDimension {
  score: number;
  grade: string;
  signals: string[];
  concerns: string[];
}

export interface PredictiveScore {
  overall_score: number;
  overall_grade: string;
  overall_label: string;
  dimensions: {
    evidence_strength: PredictiveScoreDimension;
    witness_reliability: PredictiveScoreDimension;
    element_coverage: PredictiveScoreDimension;
    legal_authority: PredictiveScoreDimension;
    narrative_coherence: PredictiveScoreDimension;
    adversarial_resilience: PredictiveScoreDimension;
  };
  top_strengths: { dimension: string; signal: string; impact: string }[];
  top_vulnerabilities: { dimension: string; concern: string; suggested_action: string; impact: string }[];
  trend: "improving" | "declining" | "stable" | null;
  previous_score: number | null;
  computed_at: string;
}

export interface ScoreHistoryEntry {
  overall_score: number;
  overall_grade: string;
  overall_label: string;
  dimension_scores: Record<string, number>;
  computed_at: string;
}

// ---- Smart Intake Wizard ----
export interface IntakeField {
  name: string;
  type: "text" | "textarea" | "select" | "date" | "email" | "tel";
  label: string;
  required: boolean;
  options?: string[];
  placeholder?: string;
}

export interface IntakeStep {
  step: number;
  title: string;
  fields: IntakeField[];
  complete?: boolean;
  summary?: Record<string, unknown>;
}

export interface IntakeSession {
  session_id: string;
  template: string;
  current_step: IntakeStep;
}

// ---- Client Portal (Extended) ----
export interface PortalDocument {
  filename: string;
  tags: string[];
  case_id: string;
  case_name: string;
  uploaded_at: string;
  size_bytes: number;
}

export interface PortalInvoice {
  id: string;
  invoice_number: string;
  case_id: string;
  status: "draft" | "sent" | "paid" | "overdue" | "partial";
  total: number;
  amount_paid: number;
  balance_due: number;
  date_created: string;
  due_date: string;
}

export interface PortalMessage {
  id: string;
  direction: "firm_to_client" | "client_to_firm";
  subject: string;
  body: string;
  channel: string;
  sent_at: string;
  status: string;
}

export interface PortalDeadline {
  id: string;
  title: string;
  event_type: string;
  date: string;
  time: string;
  location: string;
  case_id: string;
  status: string;
  days_until: number;
}

export interface PortalPaymentPlan {
  id: string;
  status: string;
  total_amount: number;
  total_paid: number;
  remaining: number;
  upcoming_payments: { due_date: string; amount: number; status: string }[];
}
