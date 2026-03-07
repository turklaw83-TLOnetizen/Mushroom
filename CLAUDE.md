# Project Mushroom Cloud

> Forked from AllRise Beta (Feb 2026). Independent repo — no shared git history.

## Project Overview
Project Mushroom Cloud — a Streamlit-based legal case management and AI analysis platform.
Location: `C:\Users\turkl\project-mushroom-cloud`

## Architecture (Two-Tier UI + Clean Core/UI Split)
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

## AI War Game (core/war_game.py)
- **5-round adversarial case simulation**: theory attack → evidence challenge → witness assault → element gaps → jury verdict
- **Cumulative effects**: Each round's outcomes carry forward (excluded evidence affects witness round, etc.)
- **3 difficulty levels**: standard, aggressive, ruthless — each with distinct LLM persona
- **Jury simulation**: 5 jurors with distinct personas deliberate using ALL round results
- **Battle report**: Overall score, ranked vulnerabilities (critical→low) with exploit scenarios + mitigations, contingency playbook ("If they argue X → respond with Y"), juror breakdown
- **Session persistence**: `data/cases/{case_id}/war_game_sessions/{prep_id}/{session_id}.json` (per-file, not array)
- **REST endpoints** (`api/routers/war_game.py`): 7 routes — session CRUD + round attack/respond + finalize
- **Frontend**: `frontend/app/cases/[id]/war-game/page.tsx` — 3 views (dashboard, active session, battle report)

## Argument Forge (core/argument_forge.py)
- **Interactive argument builder**: Multi-step LLM-powered argument development with session persistence
- **REST endpoints** (`api/routers/argument_forge.py`): Session CRUD + argument generation
- **Frontend**: `frontend/components/argument-forge.tsx` — embedded component for case pages

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

## Case Phase Lifecycle
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
- `.env` — API keys (XAI_API_KEY, ANTHROPIC_API_KEY)
- `.streamlit/config.toml` — theme, server, upload limits
- `.streamlit/secrets.toml` — OAuth secrets (gitignored)

## User Info
- Default users: Daniel Joseph Turklay (DJT, admin), Cody Ryan Johnson (CRJ, admin)
- Users authenticate via PIN or Google OAuth

## Known Issues (Inherited from AllRise Beta)
- **clone_preparation null deref**: Fixed — `source_prep.get(...)` guarded with `if source_prep else` fallback
- **delete_major_draft**: Fixed — uses storage API instead of raw `os.remove()`
- **encrypted_backend.py**: Magic bytes `b"TLO_ALLRISE_ENCRYPTION_VERIFIED"` retained for backward compat — changing would break existing encrypted data

## Deleted Files (Dead Code Removed)
- `api/env.py` — unused Settings validator (0 imports)
- `api/pagination.py` — unused pagination helper (0 imports)
- `api/response.py` — unused envelope() function (0 imports)
- `api/routers/ai_features.py` — ghost feature router (endpoints never connected to real backend)
- `core/deadline_chains.py` — orphaned LangChain deadline system (1,031 lines, 0 imports)
- `core/morning_brief.py` — orphaned morning brief generator (replaced by api/routers/morning_brief.py rewrite)

## Branding Note
Source files still reference "AllRise Beta" in many places. These should be updated to "Project Mushroom Cloud" / "mushroom-cloud" as the project evolves. The `core/storage/encrypted_backend.py` magic bytes must NOT be changed (would break encryption verification).

---

## Next.js Frontend (frontend/)

### Stack
- **Next.js 16.1.6** (Turbopack) with App Router
- **Clerk** for auth (`@clerk/nextjs` v6.39.0)
- **React Query** (`@tanstack/react-query`) for data fetching
- **Zustand** for UI state (theme, sidebar) — store key: `mc-ui-store`
- **shadcn/ui** components in `components/ui/`
- **Tailwind CSS v4** with oklch color space

### Key Architecture
- `proxy.ts` — Next.js 16 auth proxy (replaces deprecated middleware.ts). Uses `clerkMiddleware` to protect routes. Public routes: `/sign-in`, `/sign-up`, `/api`.
- `app/layout.tsx` — Root layout. ThemeAwareClerk → QueryProvider → AppShell → children. Inline `<script>` reads theme from localStorage before hydration.
- `components/app-shell.tsx` — Strips sidebar/chrome for auth routes (`/sign-in`, `/sign-up`).
- `components/theme-aware-clerk.tsx` — Reads theme from Zustand, passes to ClerkProvider. Uses stub key `pk_test_YnVpbGQuY2xlcmsuYWNjb3VudHMuZGV2JA` for build-time prerendering when no real key available.
- `lib/api-client.ts` — Typed fetch wrapper with Clerk auth, retry, offline detection. On 401, redirects to `/sign-in` unless already on an auth page.
- `next.config.ts` — CSP headers, `output: "standalone"`, `reactStrictMode: false`.

### Typed CRUD Infrastructure
- **`lib/api-routes.ts`** (~490 lines) — Centralized typed endpoint map. All API paths in one place, no magic strings. Sections: cases, witnesses, evidence, billing, calendar, crm, esign, discovery, comms, compliance, tasks, search, backup, portal, morningBrief, quality, warGame, mockExam, argumentForge.
- **`lib/query-keys.ts`** (~260 lines) — Query key factory using `as const` readonly tuples. Consistent React Query cache keys across all pages. **Note**: Use spread `[...queryKeys.x.y()]` when passing to `invalidateQueries` (readonly→mutable).
- **`lib/constants.ts`** (~270 lines) — 15 status-color maps (ESIGN, DISCOVERY, COMM, INVOICE, PLAN_HEALTH, PRIORITY, TASK, SEVERITY, WITNESS_TYPE, FEED_TX, PAYMENT, STRIPE, GENERIC, WAR_GAME_DIFFICULTY, VERDICT) + `getStatusColor(status, domain)` cascading helper + 5 formatters (`formatDate`, `formatRelativeTime`, `formatBytes`, `formatCurrency`, `formatLabel`).
- **`hooks/use-crud.ts`** (~190 lines) — Composable CRUD hook wrapping `useQuery` + `useMutationWithToast` + `useAuth`. Returns `{ items, isLoading, error, create, update, remove }`.
- **`components/shared/status-badge.tsx`** — Universal `<StatusBadge status="pending" domain="esign" />` with domain-aware color mapping.
- **`components/shared/data-table.tsx`** (~340 lines) — Sortable, filterable, paginated table with column definitions.
- **`components/shared/error-boundary.tsx`** — React class error boundary with retry/reload, wired into `app/layout.tsx`.

### Frontend Pages (47 routes)
- 26 orphaned API endpoint frontends built: billing CRUD, compliance workflows, document versioning/compare, timeline visualization, transcription, research, strategy, conflicts, search, tasks, payments, admin analytics/batch/gdpr, quality dashboard, analysis diff, argument forge
- 11 pages migrated from inline code to shared infrastructure (StatusBadge, constants, api-routes, query-keys)

### CSS/Theming
- `globals.css` — Brand colors use indigo oklch(0.55 0.23 264). Custom variables: `--brand-indigo`, `--brand-violet`, `--brand-lavender`.
- `.glass-card` utility class — backdrop-blur, left gradient accent bar, hover lift, staggered floatIn animation.
- Keyframe animations: `floatIn`, `fadeIn`, `pulseGlow`.
- Theme toggle reads/writes `mc-ui-store` in localStorage and toggles `.dark` class on `documentElement`.

### Environment Variables
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` — Required. Dev: `pk_test_...`, Prod: `pk_live_...`
- `CLERK_SECRET_KEY` — Required server-side.
- `NEXT_PUBLIC_API_URL` — FastAPI backend URL. Default: `http://localhost:8000`
- `NEXT_PUBLIC_CLERK_SIGN_IN_URL` — Default: `/sign-in`
- `NEXT_PUBLIC_CLERK_SIGN_UP_URL` — Default: `/sign-up`

---

## VPS Deployment

### Infrastructure
- **VPS**: Vultr, IP `45.32.216.52`, Ubuntu 22.04
- **Domain**: `turkclaw.net` (Cloudflare DNS + proxy)
- **Clerk prod domain**: `clerk.turkclaw.net` (Clerk loads JS/API from this subdomain)
- **Clerk prod key**: `pk_live_Y2xlcmsudHVya2NsYXcubmV0JA` (encodes to `clerk.turkclaw.net$`)
- **Docker Compose**: `docker-compose.prod.yml` — frontend, api, postgres containers
- **GitHub repo**: `turklaw83-TLOnetizen/Mushroom` (master branch)

### Deploy Commands
```bash
ssh root@45.32.216.52
cd /root/project-mushroom-cloud && git pull && docker compose -f docker-compose.prod.yml build && docker compose -f docker-compose.prod.yml up -d
```

### Critical: CSP Must Include Production Clerk Domain
The CSP in `frontend/next.config.ts` MUST include `*.turkclaw.net` in `script-src`, `connect-src`, and `frame-src`. Without this, Clerk's JS (loaded from `clerk.turkclaw.net`) is blocked by the browser and the sign-in page renders as an empty div.

### Current VPS State (as of 2026-03-06)
- VPS deployed with commit `40f3029` — includes War Game, typed CRUD infrastructure, 26 new frontends
- All 4 containers running: db (healthy), api, frontend, nginx
- CSP fix deployed — `*.turkclaw.net` in script-src/connect-src/frame-src
- Sign-in redirect loop fixes deployed (CSP, API client 401 guard, fallbackRedirectUrl)
- VPS `.env` should have: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...`, `CLERK_SECRET_KEY=sk_live_...`, `DB_PASSWORD=mcloud-db-2026-Kx9m`

### Sign-In Redirect Loop — Root Cause & Fix History (Resolved)
The sign-in page was caught in an infinite redirect loop on production. All fixes deployed as of 2026-03-06:

1. **CSP blocking Clerk JS (THE MAIN CAUSE)**: Production Clerk loads from `clerk.turkclaw.net` but CSP only allowed `*.clerk.accounts.dev`. **Fix**: Added `*.turkclaw.net` to CSP.
2. **API client 401 loop**: `lib/api-client.ts` redirected to `/sign-in` even when already there. **Fix**: Skip redirect if already on auth page.
3. **Missing fallbackRedirectUrl**: Clerk `<SignIn>` had no redirect target. **Fix**: Added `fallbackRedirectUrl="/"`.
