# Project Mushroom Cloud

> Forked from AllRise Beta (Feb 2026). Independent repo — no shared git history.
> GitHub: `https://github.com/turklaw83-TLOnetizen/Mushroom.git`

## Project Overview
Project Mushroom Cloud — a legal case management and AI analysis platform.
- **Original UI**: Streamlit (still in `app.py`, `ui/`)
- **Production UI**: Next.js 16 + FastAPI (deployed at https://turkclaw.net)
- **Local repo**: `C:\Users\turkl\project-mushroom-cloud`
- **Active branch**: `claude/quizzical-panini`

## Production Deployment
- **VPS**: Vultr (2 vCPU / 4 GB RAM / 80 GB SSD) at `45.32.216.52`
- **Domain**: `turkclaw.net` (Cloudflare DNS + Origin Certificate, Full strict SSL)
- **Stack**: Docker Compose with 5 containers:
  - `postgres` — PostgreSQL 16 (port 5432, internal)
  - `api` — FastAPI via uvicorn (port 8000, internal)
  - `frontend` — Next.js 16 standalone (port 3000, internal)
  - `nginx` — reverse proxy (ports 80/443, public)
- **Auth**: Clerk (Google OAuth) — `proxy.ts` handles auth token forwarding to API
- **Docker files**: `docker-compose.prod.yml`, `Dockerfile.api`, `frontend/Dockerfile`, `nginx.conf`
- **Requirements**: `requirements-api.txt` (slim, excludes PyTorch/streamlit/chromadb for fast builds)
- **Health check**: `GET /api/v1/health` returns DB status, latency, disk free, LLM config

## Architecture — Next.js Frontend (`frontend/`)
- **Framework**: Next.js 16 App Router + TypeScript + Tailwind CSS
- **Auth**: Clerk (`@clerk/nextjs`) with Google OAuth SSO
- **Data fetching**: TanStack React Query via custom hooks in `frontend/hooks/`
- **API client**: `frontend/lib/api-client.ts` — typed wrapper around fetch with Clerk token injection
- **UI components**: `frontend/components/ui/` — shadcn/ui primitives (button, dialog, input, card, etc.)
- **Key pages**:
  - `app/page.tsx` — Dashboard (case table, widgets, new case dialog)
  - `app/cases/[id]/` — Case detail with 20+ sub-pages (analysis, documents, billing, calendar, etc.)
  - `app/admin/` — Admin panel, tenant management
  - `app/analytics/` — Analytics dashboard

### Key Frontend Components
- **`components/dashboard/new-case-dialog.tsx`** — Create New Case dialog with ClientCombobox + 5 case sub-types
- **`components/ui/client-combobox.tsx`** — Searchable client dropdown with "+ Add New Client" dialog
- **`components/dashboard/case-table.tsx`** — Case list with sorting, filtering, pagination
- **`components/sidebar.tsx`** — Navigation sidebar with case sub-pages

### Key Frontend Hooks
- **`hooks/use-cases.ts`** — React Query hook for case CRUD (`GET/POST /cases`)
- **`hooks/use-clients.ts`** — React Query hooks for CRM clients (`useClients`, `useCreateClient`, `clientDisplayName`)
- **`hooks/use-prep.tsx`** — Preparation data fetching
- **`hooks/use-websocket.ts`** — WebSocket connection for real-time updates
- **`hooks/use-notifications.ts`** — Push notification management

## Architecture — Legacy Streamlit UI (`ui/`)
- **app.py** (~95 lines) — thin entry: splash -> login -> sidebar -> route
- **Tier 1**: `ui/case_dashboard.py` — landing when no case selected (metrics, case table, filters, **client directory**)
- **Tier 2**: `ui/case_view.py` — war room when case open (header, directives, contacts, files, analysis, tabs)
- **Router**: `ui/router.py` — dispatches between dashboard and case view
- **Sidebar**: `ui/navigation.py` — API keys, exports, journal, negotiations, version history, case management
- **Shared**: `ui/shared.py` — singletons, session state, friendly_error(), run_single_node(), render_module_notes()

## Key Classes
- **CaseManager** (`core/case_manager.py`) — all case CRUD, state, files, preps, deadlines, contacts, phase lifecycle, purge
- **BackupManager** (`core/cloud_backup.py`) — Dropbox sync + Backblaze B2 unified backup coordinator
- **UserManager** (`core/user_profiles.py`) — RBAC (admin/attorney/paralegal), PIN/OAuth auth
- **JSONStorageBackend** (`core/storage/json_backend.py`) — file-system JSON persistence (implements ABC)
- **AgentState** (`core/state.py`) — TypedDict for LangGraph workflow state
- **OCRCache** (`core/ingest.py`) — per-case OCR text caching with page-level storage and full-text search
- **DocumentIngester** (`core/ingest.py`) — PDF/image/docx/media processing with quality assessment and cache-aware OCR

## Analysis Pipeline (core/nodes/)
- `graph_builder.py` — builds LangGraph per prep type (trial/prelim/motion), uses `START` for parallel fan-out
- 14 nodes (NODE_LABELS): analyzer, strategist, elements_mapper, investigation_planner, consistency_checker, legal_researcher, devils_advocate, entity_extractor, cross_examiner, direct_examiner, timeline_generator, foundations_agent, voir_dire_agent, mock_jury
- **entity_extractor** runs parallel with analyzer from START (no dependency on case_summary)
- **Attorney directives** (`ctx['directives_block']`) injected in 13/14 nodes (all except entity_extractor)
- On-demand: witness_prep, interview_plan, deposition analysis, statements, opponent playbook
- Node counts by prep type: trial=14, prelim=12, motion=7
- **Per-witness LLM calls**: Cross-exam (State+Swing witnesses) and direct-exam (Defense+Swing) use one call per witness with max_output_tokens=16384

## Background Workers (Daemon Threads)
- **`core/bg_analysis.py`** — Background analysis runner. Streams tokens to `progress.json`. Supports `active_modules` parameter for selective re-analysis. AI stream of consciousness displayed in UI. Saves `_last_per_node_times` for ETA estimates. Witness fingerprint caching for exam nodes.
- **`core/ingestion_worker.py`** — Background document ingestion. Uses `process_file_with_cache()` for OCR-cache-aware processing. 30-min per-file timeout. Heartbeat thread every 15s. Stale detection (auto-resets after 5 min with no heartbeat).
- **`core/ocr_worker.py`** — Passive background OCR worker. Auto-starts on file upload or case open. Processes PDFs/images one page at a time. Stores results in OCRCache. Priority queue for user-requested files.

## OCR System
- **Trigger**: Auto-starts on file upload and case open (passive, background)
- **Cache**: `data/cases/{case_id}/ocr_cache/manifest.json` + `{hash}.txt` per file + `{hash}_p{N}.txt` per page
- **Page-level storage**: Supports resumable OCR (if interrupted mid-file, resumes from last completed page)
- **Quality assessment**: `_assess_text_quality()` scores 0-100 based on word count, control chars, repetitive runs, symbol soup
- **Auto-OCR triggers**: Page text < 50 chars (sparse/scanned) or quality score < 60 (garbled)
- **Vision model**: Sends page image to AI (Claude/Grok) for transcription. 5-min per-page timeout in OCR worker, 120s in ingestion.
- **OCR badges**: Files show status badges in Case Library (green=done, blue=in progress, gray=pending/text, red=error)
- **Force-OCR**: Per-file button to prioritize specific files in OCR queue

## Re-analyze System
- **Re-analyze button** opens inline module selector panel (not full re-analysis)
- **Select All / Deselect All** buttons for module checkboxes
- Skips ingestion — loads cached documents directly
- Calls `start_background_analysis(active_modules=...)` with selected subset
- Falls back to ingestion only if no cached docs exist
- **Run Full Analysis** button unchanged (goes through ingestion -> token preview -> confirm)

## CRM System
- **`core/crm.py`** — Client management: add, search, update, delete, link/unlink to cases
- **Client fields**: first_name, last_name, middle_name, suffix, email, phone, mailing_address, home_address
- **`add_client()`** accepts: first_name, last_name, middle_name, suffix, name (legacy), email, phone, mailing_address, home_address, home_same_as_mailing, referral_source, tags
- **Display name**: `clientDisplayName()` builds "First Middle Last, Suffix" — falls back to `name` field
- **API endpoints**: `GET /crm/clients` (list/search), `POST /crm/clients` (create), `PUT /crm/clients/{id}` (update), `DELETE /crm/clients/{id}` (delete)
- **Frontend**: `ClientCombobox` component in New Case dialog — autocomplete search + "+ Add New Client" dialog
- **Dashboard access**: Client Directory expandable on main landing page (no case needed)
- **In-case access**: Client CRM nav group -> Client Directory, Intake Forms, CRM Dashboard
- **Stats keys**: `total_clients`, `active`, `prospective`, `former`, `declined` (NOT `active_clients` etc.)
- **Intake templates**: general, criminal, civil

## Navigation Groups
- **Investigation Plan** is in **Core Analysis** (moved from Research & Draft for visibility)
- Groups by prep type: Core Analysis, Evidence & Facts, Witnesses & Exam, Strategy & Jury, Research & Draft, Tools, Ethical Compliance, Billing, Client CRM, Calendar, E-Signature, Activity

## Patterns & Conventions
- **Append-only keys**: witnesses, timeline, evidence_foundations, investigation_plan, consistency_check (use `safe_update_and_save`)
- **Edit pattern**: `st.session_state["_editing_X_id"]` toggle for inline edit forms
- **Cache pattern**: session state with `_dash_cache_ver` / `_file_cache_ver` version counters
- **Error handling**: `friendly_error()` in shared.py translates 25+ exception patterns
- **Module notes**: `render_module_notes()` shared helper for per-tab attorney notes
- **Streaming chat**: `invoke_with_retry_streaming()` + `st.write_stream()`
- **Background status**: All workers use JSON files on disk for status communication (not session_state)
- **Stale detection**: Workers check `updated_at` timestamp; auto-reset stuck "running" states
- **Heartbeat**: Long-running file processing sends heartbeat every 15s to refresh `updated_at`

## Case Types & Phase Lifecycle
- **Case types** (New Case dialog): `criminal` (Adult), `criminal-juvenile`, `civil-plaintiff`, `civil-defendant`, `civil-juvenile`
- **CASE_TYPES constant** in `new-case-dialog.tsx` — maps value→label for the 5 types
- **Phases**: Active (with customizable sub-phases) -> Closed -> Archived -> Purge (optional)
- **Sub-phases per case type**: criminal (9 stages), criminal-juvenile (8), civil-plaintiff (9), civil-defendant (8), civil-juvenile (7)
- **Phase config**: `data/phase_config.json` (global, editable via sidebar settings)
- **Purge**: Deletes source docs from archived cases; OCR text, analysis results, vectorstores retained
- **Backward compat**: `_migrate_phase()` derives phase from legacy `status` field on read
- **`_PHASE_TO_STATUS`**: Maps phase->status so old code reading `status` still works
- **Case locks**: `_get_case_lock(case_id)` on all prep index mutations and purge operations

## Major Document Drafter (core/nodes/major_docs.py)
- 8 functions: document_outline, draft_section, citation_library, table_of_authorities, review_brief, analyze_opposing_brief, verify_citations_cross_model, fetch_case_pdfs
- Quality scoring: `core/draft_quality.py` — rubric-based (structure, citations, argumentation, style, completeness)
- Court documents: `core/court_docs.py` — formatting rules per court type (federal, state, appellate)
- Drafts stored via `save_major_draft()` / `load_major_drafts()` on CaseManager

## Cloud Backup (core/cloud_backup.py)
- **DropboxSyncBackup**: Copies to local Dropbox folder; desktop app handles upload. Auto-detects via `~/.dropbox/info.json`
- **B2Backup**: Direct API uploads via b2sdk. Env vars: `B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`
- **BackupManager**: Unified coordinator. `backup_before_purge(case_id)` creates safety archive before file purging
- **Deploy**: `deploy/` directory has systemd service, Cloudflare Tunnel, Tailscale, backup timer/script

## Export System
- **Sidebar exports** (`ui/navigation.py`): Word Report, PDF Report, IRAC Brief, Trial Binder (13-tab)
- **Export All ZIP**: One-click button packages all 4 formats into a single ZIP download
- **Quick Cards**: Courtroom reference cards (witness, evidence, objections) in `core/export/quick_cards.py`
- Uses fpdf 1.7.2 (not fpdf2). `epw` property polyfill on PDFReport and QuickCardPDF. Use `ln=1` not `new_x/new_y`.

## Smart Caching (bg_analysis.py)
- **Document fingerprint**: SHA-256 of sorted `(filename, size)` tuples -> `_docs_fingerprint`
- **Witness fingerprint**: SHA-256 of sorted witness `name+type` -> `_witnesses_fingerprint` (invalidates cross/direct exam cache)
- **`_last_per_node_times`**: Saved after each analysis for ETA estimates on next run
- Core nodes (analyzer, strategist) always run; others skip if docs unchanged + results populated

## UI Features
- **Dashboard**: Readiness column (merged Score+Grade), pagination (10/25/50), sort by 8 columns, filters
- **War Room**: Metrics cards, charges prompt (when missing), performance profile bar chart
- **Analysis progress**: Node grid with ETA estimates, completion toast + summary with cached/regenerated badges
- **Prep selector**: Sorted newest-first by `created_at`

## Security Hardening
- **Path traversal**: `save_file()` / `delete_file()` in json_backend.py reject `../` attacks via `path.resolve()` + `startswith()` check
- **OCRCache thread safety**: Class-level `_manifest_locks` dict with `_manifest_locks_guard` for per-path locking
- **Case locks**: Threading locks on all preparation index mutations (create, delete, rename, clone) and purge
- **Session state isolation**: Staff/client counts keyed by `case_id` to prevent stale data on case switch
- **Router guard**: Checks `case_exists()` before rendering case view; redirects to dashboard if deleted

## Tests
- 222 tests in `tests/` — pytest, all passing at fork point
- Key fixtures in `conftest.py`: tmp_data_dir, storage, sample_case_metadata, populated_storage
- `tests/test_phase_system.py` — 47 tests for phase lifecycle, sub-phases, purge, config
- Run: `cd C:\Users\turkl\project-mushroom-cloud && python -m pytest tests/ -x -q`

## Config
- `config.yaml` — LLM providers (anthropic/xai), models, storage paths
- `.env` — API keys (XAI_API_KEY, ANTHROPIC_API_KEY), DATABASE_URL, CLERK keys
- `.streamlit/config.toml` — theme, server, upload limits (legacy Streamlit)
- `.streamlit/secrets.toml` — OAuth secrets (gitignored, legacy Streamlit)
- `frontend/.env.local` — NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY, CLERK_SECRET_KEY, NEXT_PUBLIC_API_URL
- `docker-compose.prod.yml` — production Docker Compose with env vars for all services

## Docker & Dependencies
- **`requirements.txt`** — Full dependency list (includes streamlit, torch, chromadb — for local/Streamlit use)
- **`requirements-api.txt`** — Slim API-only dependencies (excludes PyTorch 916MB, streamlit, chromadb, pywebview, sentence-transformers, pytest). Used by `Dockerfile.api`
- **`Dockerfile.api`** — Two-stage build: builder installs from `requirements-api.txt`, runtime copies packages + app code
- **`frontend/Dockerfile`** — Next.js standalone build with Clerk env vars
- **`nginx.conf`** — Reverse proxy: `/api/` → api:8000, `/` → frontend:3000, SSL termination via Cloudflare Origin Cert

## User Info
- Default users: Daniel Joseph Turklay (DJT, admin), Cody Ryan Johnson (CRJ, admin)
- **Clerk auth**: Google OAuth via Clerk (production)
- **Legacy auth**: PIN or Google OAuth (Streamlit UI)
- **User email**: daniel@turklaylaw.com

## Known Issues (Inherited from AllRise Beta)
- **clone_preparation null deref**: Fixed — `source_prep.get(...)` guarded with `if source_prep else` fallback
- **delete_major_draft**: Fixed — uses storage API instead of raw `os.remove()`
- **encrypted_backend.py**: Magic bytes `b"TLO_ALLRISE_ENCRYPTION_VERIFIED"` retained for backward compat — changing would break existing encrypted data

## Deployment Commands (VPS)
```bash
ssh root@45.32.216.52
cd /opt/mushroom-cloud
git pull origin claude/quizzical-panini
docker compose build --no-cache api        # rebuild API (uses requirements-api.txt)
docker compose build --no-cache frontend   # rebuild frontend
docker compose up -d                       # restart all services
docker compose logs -f api                 # tail API logs
docker compose logs -f frontend            # tail frontend logs
```

## Branding Note
Source files still reference "AllRise Beta" in many places. These should be updated to "Project Mushroom Cloud" / "mushroom-cloud" as the project evolves. The `core/storage/encrypted_backend.py` magic bytes must NOT be changed (would break encryption verification).
