/**
 * Shared test fixtures and mock data for Project Mushroom Cloud frontend tests.
 * Mirrors the Python fixtures in tests/helpers/fixtures.py for consistency.
 */

// ── Case ──

export const mockCriminalCase = {
  id: "case__criminal_001",
  name: "State v. Marcus Thompson",
  description: "Aggravated assault case with multiple witnesses",
  status: "active",
  phase: "active",
  case_type: "criminal",
  client_name: "Marcus Thompson",
  assigned_to: ["DJT"],
  created_at: "2026-01-10T09:00:00",
  last_updated: "2026-03-01T14:30:00",
};

export const mockCivilCase = {
  id: "case__civil_001",
  name: "Johnson v. Metro Corp",
  description: "Personal injury from workplace accident",
  status: "active",
  phase: "active",
  case_type: "civil-plaintiff",
  client_name: "Robert Johnson",
  assigned_to: ["DJT", "CRJ"],
  created_at: "2026-02-01T10:00:00",
  last_updated: "2026-03-05T11:00:00",
};

// ── Preparation ──

export const mockPrep = {
  id: "prep_trial_001",
  name: "Trial Preparation",
  prep_type: "trial",
  created_at: "2026-01-15T10:00:00",
  last_updated: "2026-03-01T14:30:00",
};

// ── Witnesses ──

export const mockWitnesses = [
  {
    name: "Officer James Rodriguez",
    type: "State",
    goal: "Testify about arrest and evidence collection",
    summary: "Arresting officer, 12 years experience",
  },
  {
    name: "Dr. Emily Chen",
    type: "State",
    goal: "Testify about victim injuries",
    summary: "ER physician who treated the victim",
  },
  {
    name: "Michael Torres",
    type: "Defense",
    goal: "Alibi witness — was with defendant",
    summary: "Defendant's coworker",
  },
  {
    name: "Lisa Park",
    type: "Swing",
    goal: "Eyewitness to the altercation",
    summary: "Bystander, partial view, inconsistent prior statements",
  },
];

// ── Evidence ──

export const mockEvidence = [
  {
    id: "ev-001",
    item: "Body camera footage",
    type: "Video",
    source: "Officer Rodriguez",
    relevance: "Shows defendant's behavior at arrest",
  },
  {
    id: "ev-002",
    item: "Medical records",
    type: "Document",
    source: "Memorial Hospital",
    relevance: "Documents victim injuries",
  },
];

// ── Charges ──

export const mockCharges = [
  { name: "Aggravated Assault", statute_number: "39-13-102", level: "Felony C" },
  { name: "Simple Assault", statute_number: "39-13-101", level: "Misdemeanor A" },
];

// ── War Game ──

export const mockWarGameSession = {
  id: "wg-session-001",
  case_id: "case__criminal_001",
  prep_id: "prep_trial_001",
  difficulty: "aggressive" as const,
  status: "active" as const,
  created_at: "2026-03-10T09:00:00",
  updated_at: "2026-03-10T09:30:00",
  current_round: 0,
  rounds: [
    {
      type: "theory" as const,
      status: "completed" as const,
      attack: "Your mistaken identity defense has critical flaws...",
      response: "The defense maintains the cell phone data is dispositive...",
      evaluation: {
        score: 72,
        strengths: ["Cell phone data creates strong alibi timeline"],
        vulnerabilities: ["Body cam footage places defendant at scene"],
      },
    },
    { type: "evidence" as const, status: "pending" as const, attack: null, response: null, evaluation: null },
    { type: "witnesses" as const, status: "pending" as const, attack: null, response: null, evaluation: null },
    { type: "elements" as const, status: "pending" as const, attack: null, response: null, evaluation: null },
    { type: "jury" as const, status: "pending" as const, attack: null, response: null, evaluation: null },
  ],
  report: null,
};

// ── Contradiction Matrix ──

export const mockContradiction = {
  id: "contra-001",
  doc_a: "police_report.pdf",
  doc_b: "witness_statement_park.pdf",
  type: "timeline_discrepancy",
  severity: "high" as const,
  description: "Officer's report states 11:30 PM. Park's statement says 11:15 PM.",
  implications: "15-minute discrepancy supports defense alibi theory",
};

// ── Predictive Score ──

export const mockPredictiveScore = {
  overall_score: 68,
  verdict_prediction: "Moderately favorable",
  dimensions: [
    { name: "evidence_strength", score: 75, weight: 0.25, details: "Strong physical evidence" },
    { name: "witness_reliability", score: 60, weight: 0.20, details: "One inconsistent witness" },
    { name: "element_coverage", score: 70, weight: 0.20, details: "Most elements covered" },
    { name: "legal_authority", score: 65, weight: 0.10, details: "Some supporting precedent" },
    { name: "narrative_coherence", score: 72, weight: 0.15, details: "Coherent defense theory" },
    { name: "adversarial_resilience", score: 55, weight: 0.10, details: "Vulnerable to cross" },
  ],
  strengths: ["Cell phone alibi data", "Medical records support theory"],
  vulnerabilities: ["Eyewitness inconsistency", "Body cam footage"],
};

// ── Billing ──

export const mockInvoice = {
  id: "inv-001",
  case_id: "case__criminal_001",
  amount: 2500.0,
  status: "pending",
  description: "Trial preparation — 10 hours @ $250/hr",
  created_at: "2026-03-01T10:00:00",
  due_date: "2026-03-31",
};

// ── Client ──

export const mockClient = {
  id: "client-001",
  name: "Marcus Thompson",
  email: "mthompson@email.com",
  phone: "615-555-0123",
  status: "active",
  case_ids: ["case__criminal_001"],
  created_at: "2026-01-10T09:00:00",
};

// ── API Response Wrappers ──

export function wrapApiResponse<T>(data: T, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
    text: async () => JSON.stringify(data),
  };
}

export function wrapApiError(message: string, status = 400) {
  return {
    ok: false,
    status,
    json: async () => ({ detail: message }),
    text: async () => JSON.stringify({ detail: message }),
  };
}
