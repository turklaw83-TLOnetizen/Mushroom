"""Shared test fixtures and mock data factories for Project Mushroom Cloud.

Provides realistic sample data for cases, witnesses, evidence, charges,
war game sessions, and analysis state. Import these directly in tests
or use the pytest fixtures registered in conftest.py.
"""

from datetime import datetime

# ── Case Metadata ──

SAMPLE_CRIMINAL_CASE = {
    "id": "case__criminal_001",
    "name": "State v. Marcus Thompson",
    "description": "Aggravated assault case with multiple witnesses",
    "status": "active",
    "phase": "active",
    "case_type": "criminal",
    "case_category": "violent",
    "case_subcategory": "assault",
    "client_name": "Marcus Thompson",
    "assigned_to": ["DJT"],
    "created_at": "2026-01-10T09:00:00",
    "last_updated": "2026-03-01T14:30:00",
}

SAMPLE_CIVIL_CASE = {
    "id": "case__civil_001",
    "name": "Johnson v. Metro Corp",
    "description": "Personal injury from workplace accident",
    "status": "active",
    "phase": "active",
    "case_type": "civil-plaintiff",
    "case_category": "personal_injury",
    "case_subcategory": "workplace",
    "client_name": "Robert Johnson",
    "assigned_to": ["DJT", "CRJ"],
    "created_at": "2026-02-01T10:00:00",
    "last_updated": "2026-03-05T11:00:00",
}

# ── Preparation ──

SAMPLE_PREP = {
    "id": "prep_trial_001",
    "name": "Trial Preparation",
    "prep_type": "trial",
    "created_at": "2026-01-15T10:00:00",
    "last_updated": "2026-03-01T14:30:00",
}

SAMPLE_MOTION_PREP = {
    "id": "prep_motion_001",
    "name": "Motion to Suppress",
    "prep_type": "motion",
    "created_at": "2026-02-01T10:00:00",
    "last_updated": "2026-02-20T16:00:00",
}

# ── Witnesses ──

SAMPLE_WITNESSES = [
    {
        "name": "Officer James Rodriguez",
        "type": "State",
        "goal": "Testify about arrest and evidence collection",
        "summary": "Arresting officer, 12 years experience",
    },
    {
        "name": "Dr. Emily Chen",
        "type": "State",
        "goal": "Testify about victim injuries",
        "summary": "ER physician who treated the victim",
    },
    {
        "name": "Michael Torres",
        "type": "Defense",
        "goal": "Alibi witness — was with defendant",
        "summary": "Defendant's coworker, present at time of incident",
    },
    {
        "name": "Lisa Park",
        "type": "Swing",
        "goal": "Eyewitness to the altercation",
        "summary": "Bystander, partial view, inconsistent prior statements",
    },
]

# ── Charges ──

SAMPLE_CHARGES = [
    {"name": "Aggravated Assault", "statute_number": "39-13-102", "level": "Felony C"},
    {"name": "Simple Assault", "statute_number": "39-13-101", "level": "Misdemeanor A"},
]

# ── Evidence ──

SAMPLE_EVIDENCE = [
    {
        "id": "ev-001",
        "item": "Body camera footage",
        "type": "Video",
        "source": "Officer Rodriguez",
        "foundation": "Chain of custody through department records",
        "relevance": "Shows defendant's behavior at arrest",
    },
    {
        "id": "ev-002",
        "item": "Medical records",
        "type": "Document",
        "source": "Memorial Hospital",
        "foundation": "Business records exception",
        "relevance": "Documents victim injuries consistent with assault",
    },
    {
        "id": "ev-003",
        "item": "Cell phone location data",
        "type": "Digital",
        "source": "Defense subpoena to carrier",
        "foundation": "Warrant-backed carrier records",
        "relevance": "May support alibi timeline",
    },
]

# ── Timeline ──

SAMPLE_TIMELINE = [
    {"year": "2025", "month": "11", "day": "15", "headline": "Incident occurs",
     "text": "Altercation at 2200 block of Main Street around 11:30 PM"},
    {"year": "2025", "month": "11", "day": "15", "headline": "Police respond",
     "text": "Officers arrive at scene 11:47 PM, defendant detained"},
    {"year": "2025", "month": "11", "day": "16", "headline": "Victim treated",
     "text": "Victim presents at Memorial Hospital ER with facial injuries"},
    {"year": "2025", "month": "12", "day": "03", "headline": "Arrest",
     "text": "Defendant formally charged after investigation"},
]

# ── Full Analysis State ──

SAMPLE_ANALYSIS_STATE = {
    "case_summary": "Marcus Thompson is charged with aggravated assault after an altercation on Main Street. The prosecution's case relies on Officer Rodriguez's body camera footage and Dr. Chen's medical testimony. The defense theory centers on mistaken identity supported by alibi witness Michael Torres and cell phone location data.",
    "charges": SAMPLE_CHARGES,
    "witnesses": SAMPLE_WITNESSES,
    "timeline": SAMPLE_TIMELINE,
    "evidence_foundations": SAMPLE_EVIDENCE,
    "consistency_check": [
        {"issue": "Timeline discrepancy between witness Park's initial statement (11:15 PM) and police report (11:30 PM)", "severity": "medium"},
    ],
    "legal_elements": [
        {"charge": "Aggravated Assault", "element": "Intentional/knowing conduct", "evidence": "Body cam footage", "strength": "moderate"},
        {"charge": "Aggravated Assault", "element": "Serious bodily injury", "evidence": "Medical records", "strength": "strong"},
    ],
    "investigation_plan": [
        {"action": "Obtain security footage from nearby businesses", "reason": "Corroborate alibi timeline", "priority": "High"},
        {"action": "Interview additional bystanders", "reason": "Challenge prosecution witnesses", "priority": "Medium"},
    ],
    "strategy_notes": "Focus on mistaken identity defense. Cell phone data places defendant 2 miles from scene at 11:15 PM. Attack eyewitness reliability due to poor lighting and distance.",
    "devils_advocate_notes": "Prosecution will argue cell data shows defendant arrived at scene by 11:25 PM. Body cam shows defendant at scene — identity is not in question. Focus should shift to self-defense or provocation.",
    "cross_examination_plan": [],
    "direct_examination_plan": [],
    "entities": [
        {"id": "e1", "name": "Officer James Rodriguez", "type": "PERSON", "context": "Arresting officer"},
        {"id": "e2", "name": "Marcus Thompson", "type": "PERSON", "context": "Defendant"},
        {"id": "e3", "name": "Memorial Hospital", "type": "ORG", "context": "Victim treatment location"},
    ],
    "voir_dire": {},
    "mock_jury_feedback": [],
    "legal_research_data": [],
    "drafted_documents": [],
    "current_model": "anthropic",
    "case_type": "criminal",
    "raw_documents": [
        {"filename": "police_report.pdf", "text": "Officer Rodriguez responded to a call...", "size": 45000},
        {"filename": "medical_records.pdf", "text": "Patient presented with contusions...", "size": 32000},
        {"filename": "witness_statement_park.pdf", "text": "I was walking my dog when I heard shouting...", "size": 8000},
    ],
}

# ── War Game ──

SAMPLE_WAR_GAME_SESSION = {
    "id": "wg-session-001",
    "case_id": "case__criminal_001",
    "prep_id": "prep_trial_001",
    "difficulty": "aggressive",
    "status": "active",
    "created_at": "2026-03-10T09:00:00",
    "updated_at": "2026-03-10T09:30:00",
    "current_round": 0,
    "rounds": [
        {"type": "theory", "status": "completed", "attack": "Your mistaken identity defense crumbles...", "response": "The defense stands on cell phone data...", "evaluation": {"score": 72, "strengths": ["Cell data is strong"], "vulnerabilities": ["Body cam undermines identity defense"]}},
        {"type": "evidence", "status": "pending", "attack": None, "response": None, "evaluation": None},
        {"type": "witnesses", "status": "pending", "attack": None, "response": None, "evaluation": None},
        {"type": "elements", "status": "pending", "attack": None, "response": None, "evaluation": None},
        {"type": "jury", "status": "pending", "attack": None, "response": None, "evaluation": None},
    ],
    "report": None,
}

# ── Contradiction Matrix ──

SAMPLE_CONTRADICTION = {
    "id": "contra-001",
    "doc_a": "police_report.pdf",
    "doc_b": "witness_statement_park.pdf",
    "type": "timeline_discrepancy",
    "severity": "high",
    "description": "Officer's report states incident at 11:30 PM. Park's statement says she heard shouting at 11:15 PM.",
    "doc_a_excerpt": "Incident occurred at approximately 2330 hours",
    "doc_b_excerpt": "I heard loud shouting around 11:15",
    "implications": "15-minute discrepancy may support defense alibi theory",
}

# ── Billing ──

SAMPLE_INVOICE = {
    "id": "inv-001",
    "case_id": "case__criminal_001",
    "amount": 2500.00,
    "status": "pending",
    "description": "Trial preparation — 10 hours @ $250/hr",
    "created_at": "2026-03-01T10:00:00",
    "due_date": "2026-03-31",
}

# ── CRM / Client ──

SAMPLE_CLIENT = {
    "id": "client-001",
    "name": "Marcus Thompson",
    "email": "mthompson@email.com",
    "phone": "615-555-0123",
    "status": "active",
    "case_ids": ["case__criminal_001"],
    "created_at": "2026-01-10T09:00:00",
}

# ── Redaction ──

SAMPLE_PII_TEXT = """
The defendant, Marcus Thompson (SSN: 123-45-6789), was arrested on November 15, 2025.
His phone number is (615) 555-0123 and email is mthompson@email.com.
His date of birth is March 15, 1990.
Credit card ending in 4532 was found in his possession.
"""

SAMPLE_REDACTION_FINDINGS = [
    {"category": "ssn", "text": "123-45-6789", "start": 44, "end": 55, "confidence": 0.99},
    {"category": "phone", "text": "(615) 555-0123", "start": 100, "end": 114, "confidence": 0.95},
    {"category": "email", "text": "mthompson@email.com", "start": 125, "end": 144, "confidence": 0.98},
]
