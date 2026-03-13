// ---- Query Key Factory ---------------------------------------------------
// Consistent cache keys for React Query. Used by useQuery and invalidation.
// Eliminates inconsistent key formats across pages.
//
// Pattern: queryKeys.{domain}.{operation}(params)
//
// Usage:
//   import { queryKeys } from "@/lib/query-keys";
//   useQuery({ queryKey: queryKeys.cases.byId(caseId), queryFn: ... });
//   queryClient.invalidateQueries({ queryKey: queryKeys.cases.all });

export const queryKeys = {
  // --- System ---
  health: ["health"] as const,
  providers: ["providers"] as const,

  // --- Users ---
  users: {
    all: ["users"] as const,
    me: ["users", "me"] as const,
    byId: (id: string) => ["users", id] as const,
  },

  // --- Cases ---
  cases: {
    all: ["cases"] as const,
    byId: (id: string) => ["cases", id] as const,
    preps: (caseId: string) => ["cases", caseId, "preps"] as const,
    prep: (caseId: string, prepId: string) =>
      ["cases", caseId, "preps", prepId] as const,
    prepState: (caseId: string, prepId: string) =>
      ["cases", caseId, "preps", prepId, "state"] as const,
  },

  // --- Files ---
  files: {
    list: (caseId: string) => ["files", caseId] as const,
  },

  // --- Analysis ---
  analysis: {
    progress: (caseId: string) => ["analysis", "progress", caseId] as const,
    workers: (caseId: string) => ["analysis", "workers", caseId] as const,
  },

  // --- Witnesses ---
  witnesses: {
    list: (caseId: string, prepId: string) =>
      ["witnesses", caseId, prepId] as const,
  },

  // --- Evidence ---
  evidence: {
    list: (caseId: string, prepId: string) =>
      ["evidence", caseId, prepId] as const,
    custody: (caseId: string, evidenceId: string) =>
      ["evidence", "custody", caseId, evidenceId] as const,
  },

  // --- Calendar ---
  calendar: {
    events: (caseId: string) => ["calendar", caseId] as const,
    deadlines: (caseId: string) => ["calendar", "deadlines", caseId] as const,
    chains: (caseId: string) => ["calendar", "chains", caseId] as const,
    global: ["calendar", "global"] as const,
  },

  // --- Billing ---
  billing: {
    time: (caseId: string) => ["billing", "time", caseId] as const,
    expenses: (caseId: string) => ["billing", "expenses", caseId] as const,
    invoices: ["billing", "invoices"] as const,
    aging: ["billing", "aging"] as const,
    settings: ["billing", "settings"] as const,
    retainer: (caseId: string) => ["billing", "retainer", caseId] as const,
    arOverview: ["billing", "ar-overview"] as const,
    revenueOverview: ["billing", "revenue-overview"] as const,
  },

  // --- Tasks ---
  tasks: {
    crossCase: ["tasks"] as const,
    byCase: (caseId: string) => ["tasks", caseId] as const,
  },

  // --- Documents ---
  documents: {
    drafts: (caseId: string) => ["documents", "drafts", caseId] as const,
    draft: (caseId: string, draftId: string) =>
      ["documents", "drafts", caseId, draftId] as const,
  },

  // --- Exhibits ---
  exhibits: {
    list: (caseId: string) => ["exhibits", caseId] as const,
  },

  // --- E-Signature ---
  esign: {
    requests: (caseId: string) => ["esign", "requests", caseId] as const,
  },

  // --- CRM ---
  crm: {
    clients: ["crm-clients"] as const,
    client: (clientId: string) => ["crm-clients", clientId] as const,
    cases: (clientId: string) => ["crm-cases", clientId] as const,
    intake: (clientId: string) => ["crm-intake", clientId] as const,
    templates: ["crm-intake-templates"] as const,
  },

  // --- Search ---
  search: {
    global: (q: string) => ["search", q] as const,
    inCase: (caseId: string, q: string) => ["search", caseId, q] as const,
  },

  // --- Notifications ---
  notifications: ["notifications"] as const,

  // --- Annotations ---
  annotations: {
    list: (caseId: string) => ["annotations", caseId] as const,
  },

  // --- Email ---
  email: ["email"] as const,

  // --- Backup ---
  backup: {
    status: ["backup", "status"] as const,
    list: ["backup", "list"] as const,
  },

  // --- Workflows ---
  workflows: {
    all: ["workflows"] as const,
  },

  // --- Transcription ---
  transcription: {
    list: (caseId: string) => ["transcription", caseId] as const,
    byId: (caseId: string, id: string) =>
      ["transcription", caseId, id] as const,
  },

  // --- Quality ---
  quality: {
    score: (caseId: string, prepId: string) =>
      ["quality", caseId, prepId] as const,
    costs: ["quality", "costs"] as const,
  },

  // --- Google Calendar ---
  gcal: {
    events: ["gcal", "events"] as const,
  },

  // --- Conflicts ---
  conflicts: ["conflicts"] as const,

  // --- SOL ---
  sol: {
    claims: (caseId: string) => ["sol", "claims", caseId] as const,
  },

  // --- GDPR ---
  gdpr: {
    audit: (userId: string) => ["gdpr", "audit", userId] as const,
  },

  // --- Module Notes ---
  moduleNotes: {
    get: (caseId: string, module: string) =>
      ["module-notes", caseId, module] as const,
  },

  // --- Payment Plans ---
  paymentPlans: {
    all: ["payment-plans"] as const,
    byId: (planId: string) => ["payment-plans", planId] as const,
    status: (planId: string) => ["payment-plans", planId, "status"] as const,
  },

  // --- Communications ---
  comms: {
    queue: ["comms", "queue"] as const,
    templates: ["comms", "templates"] as const,
    settings: ["comms", "settings"] as const,
    log: ["comms", "log"] as const,
    stats: ["comms", "stats"] as const,
  },

  // --- Payment Feed ---
  paymentFeed: {
    transactions: ["payment-feed", "transactions"] as const,
  },

  // --- Stripe ---
  stripe: {
    config: ["stripe", "config"] as const,
    paymentLinks: ["stripe", "payment-links"] as const,
    checkoutSessions: ["stripe", "checkout-sessions"] as const,
  },

  // --- Activity ---
  activity: {
    feed: (caseId: string) => ["activity", caseId] as const,
  },

  // --- Predictive Score ---
  predictiveScore: {
    score: (caseId: string, prepId: string) =>
      ["predictive-score", caseId, prepId] as const,
    history: (caseId: string, prepId: string) =>
      ["predictive-score", "history", caseId, prepId] as const,
  },

  // --- Smart Intake ---
  intake: {
    session: (sessionId: string) =>
      ["intake", sessionId] as const,
  },

  // --- Portal ---
  portal: {
    cases: ["portal", "cases"] as const,
    status: (clientId: string) => ["portal", "status", clientId] as const,
    documents: (clientId: string) => ["portal", "documents", clientId] as const,
    invoices: (clientId: string) => ["portal", "invoices", clientId] as const,
    messages: (clientId: string) => ["portal", "messages", clientId] as const,
    deadlines: (clientId: string) => ["portal", "deadlines", clientId] as const,
  },

  // --- Morning Brief ---
  morningBrief: ["morning-brief"] as const,

  // --- Discovery ---
  discovery: {
    data: (caseId: string) => ["discovery", caseId] as const,
    dashboard: ["discovery", "dashboard"] as const,
  },

  // --- Argument Forge ---
  argumentForge: {
    session: (caseId: string) => ["argument-forge", caseId] as const,
  },

  // --- Compliance ---
  compliance: {
    prospectiveClients: ["compliance", "prospective-clients"] as const,
    communicationGaps: ["compliance", "communication-gaps"] as const,
    feeAgreement: (caseId: string) =>
      ["compliance", "fee-agreement", caseId] as const,
    supervision: (caseId: string) =>
      ["compliance", "supervision", caseId] as const,
    solClaims: (caseId: string) =>
      ["compliance", "sol-claims", caseId] as const,
  },

  // --- AI Chat ---
  aiChat: {
    history: ["ai-chat", "history"] as const,
  },

  // --- Mock Exam ---
  mockExam: {
    sessions: (caseId: string) => ["mock-exam", caseId] as const,
  },

  // --- Research ---
  research: {
    lexisQueries: (caseId: string, prepId: string) =>
      ["research", "lexis-queries", caseId, prepId] as const,
    lexisAnalysis: (caseId: string, prepId: string) =>
      ["research", "lexis-analysis", caseId, prepId] as const,
    cheatSheet: (caseId: string, prepId: string) =>
      ["research", "cheat-sheet", caseId, prepId] as const,
  },

  // --- Contradiction Matrix ---
  contradictions: {
    matrix: (caseId: string, prepId: string) =>
      ["contradictions", "matrix", caseId, prepId] as const,
  },

  // --- Redaction ---
  redaction: {
    reports: (caseId: string) =>
      ["redaction", "reports", caseId] as const,
    report: (caseId: string, reportId: string) =>
      ["redaction", "report", caseId, reportId] as const,
    categories: (caseId: string) =>
      ["redaction", "categories", caseId] as const,
  },

  // --- War Game ---
  warGame: {
    sessions: (caseId: string, prepId: string) =>
      ["war-game", "sessions", caseId, prepId] as const,
    session: (caseId: string, prepId: string, sessionId: string) =>
      ["war-game", "session", caseId, prepId, sessionId] as const,
  },

  // --- Case Q&A ---
  caseQA: {
    history: (caseId: string, prepId: string) =>
      ["case-qa", "history", caseId, prepId] as const,
  },
} as const;
