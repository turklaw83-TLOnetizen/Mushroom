# Project Mushroom Cloud — Next.js + FastAPI Migration Guide

> **For: Antigravity (or any AI coding assistant)**
> **From: Claude Opus (Feb 2026)**
> **Project:** Migrating a Streamlit legal SaaS to Next.js + FastAPI
> **Repo:** `C:\Users\turkl\project-mushroom-cloud`

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Current Architecture](#2-current-architecture)
3. [Target Architecture](#3-target-architecture)
4. [The Golden Rule: Don't Touch core/](#4-the-golden-rule-dont-touch-core)
5. [FastAPI Backend — Route Design](#5-fastapi-backend--route-design)
6. [Next.js Frontend — Component Mapping](#6-nextjs-frontend--component-mapping)
7. [State Management Migration](#7-state-management-migration)
8. [Real-Time Features (WebSockets)](#8-real-time-features-websockets)
9. [File Handling Migration](#9-file-handling-migration)
10. [Authentication & RBAC](#10-authentication--rbac)
11. [Background Workers & Progress](#11-background-workers--progress)
12. [Known Issues & Technical Debt](#12-known-issues--technical-debt)
13. [Migration Phases](#13-migration-phases)
14. [Testing Strategy](#14-testing-strategy)
15. [Deployment](#15-deployment)
16. [File-by-File Migration Map](#16-file-by-file-migration-map)
17. [Session State Key Registry](#17-session-state-key-registry)
18. [Critical Warnings](#18-critical-warnings)

---

## 1. EXECUTIVE SUMMARY

### What We're Migrating

A **legal case management and AI analysis platform** currently built on Streamlit (~43K LOC across ~102 Python files). The platform manages legal cases through their full lifecycle: document ingestion, OCR, AI-powered analysis (14 LangGraph nodes), document drafting, billing, CRM, calendar, e-signatures, and export.

### Why We're Migrating

Streamlit's architecture has fundamental limitations for a production SaaS:

| Streamlit Pain | Next.js + FastAPI Solution |
|---|---|
| Reruns entire script on every click (275 `st.rerun()` calls) | React components only re-render what changes |
| Custom components need iframe/postMessage hacks | Native drag-and-drop, file APIs, any JS library |
| Session state is fragile & global (713 references, no schema) | Proper state management (React context, Zustand, TanStack Query) |
| No real-time communication (polls JSON files every 2-5 sec) | WebSockets / Server-Sent Events built-in |
| tkinter hacks for folder picker | Native browser File System Access API |
| Layout is rigid (columns/tabs only) | Full CSS, Tailwind, any UI library |
| Encryption key stored in client-side session_state | Server-side JWT sessions, httpOnly cookies |
| No proper routing (query params hack) | Next.js App Router with nested layouts |

### What Stays, What Goes

| Layer | Action | Estimated Effort |
|---|---|---|
| `core/` (case_manager, storage, nodes, export, etc.) | **KEEP 100% AS-IS** | 0 hours |
| `tests/` (222 tests) | **KEEP** — add FastAPI route tests | +20 hours |
| `ui/` (Streamlit layer) | **DELETE ENTIRELY** — rewrite in Next.js | 200-300 hours |
| New: `api/` (FastAPI routes) | **CREATE** — thin wrapper around core/ | 60-80 hours |
| New: `frontend/` (Next.js app) | **CREATE** — full React UI | 150-200 hours |

### Tech Stack

```
Frontend:  Next.js 14+ (App Router) + TypeScript + Tailwind CSS + shadcn/ui
Backend:   FastAPI + Python 3.11+ (wraps existing core/)
State:     Zustand (client) + TanStack Query (server state)
Real-time: WebSockets (FastAPI → Next.js)
Auth:      NextAuth.js (frontend) + FastAPI JWT middleware (backend)
Deploy:    Vercel Pro ($20/mo frontend) + existing server (FastAPI)
```

---

## 2. CURRENT ARCHITECTURE

### Directory Structure
```
project-mushroom-cloud/
  app.py                    # Streamlit entry point (117 lines)
  launcher.py               # Desktop launcher with port management
  config.yaml               # LLM providers, models, storage paths
  .env                      # API keys (XAI_API_KEY, ANTHROPIC_API_KEY)
  .streamlit/               # Streamlit config (theme, server, secrets)

  core/                     # === BUSINESS LOGIC (KEEP ALL OF THIS) ===
    case_manager.py         # 1450 LOC — all case CRUD, phases, files, preps
    cloud_backup.py         # Dropbox + B2 backup coordinator
    user_profiles.py        # RBAC (admin/attorney/paralegal), PIN/OAuth
    crm.py                  # Client management
    billing.py              # Time entries, expenses, invoicing, retainers
    calendar_events.py      # Events, deadlines, iCal export
    esign.py                # E-signature integration
    ethical_compliance.py   # 2290 LOC — conflicts, trust, SOL, supervision
    bg_analysis.py          # Background analysis daemon thread
    ingestion_worker.py     # Background document ingestion daemon
    ocr_worker.py           # Background OCR daemon
    transcription_worker.py # Background audio transcription daemon
    ingest.py               # OCRCache + DocumentIngester
    llm.py                  # LLM provider abstraction
    state.py                # AgentState TypedDict for LangGraph
    cost_tracker.py         # Token usage tracking
    draft_quality.py        # Brief quality scoring
    court_docs.py           # Court formatting rules
    append_only.py          # Safe merge for append-only keys
    storage/
      base.py               # StorageBackend ABC
      json_backend.py       # File-system JSON persistence
      encrypted_backend.py  # Fernet encryption layer
    nodes/
      graph_builder.py      # LangGraph builder (trial/prelim/motion)
      major_docs.py         # Document drafting (8 functions)
      [14 analysis nodes]   # analyzer, strategist, cross_examiner, etc.
    export/
      pdf_export.py         # PDF report + trial binder
      word_export.py        # Word report + brief outline
      quick_cards.py        # Courtroom reference cards

  ui/                       # === STREAMLIT UI (REPLACE ALL OF THIS) ===
    router.py               # Dispatches dashboard vs case view
    case_dashboard.py       # Landing page — metrics, case table, CRM
    case_view.py            # 3121 LOC — THE MONSTER: case war room
    navigation.py           # Sidebar — settings, exports, case mgmt
    login.py                # PIN/OAuth login page
    shared.py               # Singletons, session state, helpers
    splash.py               # Animated splash screen
    theme.py                # 1005 LOC — CSS theme generation
    components/
      folder_drop.py        # Custom folder picker component
      folder_drop_frontend/ # JS/HTML for folder drop zone
    pages/
      core_analysis_ui.py   # 1229 LOC — analysis results + streaming
      major_docs_ui.py      # 1469 LOC — document drafter UI
      evidence_ui.py        # Evidence tagging, foundations
      witnesses_ui.py       # Witness management, cross/direct exam
      strategy_ui.py        # Strategy, voir dire, mock jury
      research_ui.py        # Legal research, Lexis+ import
      tools_ui.py           # OCR tools, voice brief
      billing_ui.py         # Time, expenses, invoices
      calendar_ui.py        # Calendar events
      master_calendar_ui.py # Month view calendar
      ethical_compliance_ui.py # 1060 LOC — full compliance suite
      esign_ui.py           # E-signature UI
      activity_ui.py        # Activity log viewer
      doc_viewer_ui.py      # Document viewer (PDF, text)
      doc_compare_ui.py     # Side-by-side document comparison

  data/                     # Case data (JSON files, uploaded docs, OCR cache)
  tests/                    # 222 pytest tests
  deploy/                   # Systemd, Cloudflare, Tailscale, backup scripts
```

### Two-Tier UI Pattern
- **Tier 1 (Dashboard):** No case selected. Shows metrics, case list, CRM directory.
- **Tier 2 (War Room):** Case selected. Shows header, files, analysis, all module tabs.
- **Router** dispatches between them based on `current_case_id` in session state.

### How Streamlit Runs (Critical to Understand)
Streamlit re-executes the ENTIRE Python script top-to-bottom on every user interaction. This means:
- Every button click runs `app.py` from line 1
- State survives only through `st.session_state` (a dict persisted across reruns)
- Background threads communicate via JSON files on disk (not session_state — session_state resets on rerun)
- The 275 `st.rerun()` calls explicitly trigger this full re-execution
- `st.stop()` halts execution mid-script (used for auth gates)

This is the fundamental architectural problem we're solving.

---

## 3. TARGET ARCHITECTURE

### Directory Structure (Post-Migration)
```
project-mushroom-cloud/
  core/                     # UNCHANGED — all business logic
  tests/                    # UNCHANGED + new API tests
  data/                     # UNCHANGED — case data
  deploy/                   # UPDATED — new deployment configs

  api/                      # NEW — FastAPI backend
    main.py                 # FastAPI app, CORS, middleware
    deps.py                 # Dependency injection (CaseManager, UserManager, etc.)
    auth.py                 # JWT auth middleware
    routers/
      cases.py              # /api/cases/* — CRUD, phases, files
      preparations.py       # /api/cases/{id}/preps/* — prep management
      analysis.py           # /api/analysis/* — start/stop/status + WebSocket
      documents.py          # /api/documents/* — upload, download, OCR status
      crm.py                # /api/crm/* — client management
      billing.py            # /api/billing/* — time, expenses, invoices
      calendar.py           # /api/calendar/* — events, deadlines
      compliance.py         # /api/compliance/* — ethical compliance
      esign.py              # /api/esign/* — e-signature
      export.py             # /api/export/* — PDF, Word, trial binder
      users.py              # /api/users/* — auth, RBAC
      backup.py             # /api/backup/* — backup status/trigger
    websockets/
      analysis_ws.py        # Real-time analysis progress streaming
      ingestion_ws.py       # Real-time ingestion/OCR status

  frontend/                 # NEW — Next.js app
    app/
      layout.tsx            # Root layout (sidebar, auth provider)
      page.tsx              # Dashboard (Tier 1)
      login/page.tsx        # Login page
      cases/
        [id]/
          layout.tsx        # Case layout (war room shell)
          page.tsx          # Case overview/header
          files/page.tsx    # File library
          analysis/page.tsx # Analysis results + progress
          documents/page.tsx # Document drafter
          witnesses/page.tsx
          evidence/page.tsx
          strategy/page.tsx
          research/page.tsx
          billing/page.tsx
          calendar/page.tsx
          compliance/page.tsx
          esign/page.tsx
          activity/page.tsx
    components/
      ui/                   # shadcn/ui components
      dashboard/            # Dashboard-specific components
      case/                 # Case view components
      shared/               # Shared components (file uploader, etc.)
    lib/
      api.ts                # API client (fetch wrapper)
      auth.ts               # Auth utilities
      websocket.ts          # WebSocket client
      stores/               # Zustand stores
    hooks/
      useCase.ts            # TanStack Query hooks for cases
      useAnalysis.ts        # Analysis state + WebSocket
      useFiles.ts           # File operations
```

### Data Flow
```
Browser (Next.js)
  ↓ HTTP/WS
FastAPI (api/)
  ↓ Python calls
core/ (CaseManager, etc.)
  ↓ File I/O
data/ (JSON files, documents)
```

---

## 4. THE GOLDEN RULE: DON'T TOUCH core/

The entire `core/` directory is **production-tested business logic** with 222 passing tests. It handles:

- Case CRUD with thread-safe locking
- 14-node LangGraph analysis pipeline
- OCR with page-level caching and quality assessment
- Document ingestion with vision model fallback
- Background daemon threads with heartbeat and stale detection
- Append-only safe merge for concurrent updates
- Path traversal protection
- Encryption at rest (Fernet)

**The FastAPI layer is a THIN WRAPPER.** Every API route should be ~5-15 lines:

```python
# Example: api/routers/cases.py
@router.get("/")
async def list_cases(
    include_archived: bool = False,
    cm: CaseManager = Depends(get_case_manager),
    user: dict = Depends(get_current_user),
):
    cases = cm.list_cases(include_archived=include_archived)
    # Filter by user's assigned cases (RBAC)
    if not user_manager.is_admin(user["user_id"]):
        allowed = user_manager.get_cases_for_user(user["user_id"]) or []
        cases = [c for c in cases if c["case_id"] in allowed]
    return cases
```

**Never rewrite core logic in FastAPI.** Just call the existing methods.

---

## 5. FASTAPI BACKEND — ROUTE DESIGN

### Dependency Injection Setup

```python
# api/deps.py
from core.case_manager import CaseManager
from core.user_profiles import UserManager
from core.cloud_backup import BackupManager

_case_manager: CaseManager | None = None
_user_manager: UserManager | None = None

def get_case_manager() -> CaseManager:
    global _case_manager
    if _case_manager is None:
        from core.storage.json_backend import JSONStorageBackend
        storage = JSONStorageBackend("data")
        _case_manager = CaseManager(storage)
    return _case_manager

def get_user_manager() -> UserManager:
    global _user_manager
    if _user_manager is None:
        _user_manager = UserManager()
    return _user_manager
```

### Complete Route Map

Every route wraps an existing `core/` method. Here's the full map:

#### Cases Router (`/api/cases`)
| Method | Path | Core Method | Notes |
|--------|------|-------------|-------|
| GET | `/` | `cm.list_cases()` | + RBAC filtering |
| POST | `/` | `cm.create_case()` | Returns new case_id |
| GET | `/{id}` | `cm.get_case_metadata()` | |
| DELETE | `/{id}` | `cm.delete_case()` | Admin only |
| PUT | `/{id}/rename` | `cm.rename_case()` | |
| POST | `/{id}/clone` | `cm.clone_case()` | |
| PUT | `/{id}/phase` | `cm.set_phase()` | Phase + sub_phase |
| GET | `/{id}/phase` | `cm.get_phase()` | |
| POST | `/{id}/archive` | `cm.archive_case()` | |
| POST | `/{id}/unarchive` | `cm.unarchive_case()` | |
| POST | `/{id}/purge` | `cm.purge_source_docs()` | Long-running, use background task |
| GET | `/{id}/activity` | `cm.get_activity_log()` | Paginated |
| GET | `/{id}/directives` | `cm.load_directives()` | |
| POST | `/{id}/directives` | `cm.save_directive()` | |
| GET | `/{id}/contacts` | `cm.load_contact_log()` | |
| POST | `/{id}/contacts` | `cm.add_contact_log_entry()` | |
| GET | `/{id}/journal` | Case journal entries | |
| POST | `/{id}/journal` | `cm.add_journal_entry()` | |

#### Files Router (`/api/cases/{id}/files`)
| Method | Path | Core Method | Notes |
|--------|------|-------------|-------|
| GET | `/` | `cm.get_case_files()` | + OCR status per file |
| POST | `/upload` | `cm.save_file()` | Multipart, multiple files |
| POST | `/upload-folder` | Iterate `cm.save_file()` | Batch upload from folder |
| DELETE | `/{filename}` | `cm.delete_file()` | |
| GET | `/{filename}/download` | Direct file streaming | StreamingResponse |
| GET | `/{filename}/preview` | Text preview (first 10KB) | |
| PUT | `/order` | `cm.save_file_order()` | Drag-and-drop reorder |
| POST | `/{filename}/force-ocr` | `ocr_worker.prioritize_file()` | |

#### Preparations Router (`/api/cases/{id}/preps`)
| Method | Path | Core Method | Notes |
|--------|------|-------------|-------|
| GET | `/` | `cm.list_preparations()` | |
| POST | `/` | `cm.create_preparation()` | |
| DELETE | `/{prep_id}` | `cm.delete_preparation()` | |
| POST | `/{prep_id}/clone` | `cm.clone_preparation()` | |
| GET | `/{prep_id}/state` | `cm.load_prep_state()` | Full analysis state |
| PUT | `/{prep_id}/state/{key}` | `cm.save_prep_state()` | Partial update |
| GET | `/{prep_id}/snapshots` | `cm.list_snapshots()` | |
| POST | `/{prep_id}/snapshots` | `cm.save_snapshot()` | |
| POST | `/{prep_id}/snapshots/{snap_id}/restore` | `cm.restore_snapshot()` | |

#### Analysis Router (`/api/analysis`)
| Method | Path | Core Method | Notes |
|--------|------|-------------|-------|
| POST | `/start` | `bg_analysis.start_background_analysis()` | Spawns daemon thread |
| POST | `/stop` | `bg_analysis.stop_background_analysis()` | |
| GET | `/status/{case_id}/{prep_id}` | `bg_analysis.get_analysis_progress()` | Polling fallback |
| WS | `/ws/{case_id}/{prep_id}` | Stream progress.json changes | **WebSocket** |

#### Ingestion Router (`/api/ingestion`)
| Method | Path | Core Method | Notes |
|--------|------|-------------|-------|
| POST | `/start/{case_id}` | `ingestion_worker.start_background_ingestion()` | |
| GET | `/status/{case_id}` | `ingestion_worker.get_ingestion_status()` | |
| WS | `/ws/{case_id}` | Stream ingestion progress | **WebSocket** |

#### OCR Router (`/api/ocr`)
| Method | Path | Core Method | Notes |
|--------|------|-------------|-------|
| POST | `/start/{case_id}` | `ocr_worker.start_ocr_worker()` | |
| POST | `/stop/{case_id}` | `ocr_worker.stop_ocr_worker()` | |
| GET | `/status/{case_id}` | `ocr_worker.get_ocr_status()` | |
| GET | `/file-status/{case_id}` | `OCRCache.get_status()` per file | Batch status |
| POST | `/prioritize` | `ocr_worker.prioritize_file()` | |
| GET | `/search/{case_id}` | `OCRCache.search()` | Full-text OCR search |

#### CRM Router (`/api/crm`)
| Method | Path | Core Method | Notes |
|--------|------|-------------|-------|
| GET | `/clients` | `crm.load_clients()` | |
| POST | `/clients` | `crm.add_client()` | |
| GET | `/clients/{id}` | `crm.get_client()` | |
| PUT | `/clients/{id}` | `crm.update_client()` | |
| DELETE | `/clients/{id}` | `crm.delete_client()` | |
| GET | `/search` | `crm.search_clients()` | |
| POST | `/clients/{id}/link/{case_id}` | `crm.link_client_to_case()` | |
| GET | `/stats` | `crm.get_crm_stats()` | |
| GET | `/intake/templates` | `crm.get_intake_templates()` | |
| POST | `/intake/{client_id}` | `crm.save_intake_answers()` | |

#### Billing Router (`/api/billing`)
| Method | Path | Core Method | Notes |
|--------|------|-------------|-------|
| GET | `/time/{case_id}` | `billing.load_time_entries()` | |
| POST | `/time/{case_id}` | `billing.add_time_entry()` | |
| GET | `/expenses/{case_id}` | `billing.load_expenses()` | |
| POST | `/expenses/{case_id}` | `billing.add_expense()` | |
| POST | `/invoices` | `billing.create_invoice()` | |
| GET | `/invoices/{id}/pdf` | `billing.generate_invoice_pdf()` | StreamingResponse |
| POST | `/invoices/{id}/email` | `billing.email_invoice()` | |
| GET | `/retainer/{case_id}` | `billing.get_retainer_balance()` | |
| GET | `/summary/{case_id}` | `billing.get_case_billing_summary()` | |
| GET | `/aging` | `billing.get_aging_report()` | Firm-wide |

#### Calendar Router (`/api/calendar`)
| Method | Path | Core Method | Notes |
|--------|------|-------------|-------|
| GET | `/events` | `calendar.load_events()` | Filter by date range |
| POST | `/events` | `calendar.add_event()` | |
| PUT | `/events/{id}` | `calendar.update_event()` | |
| DELETE | `/events/{id}` | `calendar.delete_event()` | |
| GET | `/month/{year}/{month}` | `calendar.get_month_calendar()` | |
| GET | `/upcoming` | `calendar.get_upcoming_events()` | |
| GET | `/ical` | `calendar.export_ical()` | Returns .ics file |
| GET | `/merged/{case_id}` | `calendar.merge_deadlines_and_events()` | |

#### Compliance Router (`/api/compliance`)
| Method | Path | Core Method | Notes |
|--------|------|-------------|-------|
| GET | `/conflicts/{case_id}` | `ethical.scan_conflicts_smart()` | |
| GET | `/dashboard` | `ethical.get_compliance_dashboard()` | |
| GET | `/trust/{case_id}` | `ethical.load_trust_ledger()` | |
| POST | `/trust/{case_id}` | `ethical.add_trust_entry()` | |
| GET | `/trust/summary` | `ethical.get_trust_summary()` | |
| GET | `/sol/{case_id}` | `ethical.load_sol_tracking()` | |
| POST | `/sol/{case_id}` | `ethical.add_sol_claim()` | |
| GET | `/sol/alerts` | `ethical.get_sol_alerts()` | |
| GET | `/fee-agreement/{case_id}` | `ethical.load_fee_agreement()` | |
| POST | `/fee-agreement/{case_id}` | `ethical.save_fee_agreement()` | |
| GET | `/supervision/{case_id}` | `ethical.load_supervision_log()` | |
| GET | `/lit-hold/{case_id}` | `ethical.load_lit_hold()` | |
| POST | `/lit-hold/{case_id}` | `ethical.save_lit_hold()` | |
| GET | `/engagement-letter` | `ethical.generate_letter()` | |
| GET | `/rules/search` | `ethical.search_rules()` | |
| GET | `/sentencing` | `ethical.get_sentencing_range()` | |

#### Export Router (`/api/export`)
| Method | Path | Core Method | Notes |
|--------|------|-------------|-------|
| GET | `/pdf/{case_id}/{prep_id}` | `pdf_export.generate_pdf_report()` | StreamingResponse |
| GET | `/word/{case_id}/{prep_id}` | `word_export.generate_word_report()` | StreamingResponse |
| GET | `/binder/{case_id}/{prep_id}` | `pdf_export.generate_trial_binder_pdf()` | StreamingResponse |
| GET | `/brief/{case_id}/{prep_id}` | `word_export.generate_brief_outline()` | StreamingResponse |
| GET | `/cards/{case_id}/{prep_id}` | `quick_cards.generate_quick_cards_pdf()` | StreamingResponse |
| GET | `/all/{case_id}/{prep_id}` | All 4 formats zipped | StreamingResponse |

#### Users Router (`/api/users`)
| Method | Path | Core Method | Notes |
|--------|------|-------------|-------|
| POST | `/login` | `um.authenticate()` | Returns JWT |
| POST | `/login/google` | `um.find_by_google_email()` | OAuth flow |
| GET | `/me` | Current user from JWT | |
| GET | `/` | `um.list_users()` | Admin only |
| POST | `/` | `um.create_user()` | Admin only |
| PUT | `/{id}` | `um.update_user()` | |
| GET | `/team-stats` | `um.get_team_stats()` | |

#### Major Documents Router (`/api/documents/drafts`)
| Method | Path | Core Method | Notes |
|--------|------|-------------|-------|
| POST | `/outline` | `major_docs.generate_document_outline()` | LLM call |
| POST | `/draft-section` | `major_docs.draft_document_section()` | LLM call |
| POST | `/citations` | `major_docs.build_citation_library()` | LLM call |
| POST | `/review` | `major_docs.review_brief()` | LLM call |
| POST | `/analyze-opposing` | `major_docs.analyze_opposing_brief()` | LLM call |
| POST | `/verify-citations` | `major_docs.verify_citations_cross_model()` | LLM call |
| GET | `/{case_id}` | `cm.load_major_drafts()` | |
| POST | `/{case_id}` | `cm.save_major_draft()` | |
| DELETE | `/{case_id}/{draft_id}` | `cm.delete_major_draft()` | |

#### Phase Config Router (`/api/config`)
| Method | Path | Core Method | Notes |
|--------|------|-------------|-------|
| GET | `/phases` | `cm.get_phase_config()` | |
| PUT | `/phases` | `cm.save_phase_config()` | Admin only |
| GET | `/sub-phases/{case_type}` | `cm.get_sub_phases_for_case()` | |

---

## 6. NEXT.JS FRONTEND — COMPONENT MAPPING

### Page-Level Mapping (Streamlit -> Next.js)

| Streamlit File | Next.js Route | Component Strategy |
|---|---|---|
| `app.py` (entry + gates) | `app/layout.tsx` + `middleware.ts` | Auth middleware, theme provider |
| `ui/login.py` | `app/login/page.tsx` | NextAuth.js login form |
| `ui/case_dashboard.py` | `app/page.tsx` | Dashboard with TanStack Table |
| `ui/case_view.py` (3121 LOC!) | `app/cases/[id]/layout.tsx` + sub-routes | **SPLIT INTO 15+ COMPONENTS** |
| `ui/navigation.py` | `components/sidebar.tsx` | Persistent sidebar layout |
| `ui/router.py` | Next.js App Router | Automatic via file structure |
| `ui/theme.py` | `tailwind.config.ts` + CSS variables | Tailwind handles all theming |
| `ui/splash.py` | Loading states / Suspense boundaries | React Suspense |
| `ui/shared.py` | `lib/` utilities + hooks | React hooks replace singletons |

### Breaking Up the 3121-Line Monster (case_view.py)

`case_view.py` does EVERYTHING for the case war room. It must be decomposed:

```
app/cases/[id]/
  layout.tsx          # Case header, phase badge, metrics cards
  page.tsx            # Overview (charges, directives, contacts)
  files/
    page.tsx          # File library (upload, OCR badges, drag-reorder)
    [filename]/page.tsx  # Individual file viewer
  analysis/
    page.tsx          # Analysis status, progress grid, results tabs
    compare/page.tsx  # Snapshot comparison
  documents/page.tsx  # Major document drafter
  witnesses/page.tsx  # Witness management, cross/direct exam
  evidence/page.tsx   # Evidence tagging, foundations
  strategy/page.tsx   # Strategy, voir dire, mock jury
  research/page.tsx   # Legal research, Lexis+ import
  billing/page.tsx    # Time, expenses, invoices, retainers
  calendar/page.tsx   # Case deadlines + global calendar
  compliance/page.tsx # Trust, conflicts, SOL, supervision
  esign/page.tsx      # E-signature management
  activity/page.tsx   # Activity log
```

### Recommended UI Libraries

| Need | Library | Why |
|---|---|---|
| Component primitives | **shadcn/ui** | Copy-paste components, full control, Tailwind native |
| Data tables | **TanStack Table** | Sorting, filtering, pagination (replaces st.dataframe) |
| Forms | **React Hook Form + Zod** | Validation, nested forms (replaces st.text_input chains) |
| File upload | **react-dropzone** | Native drag-and-drop (replaces tkinter hack + iframe component) |
| Rich text | **Tiptap** or **Plate** | Markdown rendering for analysis results |
| Calendar | **react-big-calendar** | Month/week/day views (replaces master_calendar_ui.py) |
| Charts | **Recharts** | Performance profile bar chart, metrics |
| Toast notifications | **sonner** | Replaces st.toast() |
| Modals/Dialogs | **shadcn/ui Dialog** | Replaces st.form + confirmation patterns |
| PDF viewer | **react-pdf** | Replaces PyMuPDF in doc_viewer_ui.py |

---

## 7. STATE MANAGEMENT MIGRATION

### Current: Streamlit Session State (Fragile, Global, Untyped)

The current app uses 713 `st.session_state` references with no schema. Key categories:

**Authentication State:**
- `current_user` — logged-in user dict
- `_encryption_key` — derived encryption key (SECURITY RISK: client-side!)
- `login_method` — "pin" or "google"

**Navigation State:**
- `current_case_id` — active case ID
- `current_prep_id` — active preparation ID
- `_active_tab` — current tab in war room

**Cache Invalidation:**
- `_dash_cache_ver` — bumped on any case/file mutation (27 references!)
- `_file_cache_ver` — bumped on file upload/delete
- `_uploader_key_counter` — forces Streamlit file_uploader widget refresh
- `_cached_files_{case_id}` — per-case file list cache

**UI State:**
- `_editing_X_id` — toggles for inline edit forms (20+ keys)
- `_confirm_purge` — purge confirmation dialog
- `_dash_new_case_open` — new case form visibility
- `theme` — "light" or "dark"
- `model_provider` — "anthropic" or "xai"
- `_max_context_mode` — extended context toggle

**Analysis State:**
- `agent_results` — full analysis state dict
- `chat_history` — LLM chat messages
- `session_costs` — token usage tracking
- `_compare_snapshot_id` / `_compare_snapshot_label` — diff comparison

### Target: Zustand + TanStack Query (Typed, Scoped, Reactive)

```typescript
// lib/stores/authStore.ts — Zustand
interface AuthState {
  user: User | null;
  login: (userId: string, pin: string) => Promise<void>;
  logout: () => void;
}

// lib/stores/caseStore.ts — Zustand (UI-only state)
interface CaseState {
  activeCaseId: string | null;
  activePrepId: string | null;
  theme: "light" | "dark";
  modelProvider: "anthropic" | "xai";
  setActiveCase: (id: string) => void;
}

// hooks/useCases.ts — TanStack Query (server state)
export function useCases(includeArchived = false) {
  return useQuery({
    queryKey: ["cases", { includeArchived }],
    queryFn: () => api.get("/cases", { params: { include_archived: includeArchived } }),
  });
}

export function useCaseFiles(caseId: string) {
  return useQuery({
    queryKey: ["cases", caseId, "files"],
    queryFn: () => api.get(`/cases/${caseId}/files`),
  });
}

// Mutations auto-invalidate related queries:
export function useUploadFile(caseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.uploadFile(caseId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cases", caseId, "files"] });
    },
  });
}
```

**Key Insight:** The 27 references to `_dash_cache_ver` all become automatic with TanStack Query's `invalidateQueries()`. No manual cache versioning needed.

---

## 8. REAL-TIME FEATURES (WebSockets)

### Current: Disk-Based Polling (2-5 Second Intervals)

Background workers write JSON status files to disk. The Streamlit UI polls these files every 2-5 seconds using `streamlit-autorefresh`:

- `progress.json` — analysis progress (node statuses, ETA, streaming tokens)
- `ingestion_status.json` — ingestion progress
- `ocr_status/` — per-case OCR status
- `transcription_status.json` — transcription progress

9 auto-refresh instances in `case_view.py` alone, at intervals of 2000-5000ms.

### Target: WebSocket Streaming

```python
# api/websockets/analysis_ws.py
from fastapi import WebSocket
import asyncio, json
from core.bg_analysis import get_analysis_progress

@router.websocket("/ws/analysis/{case_id}/{prep_id}")
async def analysis_progress(ws: WebSocket, case_id: str, prep_id: str):
    await ws.accept()
    last_data = None
    try:
        while True:
            progress = get_analysis_progress(case_id, prep_id)
            if progress != last_data:
                await ws.send_json(progress)
                last_data = progress
                if progress.get("status") in ("complete", "error"):
                    break
            await asyncio.sleep(0.5)  # 500ms server-side, no client polling
    except Exception:
        pass
    finally:
        await ws.close()
```

```typescript
// frontend/hooks/useAnalysisProgress.ts
export function useAnalysisProgress(caseId: string, prepId: string) {
  const [progress, setProgress] = useState<AnalysisProgress | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/analysis/${caseId}/${prepId}`);
    ws.onmessage = (event) => setProgress(JSON.parse(event.data));
    ws.onclose = () => { /* handle reconnect */ };
    return () => ws.close();
  }, [caseId, prepId]);

  return progress;
}
```

### What Gets WebSockets vs REST

| Feature | Method | Why |
|---|---|---|
| Analysis progress | **WebSocket** | Streams tokens + node progress every 500ms |
| Ingestion progress | **WebSocket** | File-by-file progress updates |
| OCR status | **WebSocket** | Per-file page-level progress |
| Case CRUD | REST | Standard request/response |
| File upload | REST (multipart) | One-shot operation |
| Export download | REST (streaming) | One-shot file download |
| Everything else | REST | Standard CRUD |

---

## 9. FILE HANDLING MIGRATION

### Current Pain Points

1. **File Upload:** `st.file_uploader()` — works but loses files on rerun, requires `_uploader_key_counter` hack
2. **Folder Import:** tkinter `filedialog.askdirectory()` — native OS dialog, platform-dependent hack
3. **Custom Drop Zone:** `ui/components/folder_drop.py` — iframe-based component, unreliable
4. **File Download:** `st.download_button()` — 49 instances, each generates the full file on render
5. **RerunException Bug:** `st.rerun()` inside `try/except Exception` was silently caught (FIXED but fragile)

### Target

```typescript
// components/FileUploader.tsx
import { useDropzone } from "react-dropzone";

export function FileUploader({ caseId }: { caseId: string }) {
  const uploadFile = useUploadFile(caseId);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (files) => {
      files.forEach((file) => uploadFile.mutate(file));
    },
    multiple: true,
  });

  return (
    <div {...getRootProps()} className="border-2 border-dashed p-8 rounded-lg">
      <input {...getInputProps()} />
      {isDragActive ? "Drop files here..." : "Drag & drop files, or click to browse"}
    </div>
  );
}

// Folder upload using File System Access API (Chrome/Edge)
async function handleFolderUpload(caseId: string) {
  const dirHandle = await window.showDirectoryPicker();
  for await (const entry of dirHandle.values()) {
    if (entry.kind === "file") {
      const file = await entry.getFile();
      await api.uploadFile(caseId, file);
    }
  }
}
```

**File downloads** become simple `<a href="/api/export/pdf/{caseId}/{prepId}" download>` links. No more generating files on every render.

---

## 10. AUTHENTICATION & RBAC

### Current: PIN + Google OAuth via Streamlit Session

- Users authenticate via 4-digit PIN (SHA-256 hashed) or Google OAuth
- `current_user` dict stored in `st.session_state`
- Role-based access: admin (all cases), attorney/paralegal (assigned cases only)
- `st.stop()` halts script if not authenticated
- Encryption passphrase stored in `st.session_state._encryption_key` (SECURITY RISK)

### Target: NextAuth.js + FastAPI JWT

```typescript
// Frontend: NextAuth.js handles login UI + session
// middleware.ts — protects all routes
export { default } from "next-auth/middleware";
export const config = { matcher: ["/((?!login|api/auth).*)"] };
```

```python
# Backend: FastAPI JWT middleware
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
import jwt

security = HTTPBearer()

async def get_current_user(token = Depends(security)):
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=["HS256"])
        user = user_manager.get_user(payload["user_id"])
        if not user:
            raise HTTPException(401)
        return user
    except jwt.InvalidTokenError:
        raise HTTPException(401)

# RBAC decorator
def require_role(*roles):
    def checker(user = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return user
    return checker
```

**Encryption key:** Stays server-side only. Never sent to client. FastAPI middleware injects it from environment or secure vault.

---

## 11. BACKGROUND WORKERS & PROGRESS

### Current Worker Architecture

4 background daemon threads communicate via JSON files on disk:

1. **Analysis Worker** (`core/bg_analysis.py`) — Spawns LangGraph pipeline, streams tokens to `progress.json`. Supports `active_modules` for partial re-analysis. Uses `_active_analysis_threads` global dict.

2. **Ingestion Worker** (`core/ingestion_worker.py`) — Processes documents with OCR-cache-aware pipeline. 30-min per-file timeout. Heartbeat thread every 15s. Stale detection (auto-resets after 5 min).

3. **OCR Worker** (`core/ocr_worker.py`) — Page-level incremental OCR. Priority queue for user-requested files. Auto-triggers on page text <50 chars or quality score <60.

4. **Transcription Worker** (`core/transcription_worker.py`) — Audio transcription with heartbeat.

### Why They Work with FastAPI

These workers are **independent daemon threads** that use **disk-based IPC** (JSON files). They do NOT depend on Streamlit. They will work identically with FastAPI — the API just calls the same start/stop/status functions.

The only change: Replace Streamlit's polling (auto-refresh every 2-5s) with WebSocket streaming (server pushes every 500ms).

### Worker Status Monitoring Pattern

```python
# api/websockets/workers_ws.py
@router.websocket("/ws/workers/{case_id}")
async def worker_status(ws: WebSocket, case_id: str):
    """Unified worker status stream for a case."""
    await ws.accept()
    try:
        while True:
            status = {
                "analysis": bg_analysis.get_analysis_progress(case_id, prep_id),
                "ingestion": ingestion_worker.get_ingestion_status(case_id),
                "ocr": ocr_worker.get_ocr_status(case_id),
            }
            await ws.send_json(status)

            # Stop if all idle
            if all(s.get("status") in (None, "idle", "complete", "error")
                   for s in status.values()):
                break
            await asyncio.sleep(0.5)
    finally:
        await ws.close()
```

---

## 12. KNOWN ISSUES & TECHNICAL DEBT

### Critical Issues (Must Address During Migration)

1. **275 `st.rerun()` calls** — Every one of these is a state management problem. In React, they become component re-renders (automatic) or state updates (explicit). No equivalent needed.

2. **713 `st.session_state` references with no schema** — No TypedDict, no validation, keys scattered across 20+ files. Create proper Zustand stores with TypeScript interfaces.

3. **100+ broad `except Exception` blocks** — Hide real errors. Replace with specific exception types and structured error responses.

4. **Encryption key in client-side session state** — Security risk. Move to server-side only.

5. **RerunException caught by `except Exception`** — The `_scan_and_import_folder()` bug where `st.rerun()` inside `try/except Exception` was silently swallowed. This entire category of bug vanishes with React (no reruns).

### High Priority Issues

6. **50+ direct file I/O operations in UI code** — Files read directly from disk in UI modules. All file access must go through API routes.

7. **Hardcoded paths** in 3+ files:
   - `ui/pages/esign_ui.py:21-22` — `DATA_DIR = os.path.join("data", "cases")`
   - `ui/pages/tools_ui.py:41` — `PROJECT_ROOT / "data" / "cases"`
   - `ui/case_view.py:2174,2264,2310` — `os.path.join(DATA_DIR, case_id, "ingestion_cache.json")`

8. **tkinter dependency** — Platform-specific folder picker. Eliminated by File System Access API.

9. **14 `unsafe_allow_html=True` instances** — Some render LLM output directly as HTML. Must sanitize.

10. **Global mutable state** — 8+ threading lock globals, 4+ active worker dicts, thread-local storage. These all live in `core/` and are fine — just don't create new ones in the API layer.

### Medium Priority Issues

11. **No `@st.cache_data` or `@st.cache_resource` usage** — All caching is manual version-counter based. TanStack Query handles this automatically.

12. **30+ magic numbers** (timeouts, thresholds, limits) — Should be in `config.yaml`. Many are:
   - OCR quality threshold: 60
   - OCR sparse threshold: 50 chars
   - Stale detection: 5 minutes
   - Heartbeat interval: 15 seconds
   - Max preview text: 10,000 / 5,000 / 50,000 chars
   - UI poll intervals: 2000-5000ms
   - Per-file timeout: 30 minutes

13. **case_view.py is 3121 lines** — Must be decomposed into 15+ React components.

14. **theme.py is 1005 lines of CSS** — Replace entirely with Tailwind CSS + CSS variables.

### Issues That Vanish With Migration

These Streamlit problems disappear entirely with Next.js + FastAPI:

- All 275 `st.rerun()` calls (React re-renders automatically)
- `_uploader_key_counter` hack (React file inputs are stateless)
- `_dash_cache_ver` manual cache invalidation (TanStack Query handles this)
- iframe-based custom components (native React components)
- `st.stop()` execution halting (middleware + route guards)
- Script-reruns-on-every-click (React event handlers)
- `streamlit-autorefresh` polling (WebSockets)
- Theme CSS generation in Python (Tailwind)

---

## 13. MIGRATION PHASES

### Phase 0: FastAPI Foundation (Week 1-2)

**Goal:** API server running alongside existing Streamlit, sharing the same `core/` and `data/`.

1. Create `api/` directory structure
2. Set up FastAPI app with CORS (allow Next.js dev server)
3. Implement dependency injection (`deps.py`) for CaseManager, UserManager
4. Implement JWT auth middleware
5. Build 3 critical routers: `users.py`, `cases.py`, `files.py`
6. Add WebSocket endpoint for analysis progress
7. Write API tests (pytest + httpx)
8. **Verify:** Both Streamlit and FastAPI can read/write the same `data/` directory simultaneously

### Phase 1: Next.js Shell (Week 2-3)

**Goal:** Basic Next.js app that can authenticate and display the dashboard.

1. `npx create-next-app@latest frontend --typescript --tailwind --app`
2. Install shadcn/ui, TanStack Query, Zustand, NextAuth.js
3. Build login page with PIN auth (call FastAPI `/api/users/login`)
4. Build dashboard page (case list with TanStack Table)
5. Build sidebar layout (case navigation)
6. Set up API client (`lib/api.ts`) with JWT token injection
7. **Verify:** Can log in and see case list from same data as Streamlit

### Phase 2: Case War Room (Week 3-6)

**Goal:** Replace the 3121-line case_view.py with React components.

1. Case layout with header, phase badge, metrics
2. File library with drag-and-drop upload (react-dropzone)
3. Analysis tab with WebSocket progress streaming
4. Each module tab as a separate page/component
5. Inline editing with React Hook Form
6. Export downloads as `<a href>` links to API routes

**Build order by priority:**
1. Files (upload, list, OCR status, download) — needed for everything
2. Analysis (start, progress, results) — the core feature
3. Core Analysis results (case summary, strategy, elements)
4. Witnesses (cross-exam, direct-exam)
5. Evidence (tags, foundations)
6. Strategy (voir dire, mock jury)
7. Document Drafter (outline, draft, review)
8. Research
9. Billing
10. Calendar
11. Compliance
12. E-Signature
13. Activity Log

### Phase 3: Remaining Features (Week 6-8)

1. CRM (client directory, intake forms)
2. Document viewer (PDF rendering with react-pdf)
3. Document comparison (side-by-side diff)
4. Snapshot comparison
5. Navigation settings (API key management, model provider selection)
6. Phase config editor

### Phase 4: Polish & Deploy (Week 8-10)

1. Theme system (Tailwind dark mode)
2. Responsive design (mobile-friendly)
3. Error boundaries and loading states
4. Toast notifications (sonner)
5. Keyboard shortcuts
6. Vercel deployment for frontend
7. FastAPI deployment (systemd or Docker)
8. Remove Streamlit dependencies from `requirements.txt`
9. Delete `ui/` directory

---

## 14. TESTING STRATEGY

### Existing Tests (KEEP)
222 pytest tests covering `core/` — these continue to pass unchanged.

### New API Tests
```python
# tests/test_api_cases.py
from httpx import AsyncClient

async def test_list_cases(client: AsyncClient, auth_headers):
    response = await client.get("/api/cases", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

async def test_create_case(client: AsyncClient, auth_headers):
    response = await client.post("/api/cases", json={
        "case_name": "Test v. State",
        "case_category": "criminal",
    }, headers=auth_headers)
    assert response.status_code == 201
    assert "case_id" in response.json()
```

### Frontend Tests
```typescript
// __tests__/dashboard.test.tsx
import { render, screen } from "@testing-library/react";
import Dashboard from "@/app/page";

test("renders case list", async () => {
  render(<Dashboard />);
  expect(await screen.findByText("Cases")).toBeInTheDocument();
});
```

---

## 15. DEPLOYMENT

### Development
```bash
# Terminal 1: FastAPI
cd project-mushroom-cloud
uvicorn api.main:app --reload --port 8000

# Terminal 2: Next.js
cd project-mushroom-cloud/frontend
npm run dev  # Port 3000
```

### Production

**Frontend (Vercel Pro — $20/mo):**
- Push `frontend/` to Vercel
- Set environment variables: `NEXT_PUBLIC_API_URL`, `NEXTAUTH_SECRET`
- Automatic deployments on push

**Backend (Your Server):**
- Systemd service running uvicorn (or gunicorn + uvicorn workers)
- Same server that currently runs Streamlit
- HTTPS via Cloudflare Tunnel (already configured in `deploy/`)

```ini
# deploy/mushroom-cloud-api.service
[Unit]
Description=Project Mushroom Cloud API
After=network.target

[Service]
Type=simple
User=tlo
WorkingDirectory=/opt/mushroom-cloud
Environment="PATH=/opt/mushroom-cloud/venv/bin:/usr/local/bin:/usr/bin"
EnvironmentFile=-/opt/mushroom-cloud/.env
ExecStart=/opt/mushroom-cloud/venv/bin/uvicorn api.main:app \
    --host 0.0.0.0 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 16. FILE-BY-FILE MIGRATION MAP

### Files to DELETE (Streamlit UI — all replaced by Next.js)
```
ui/router.py
ui/case_dashboard.py
ui/case_view.py            # 3121 lines → 15+ React components
ui/navigation.py
ui/login.py
ui/shared.py
ui/splash.py
ui/theme.py                # 1005 lines → Tailwind config
ui/components/folder_drop.py
ui/components/folder_drop_frontend/
ui/pages/core_analysis_ui.py
ui/pages/major_docs_ui.py
ui/pages/evidence_ui.py
ui/pages/witnesses_ui.py
ui/pages/strategy_ui.py
ui/pages/research_ui.py
ui/pages/tools_ui.py
ui/pages/billing_ui.py
ui/pages/calendar_ui.py
ui/pages/master_calendar_ui.py
ui/pages/ethical_compliance_ui.py
ui/pages/esign_ui.py
ui/pages/activity_ui.py
ui/pages/doc_viewer_ui.py
ui/pages/doc_compare_ui.py
```

### Files to DELETE (Streamlit-only)
```
app.py                     # Replaced by api/main.py
launcher.py                # Replaced by deployment scripts
.streamlit/                # Entire directory
```

### Files to KEEP (Business Logic)
```
core/**/*                  # ALL OF IT — untouched
tests/**/*                 # ALL OF IT — keep + add API tests
data/**/*                  # ALL OF IT — same data directory
deploy/**/*                # KEEP — update for FastAPI
config.yaml                # KEEP — add API-specific config
.env                       # KEEP — add JWT_SECRET, NEXTAUTH_SECRET
requirements.txt           # UPDATE — remove streamlit, add fastapi/uvicorn
```

### Files to CREATE (New)
```
api/main.py
api/deps.py
api/auth.py
api/routers/*.py           # 12+ router files
api/websockets/*.py        # 2-3 WebSocket handlers
frontend/                  # Entire Next.js app
```

---

## 17. SESSION STATE KEY REGISTRY

Complete list of all `st.session_state` keys used in the current codebase. Each needs a home in the new architecture:

### Authentication (-> Zustand authStore + JWT)
| Key | Type | Used In | New Home |
|-----|------|---------|----------|
| `current_user` | dict | app.py, shared.py, navigation.py | Zustand authStore |
| `_encryption_key` | str | app.py, shared.py | Server-side env var (NEVER client) |
| `login_method` | str | login.py | JWT claims |

### Navigation (-> Next.js Router + Zustand)
| Key | Type | Used In | New Home |
|-----|------|---------|----------|
| `current_case_id` | str | router.py, navigation.py, case_view.py | URL params: `/cases/[id]` |
| `current_prep_id` | str | case_view.py, pages/*.py | URL params or Zustand |
| `_active_tab` | str | case_view.py | URL path: `/cases/[id]/analysis` |

### Cache (-> TanStack Query automatic)
| Key | Type | Used In | New Home |
|-----|------|---------|----------|
| `_dash_cache_ver` | int | 27 references! | TanStack `invalidateQueries()` |
| `_file_cache_ver` | int | case_view.py | TanStack `invalidateQueries()` |
| `_uploader_key_counter` | int | case_view.py | Not needed (React) |
| `_cached_files_{case_id}` | list | case_view.py | TanStack Query cache |
| `_dash_metrics_cache` | dict | case_dashboard.py | TanStack Query cache |

### UI State (-> React component state or Zustand)
| Key | Type | Used In | New Home |
|-----|------|---------|----------|
| `_editing_X_id` (20+ keys) | str/None | Various pages | React `useState` per component |
| `_confirm_purge` | bool | navigation.py | React Dialog state |
| `_dash_new_case_open` | bool | case_dashboard.py | React Dialog state |
| `theme` | str | app.py, theme.py | Zustand + CSS class on `<html>` |
| `model_provider` | str | navigation.py, shared.py | Zustand settingsStore |
| `_max_context_mode` | bool | navigation.py | Zustand settingsStore |

### Analysis State (-> TanStack Query + WebSocket)
| Key | Type | Used In | New Home |
|-----|------|---------|----------|
| `agent_results` | dict | case_view.py, pages/*.py | TanStack Query: `/api/preps/{id}/state` |
| `chat_history` | list | case_view.py | TanStack Query |
| `session_costs` | dict | navigation.py | Zustand or API |
| `_compare_snapshot_id` | str | core_analysis_ui.py | URL search params |

---

## 18. CRITICAL WARNINGS

### DO NOT Change These

1. **`core/storage/encrypted_backend.py` magic bytes** — `b"TLO_ALLRISE_ENCRYPTION_VERIFIED"` — changing breaks existing encrypted data. Leave as-is.

2. **Append-only key merge logic** (`core/append_only.py`) — Deduplication by ID for witnesses, timeline, etc. Don't bypass with direct overwrites.

3. **Case lock patterns** (`core/case_manager.py`) — Per-case threading locks protect prep index mutations. The FastAPI layer inherits this protection since it shares the same process.

4. **Progress file format** (`progress.json`) — Background workers write this. WebSocket layer reads it. Don't change the format or workers break.

5. **OCR cache manifest format** — `data/cases/{id}/ocr_cache/manifest.json` — Page-level tracking enables resumable OCR. Breaking format loses OCR progress.

### Watch Out For

1. **Thread safety with multiple uvicorn workers** — If you run `uvicorn --workers 4`, each worker gets its own `_case_locks` dict. This breaks thread safety for concurrent case mutations. Options:
   - Use `--workers 1` (simplest, probably fine for your scale)
   - Use file-based locking (fcntl.flock)
   - Use Redis distributed locks

2. **Background workers are daemon threads** — They die when the process exits. With uvicorn workers, a worker restart kills running analysis. Consider: move long-running tasks to a separate process (Celery, or a dedicated analysis server).

3. **Data directory must be shared** — FastAPI and any background workers must read/write the same `data/` directory. With Vercel, the frontend is remote — only the API server needs local `data/` access.

4. **Export functions return `io.BytesIO`** — FastAPI's `StreamingResponse` works perfectly with these. Just return the BytesIO directly.

5. **LLM calls are synchronous** — All nodes in `core/nodes/` use synchronous `invoke_with_retry_streaming()`. FastAPI routes should use `run_in_executor()` or `asyncio.to_thread()` to avoid blocking the event loop:
   ```python
   @router.post("/draft-section")
   async def draft_section(request: DraftRequest):
       result = await asyncio.to_thread(
           major_docs.draft_document_section,
           state, request.section, request.outline
       )
       return {"content": result}
   ```

6. **Uses fpdf 1.7.2 (NOT fpdf2)** — The PDF export code uses `ln=1` not `new_x/new_y`, and has an `epw` property polyfill. Don't upgrade fpdf without testing all exports.

7. **Source files still say "AllRise Beta"** — The Python source still has AllRise Beta branding. Update to "Project Mushroom Cloud" as you build the new frontend.

---

## APPENDIX A: QUICK REFERENCE — CORE/ PUBLIC API

### CaseManager (90+ methods) — Most Called
```python
cm.list_cases(include_archived=False) -> List[Dict]
cm.get_case_metadata(case_id) -> Dict
cm.create_case(case_name, description, ...) -> str  # Returns case_id
cm.delete_case(case_id)
cm.get_case_files(case_id) -> List[str]
cm.save_file(case_id, file_obj, filename) -> str
cm.delete_file(case_id, filename) -> bool
cm.list_preparations(case_id) -> List[Dict]
cm.create_preparation(case_id, prep_type, prep_name="") -> str
cm.save_prep_state(case_id, prep_id, state)
cm.load_prep_state(case_id, prep_id) -> Optional[Dict]  # Returns None if no state
cm.get_phase(case_id) -> tuple[str, str]  # (phase, sub_phase)
cm.set_phase(case_id, phase, sub_phase="")
cm.purge_source_docs(case_id) -> int  # Returns count deleted
cm.get_activity_log(case_id, limit=50) -> List[Dict]
cm.log_activity(case_id, action, description="", user_id="")
cm.compute_docs_fingerprint(case_id) -> str  # SHA-256 for cache invalidation
```

### Background Workers — Control Functions
```python
# Analysis
bg_analysis.start_background_analysis(case_id, prep_id, case_mgr, model_provider, force_rerun=False, active_modules=None)
bg_analysis.stop_background_analysis(case_id, prep_id)
bg_analysis.get_analysis_progress(case_id, prep_id) -> dict  # Has stale detection
bg_analysis.is_analysis_running(case_id, prep_id) -> bool

# Ingestion
ingestion_worker.start_background_ingestion(case_id, case_mgr, model_provider, force_ocr=False)
ingestion_worker.get_ingestion_status(case_id) -> dict

# OCR
ocr_worker.start_ocr_worker(case_id, case_mgr, model_provider) -> bool
ocr_worker.stop_ocr_worker(case_id)
ocr_worker.get_ocr_status(case_id) -> dict
ocr_worker.prioritize_file(case_id, file_key)
```

### Export Functions — All Return BytesIO
```python
pdf_export.generate_pdf_report(state, case_name) -> io.BytesIO
pdf_export.generate_trial_binder_pdf(state, case_name, prep_type, prep_name) -> io.BytesIO
word_export.generate_word_report(state, case_name, module_filter=None) -> io.BytesIO
word_export.generate_brief_outline(state, case_name) -> io.BytesIO
quick_cards.generate_quick_cards_pdf(state, card_type, case_name) -> io.BytesIO
```

---

## APPENDIX B: BRANDING

The source code currently uses "AllRise Beta" branding (inherited from fork). Update to "Project Mushroom Cloud" as you build:

- `app.py` — page title, logger name
- `launcher.py` — app title
- `ui/case_dashboard.py` — hero title
- `ui/login.py` — login page title
- `core/export/pdf_export.py` — PDF header/footer
- `core/export/word_export.py` — Word footer
- `core/nodes/major_docs.py` — User-Agent string
- `deploy/` — all service files reference "allrise-beta"
- `requirements.txt` — comment header

**DO NOT change:** `core/storage/encrypted_backend.py` magic bytes (`b"TLO_ALLRISE_ENCRYPTION_VERIFIED"`)

---

*Guide prepared by Claude Opus, February 2026. Based on complete audit of 102 Python files, 43K+ lines of code, 222 tests, 275 st.rerun() calls, 713 session_state references, and 4 background worker architectures.*
