// ---- API Route Map -------------------------------------------------------
// Centralized endpoint paths. Eliminates magic strings across all pages.
// All paths are relative to /api/v1 (prepended by api-client.ts).
//
// Usage:
//   import { routes } from "@/lib/api-routes";
//   api.get(routes.cases.byId(caseId));
//   api.post(routes.files.upload(caseId), formData);

export const routes = {
  // --- System ---
  health: "/health",
  providers: "/config/providers",

  // --- Users ---
  users: {
    list: "/users",
    me: "/users/me",
    byId: (id: string) => `/users/${id}`,
    role: (id: string) => `/users/${id}/role`,
  },

  // --- Cases ---
  cases: {
    list: "/cases",
    create: "/cases",
    byId: (id: string) => `/cases/${id}`,
    rename: (id: string) => `/cases/${id}/rename`,
    preps: (caseId: string) => `/cases/${caseId}/preps`,
    createPrep: (caseId: string) => `/cases/${caseId}/preps`,
    prep: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preps/${prepId}`,
    prepState: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preps/${prepId}/state`,
    status: (id: string) => `/cases/${id}/status`,
    contacts: (id: string) => `/cases/${id}/contacts`,
  },

  // --- Files ---
  files: {
    list: (caseId: string) => `/cases/${caseId}/files`,
    upload: (caseId: string) => `/cases/${caseId}/files/upload`,
    download: (caseId: string, filename: string) =>
      `/cases/${caseId}/files/${encodeURIComponent(filename)}`,
    delete: (caseId: string, filename: string) =>
      `/cases/${caseId}/files/${encodeURIComponent(filename)}`,
    tags: (caseId: string, filename: string) =>
      `/cases/${caseId}/files/${encodeURIComponent(filename)}/tags`,
    pin: (caseId: string, filename: string) =>
      `/cases/${caseId}/files/${encodeURIComponent(filename)}/pin`,
  },

  // --- Analysis ---
  analysis: {
    start: (caseId: string) => `/analysis/${caseId}/start`,
    progress: (caseId: string) => `/analysis/${caseId}/progress`,
    stop: (caseId: string) => `/analysis/${caseId}/stop`,
    workers: (caseId: string) => `/analysis/${caseId}/workers`,
  },

  // --- Witnesses ---
  witnesses: {
    list: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preps/${prepId}/witnesses`,
    add: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preps/${prepId}/witnesses`,
    update: (caseId: string, prepId: string, witnessId: string) =>
      `/cases/${caseId}/preps/${prepId}/witnesses/${witnessId}`,
    delete: (caseId: string, prepId: string, witnessId: string) =>
      `/cases/${caseId}/preps/${prepId}/witnesses/${witnessId}`,
  },

  // --- Evidence ---
  evidence: {
    list: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preps/${prepId}/evidence`,
    add: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preps/${prepId}/evidence`,
    update: (caseId: string, prepId: string, evidenceId: string) =>
      `/cases/${caseId}/preps/${prepId}/evidence/${evidenceId}`,
    delete: (caseId: string, prepId: string, evidenceId: string) =>
      `/cases/${caseId}/preps/${prepId}/evidence/${evidenceId}`,
    custody: (caseId: string, evidenceId: string) =>
      `/cases/${caseId}/evidence/${evidenceId}/custody`,
  },

  // --- Calendar ---
  calendar: {
    events: (caseId: string) => `/cases/${caseId}/calendar`,
    create: (caseId: string) => `/cases/${caseId}/calendar`,
    update: (caseId: string, eventId: string) =>
      `/cases/${caseId}/calendar/${eventId}`,
    delete: (caseId: string, eventId: string) =>
      `/cases/${caseId}/calendar/${eventId}`,
    deadlines: (caseId: string) => `/cases/${caseId}/calendar/deadlines`,
    chains: (caseId: string) => `/cases/${caseId}/calendar/chains`,
    chainById: (caseId: string, chainId: string) =>
      `/cases/${caseId}/calendar/chains/${chainId}`,
    global: "/calendar/all",
    globalEvents: "/calendar/events",
    globalEventById: (eventId: string) => `/calendar/events/${eventId}`,
    month: "/calendar/month",
    upcoming: "/calendar/upcoming",
    stats: "/calendar/stats",
  },

  // --- Billing ---
  billing: {
    time: (caseId: string) => `/billing/time/${caseId}`,
    timeEntry: (caseId: string, entryId: string) =>
      `/billing/time/${caseId}/${entryId}`,
    expenses: (caseId: string) => `/billing/expenses/${caseId}`,
    expense: (caseId: string, expenseId: string) =>
      `/billing/expenses/${caseId}/${expenseId}`,
    invoices: "/billing/invoices",
    invoice: (invoiceId: string) => `/billing/invoices/${invoiceId}`,
    invoiceStatus: (invoiceId: string) =>
      `/billing/invoices/${invoiceId}/status`,
    aging: "/billing/aging",
    settings: "/billing/settings",
    retainer: (caseId: string) => `/billing/retainer/${caseId}`,
    retainerTransaction: (caseId: string) =>
      `/billing/retainer/${caseId}/transaction`,
    arOverview: "/billing/ar-overview",
    revenueOverview: "/billing/revenue-overview",
  },

  // --- Tasks ---
  tasks: {
    crossCase: "/tasks",
    list: (caseId: string) => `/cases/${caseId}/tasks`,
    create: (caseId: string) => `/cases/${caseId}/tasks`,
    update: (caseId: string, taskId: string) =>
      `/cases/${caseId}/tasks/${taskId}`,
    delete: (caseId: string, taskId: string) =>
      `/cases/${caseId}/tasks/${taskId}`,
    complete: (caseId: string, taskId: string) =>
      `/cases/${caseId}/tasks/${taskId}/complete`,
  },

  // --- Documents ---
  documents: {
    drafts: (caseId: string) => `/documents/${caseId}/drafts`,
    draft: (caseId: string, draftId: string) =>
      `/documents/${caseId}/drafts/${draftId}`,
    outline: (caseId: string) => `/documents/${caseId}/outline`,
    sectionDraft: (caseId: string) => `/documents/${caseId}/sections/draft`,
    citationsBuild: (caseId: string) => `/documents/${caseId}/citations/build`,
    review: (caseId: string) => `/documents/${caseId}/review`,
    opponentAnalysis: (caseId: string) =>
      `/documents/${caseId}/opponent-analysis`,
    verifyCitations: (caseId: string) =>
      `/documents/${caseId}/verify-citations`,
    fetchPdfs: (caseId: string) => `/documents/${caseId}/fetch-pdfs`,
    exportWord: (caseId: string) => `/documents/${caseId}/export-word`,
  },

  // --- Strategy ---
  strategy: {
    state: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preps/${prepId}/strategy`,
    save: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preps/${prepId}/strategy`,
  },

  // --- Exhibits ---
  exhibits: {
    list: (caseId: string) => `/cases/${caseId}/exhibits`,
    create: (caseId: string) => `/cases/${caseId}/exhibits`,
    update: (caseId: string, exhibitId: string) =>
      `/cases/${caseId}/exhibits/${exhibitId}`,
    delete: (caseId: string, exhibitId: string) =>
      `/cases/${caseId}/exhibits/${exhibitId}`,
  },

  // --- E-Signature ---
  esign: {
    requests: (caseId: string) => `/cases/${caseId}/esign/requests`,
    send: (caseId: string) => `/cases/${caseId}/esign/send`,
    status: (caseId: string, requestId: string) =>
      `/cases/${caseId}/esign/requests/${requestId}/status`,
    remind: (caseId: string, requestId: string) =>
      `/cases/${caseId}/esign/requests/${requestId}/remind`,
    download: (caseId: string, requestId: string) =>
      `/cases/${caseId}/esign/requests/${requestId}/download`,
  },

  // --- CRM ---
  crm: {
    clients: "/crm/clients",
    client: (clientId: string) => `/crm/clients/${clientId}`,
    linkCase: (clientId: string) => `/crm/clients/${clientId}/link`,
    unlinkCase: (clientId: string) => `/crm/clients/${clientId}/unlink`,
    cases: (clientId: string) => `/crm/clients/${clientId}/cases`,
    intakeTemplates: "/crm/intake/templates",
    intake: (clientId: string) => `/crm/clients/${clientId}/intake`,
    repAgreement: (clientId: string) =>
      `/crm/clients/${clientId}/rep-agreement`,
  },

  // --- Search ---
  search: {
    global: "/search",
    inCase: (caseId: string) => `/search/case/${caseId}`,
  },

  // --- Notifications ---
  notifications: {
    list: "/notifications",
    markRead: (id: string) => `/notifications/${id}/read`,
  },

  // --- Annotations ---
  annotations: {
    list: (caseId: string) => `/cases/${caseId}/annotations`,
    create: (caseId: string) => `/cases/${caseId}/annotations`,
    delete: (caseId: string, annotationId: string) =>
      `/cases/${caseId}/annotations/${annotationId}`,
  },

  // --- Email ---
  email: {
    list: "/email",
    send: "/email/send",
  },

  // --- Export ---
  exports: {
    word: (caseId: string, prepId: string) =>
      `/export/${caseId}/${prepId}/word`,
    pdf: (caseId: string, prepId: string) =>
      `/export/${caseId}/${prepId}/pdf`,
    irac: (caseId: string, prepId: string) =>
      `/export/${caseId}/${prepId}/irac`,
    trialBinder: (caseId: string, prepId: string) =>
      `/export/${caseId}/${prepId}/trial-binder`,
    quickCards: (caseId: string, prepId: string) =>
      `/export/${caseId}/${prepId}/quick-cards`,
  },

  // --- Backup ---
  backup: {
    status: "/backup/status",
    create: "/backup/create",
    run: "/backup/run",
    list: "/backup/list",
    restore: "/backup/restore",
  },

  // --- Workflows ---
  workflows: {
    list: "/workflows",
    create: "/workflows",
    byId: (id: string) => `/workflows/${id}`,
    trigger: (id: string) => `/workflows/${id}/trigger`,
  },

  // --- Transcription ---
  transcription: {
    list: (caseId: string) => `/cases/${caseId}/transcriptions`,
    upload: (caseId: string) => `/cases/${caseId}/transcriptions/upload`,
    byId: (caseId: string, transcriptionId: string) =>
      `/cases/${caseId}/transcriptions/${transcriptionId}`,
    analyze: (caseId: string, transcriptionId: string) =>
      `/cases/${caseId}/transcriptions/${transcriptionId}/analyze`,
  },

  // --- Quality ---
  quality: {
    score: (caseId: string, prepId: string) =>
      `/quality/${caseId}/${prepId}/score`,
    costsSummary: "/quality/costs/summary",
  },

  // --- Google Calendar ---
  gcal: {
    connect: "/gcal/connect",
    events: "/gcal/events",
    sync: "/gcal/sync",
  },

  // --- Conflicts ---
  conflicts: {
    check: "/conflicts/check",
  },

  // --- SOL ---
  sol: {
    calculate: (caseId: string) => `/cases/${caseId}/sol/calculate`,
    claims: (caseId: string) => `/cases/${caseId}/sol/claims`,
    claim: (caseId: string, claimId: string) =>
      `/cases/${caseId}/sol/claims/${claimId}`,
  },

  // --- Webhooks ---
  webhooks: {
    clerk: "/webhooks/clerk",
  },

  // --- GDPR ---
  gdpr: {
    export: (userId: string) => `/gdpr/export/${userId}`,
    delete: (userId: string) => `/gdpr/delete/${userId}`,
    audit: (userId: string) => `/gdpr/audit/${userId}`,
  },

  // --- Batch ---
  batch: {
    execute: "/batch/execute",
  },

  // --- Metrics ---
  metrics: {
    prometheus: "/metrics",
  },

  // --- On-Demand AI ---
  onDemand: {
    generate: (caseId: string, tool: string) =>
      `/cases/${caseId}/on-demand/${tool}`,
    medicalChronology: (caseId: string) =>
      `/cases/${caseId}/on-demand/medical-chronology`,
    demandLetter: (caseId: string) =>
      `/cases/${caseId}/on-demand/demand-letter`,
  },

  // --- Research ---
  research: {
    lexisQueries: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preparations/${prepId}/generate/lexis-queries`,
    lexisAnalysis: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preparations/${prepId}/generate/lexis-analysis`,
    cheatSheet: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preparations/${prepId}/generate/cheat-sheet`,
  },

  // --- Module Notes ---
  moduleNotes: {
    get: (caseId: string, module: string) =>
      `/cases/${caseId}/notes/${module}`,
    save: (caseId: string, module: string) =>
      `/cases/${caseId}/notes/${module}`,
  },

  // --- Payment Plans ---
  paymentPlans: {
    list: "/payment-plans",
    create: "/payment-plans",
    byId: (planId: string) => `/payment-plans/${planId}`,
    status: (planId: string) => `/payment-plans/${planId}/status`,
    payments: (planId: string) => `/payment-plans/${planId}/payments`,
    schedule: (planId: string) => `/payment-plans/${planId}/schedule`,
  },

  // --- Communications ---
  comms: {
    queue: "/communications/queue",
    templates: "/communications/templates",
    template: (id: string) => `/communications/templates/${id}`,
    settings: "/communications/settings",
    log: "/communications/log",
    approve: (id: string) => `/communications/queue/${id}/approve`,
    dismiss: (id: string) => `/communications/queue/${id}/dismiss`,
    stats: "/communications/stats",
  },

  // --- Payment Feed ---
  paymentFeed: {
    ingestEmail: "/payment-feed/ingest-email",
    upload: "/payment-feed/upload",
    transactions: "/payment-feed/transactions",
    transaction: (id: string) => `/payment-feed/transactions/${id}`,
    confirm: (id: string) => `/payment-feed/transactions/${id}/confirm`,
    dismiss: (id: string) => `/payment-feed/transactions/${id}/dismiss`,
    reclassify: (id: string) => `/payment-feed/transactions/${id}/reclassify`,
  },

  // --- Stripe ---
  stripe: {
    config: "/stripe/config",
    paymentLink: "/stripe/payment-link",
    paymentLinks: "/stripe/payment-links",
    checkoutSessions: "/stripe/checkout-sessions",
  },

  // --- Activity ---
  activity: {
    feed: (caseId: string) => `/cases/${caseId}/activity`,
  },

  // --- Predictive Score ---
  predictiveScore: {
    score: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preparations/${prepId}/predictive-score`,
    history: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preparations/${prepId}/predictive-score/history`,
    compare: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preparations/${prepId}/predictive-score/compare`,
  },

  // --- Smart Intake ---
  intake: {
    start: "/crm/intake/start",
    step: (sessionId: string) => `/crm/intake/${sessionId}/step`,
    complete: (sessionId: string) => `/crm/intake/${sessionId}/complete`,
  },

  // --- Portal ---
  portal: {
    cases: "/portal/cases",
    case: (caseId: string) => `/portal/cases/${caseId}`,
    clientStatus: (clientId: string) => `/portal/client/${clientId}/status`,
    documents: (clientId: string) => `/portal/client/${clientId}/documents`,
    invoices: (clientId: string) => `/portal/client/${clientId}/invoices`,
    messages: (clientId: string) => `/portal/client/${clientId}/messages`,
    deadlines: (clientId: string) => `/portal/client/${clientId}/deadlines`,
  },

  // --- Morning Brief ---
  morningBrief: {
    generate: "/morning-brief/generate",
    get: "/brief",
    dismissItem: (itemId: string) => `/brief/items/${itemId}/dismiss`,
    snoozeItem: (itemId: string) => `/brief/items/${itemId}/snooze`,
    sendDigest: "/brief/send-digest",
  },

  // --- Discovery ---
  discovery: {
    data: (caseId: string) => `/cases/${caseId}/discovery`,
    createRequest: (caseId: string) =>
      `/cases/${caseId}/discovery/requests`,
    request: (caseId: string, requestId: string) =>
      `/cases/${caseId}/discovery/requests/${requestId}`,
    updateItem: (caseId: string, requestId: string, itemNum: number) =>
      `/cases/${caseId}/discovery/requests/${requestId}/items/${itemNum}`,
    draftItems: (caseId: string) =>
      `/cases/${caseId}/discovery/draft-items`,
    draftResponses: (caseId: string) =>
      `/cases/${caseId}/discovery/draft-responses`,
    productionSets: (caseId: string) =>
      `/cases/${caseId}/discovery/production-sets`,
    productionSet: (caseId: string, setId: string) =>
      `/cases/${caseId}/discovery/production-sets/${setId}`,
    privilegeLog: (caseId: string) =>
      `/cases/${caseId}/discovery/privilege-log`,
    privilegeEntry: (caseId: string, entryId: string) =>
      `/cases/${caseId}/discovery/privilege-log/${entryId}`,
    dashboard: "/discovery/dashboard",
  },

  // --- Argument Forge ---
  argumentForge: {
    session: (caseId: string) =>
      `/cases/${caseId}/argument-forge/session`,
    saveSession: (caseId: string) =>
      `/cases/${caseId}/argument-forge/session`,
    issues: (caseId: string) =>
      `/cases/${caseId}/argument-forge/issues`,
    arguments: (caseId: string) =>
      `/cases/${caseId}/argument-forge/arguments`,
    steelman: (caseId: string) =>
      `/cases/${caseId}/argument-forge/steelman`,
    counterMatrix: (caseId: string) =>
      `/cases/${caseId}/argument-forge/counter-matrix`,
    oralPrep: (caseId: string) =>
      `/cases/${caseId}/argument-forge/oral-prep`,
    score: (caseId: string) =>
      `/cases/${caseId}/argument-forge/score`,
    exportToDraft: (caseId: string) =>
      `/cases/${caseId}/argument-forge/export-to-draft`,
  },

  // --- Ethical Compliance ---
  compliance: {
    scan: (caseId: string) => `/compliance/conflicts/${caseId}/scan`,
    prospectiveClients: "/compliance/prospective-clients",
    prospectiveClient: (id: string) =>
      `/compliance/prospective-clients/${id}`,
    communicationGaps: "/compliance/communication-gaps",
    feeAgreement: (caseId: string) =>
      `/compliance/fee-agreements/${caseId}`,
    evidencePreservation: (caseId: string) =>
      `/compliance/evidence-preservation/${caseId}`,
    supervision: (caseId: string) => `/compliance/supervision/${caseId}`,
    solClaims: (caseId: string) => `/compliance/sol/${caseId}/claims`,
    solClaim: (caseId: string, claimId: string) =>
      `/compliance/sol/${caseId}/claims/${claimId}`,
  },

  // --- AI Chat ---
  aiChat: {
    send: "/ai/chat",
    caseChat: (caseId: string) => `/cases/${caseId}/ai/chat`,
    history: "/ai/chat/history",
  },

  // --- Mock Exam ---
  mockExam: {
    sessions: (caseId: string) => `/cases/${caseId}/mock-exam/sessions`,
    session: (caseId: string, sessionId: string) =>
      `/cases/${caseId}/mock-exam/sessions/${sessionId}`,
    start: (caseId: string) => `/cases/${caseId}/mock-exam/start`,
  },

  // --- Contradiction Matrix ---
  contradictions: {
    matrix: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preparations/${prepId}/contradiction-matrix`,
  },

  // --- Redaction ---
  redaction: {
    scan: (caseId: string) => `/cases/${caseId}/redaction/scan`,
    reports: (caseId: string) => `/cases/${caseId}/redaction/reports`,
    report: (caseId: string, reportId: string) =>
      `/cases/${caseId}/redaction/reports/${reportId}`,
    apply: (caseId: string) => `/cases/${caseId}/redaction/apply`,
    categories: (caseId: string) => `/cases/${caseId}/redaction/categories`,
  },

  // --- War Game ---
  warGame: {
    sessions: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preparations/${prepId}/war-game/sessions`,
    session: (caseId: string, prepId: string, sessionId: string) =>
      `/cases/${caseId}/preparations/${prepId}/war-game/sessions/${sessionId}`,
    attack: (caseId: string, prepId: string, sessionId: string, roundType: string) =>
      `/cases/${caseId}/preparations/${prepId}/war-game/sessions/${sessionId}/rounds/${roundType}/attack`,
    respond: (caseId: string, prepId: string, sessionId: string, roundType: string) =>
      `/cases/${caseId}/preparations/${prepId}/war-game/sessions/${sessionId}/rounds/${roundType}/respond`,
    finalize: (caseId: string, prepId: string, sessionId: string) =>
      `/cases/${caseId}/preparations/${prepId}/war-game/sessions/${sessionId}/finalize`,
  },

  // --- Case Q&A ---
  caseQA: {
    ask: (caseId: string, prepId: string) =>
      `/cases/${caseId}/preparations/${prepId}/generate/case-qa`,
  },
} as const;
