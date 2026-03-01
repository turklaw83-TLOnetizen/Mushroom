# 🍄 Project Mushroom Cloud

**AI-powered legal case management platform** built with Next.js 16 + FastAPI + PostgreSQL.

---

## Quick Start

```bash
# Clone
git clone <your-repo-url>
cd project-mushroom-cloud

# Copy env
cp .env.example .env
# Edit .env with your Clerk + DB credentials

# Start everything (dev)
docker compose up -d

# Or run individually:
# Backend
cd api && pip install -r requirements.txt && uvicorn api.main:app --reload
# Frontend
cd frontend && npm install && npm run dev
```

Visit **http://localhost:3000**

---

## Architecture

```
┌──────────────────────────────────────────────┐
│                  Nginx (SSL)                  │
│         ┌──────────┬──────────┐              │
│         │ /api/*   │ /*       │              │
│         ▼          ▼          │              │
│    ┌─────────┐ ┌──────────┐  │              │
│    │ FastAPI │ │ Next.js  │  │              │
│    │ (8000)  │ │  (3000)  │  │              │
│    └────┬────┘ └──────────┘  │              │
│         │                     │              │
│    ┌────▼────┐               │              │
│    │Postgres │               │              │
│    │ (5432)  │               │              │
│    └─────────┘               │              │
└──────────────────────────────────────────────┘
```

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TanStack Query, Clerk Auth |
| Backend | FastAPI, Pydantic, SQLAlchemy, Starlette Middleware |
| Database | PostgreSQL 16 with encrypted storage |
| AI | OpenAI / Anthropic LLMs for analysis + summaries |
| Auth | Clerk (JWKS verification, RBAC) |
| Deployment | Docker, Nginx, GitHub Actions CI/CD |

## Features (32 API Routers)

| Category | Features |
|----------|----------|
| **Case Management** | CRUD, sub-tabs (files, analysis, witnesses, evidence, strategy, billing, calendar, compliance, documents, research, activity) |
| **AI Features** | Case analysis, AI summaries (4 styles), deposition prep |
| **Client Management** | CRM, conflict of interest checker, client portal |
| **Productivity** | Task board (kanban), workflow automation, email queue, calendar sync |
| **Compliance** | SOL tracker (10 case types × 4 states), audit trail, compliance checks |
| **Infrastructure** | Rate limiting, input sanitization, encryption-at-rest, backup/restore, export, search |

## Frontend Routes (24)

```
/                Dashboard + stats
/tasks           Kanban task board
/crm             Client management
/email           Email queue + review
/conflicts       Conflict of interest check
/analytics       SVG charts + insights
/portal          Client-facing portal
/profile         User profile + sessions
/settings        Integrations + backup
/admin           Health dashboard
/cases/[id]      Case detail + 11 sub-tabs
/sign-in         Clerk authentication
```

## Middleware Stack

1. **RequestID** — Unique ID per request for tracing
2. **SecurityHeaders** — HSTS, X-Frame-Options, CSP
3. **AuditTrail** — Logs all mutations to audit table
4. **RateLimit** — Per-IP sliding window (120/min)
5. **UploadSize** — 20GB max upload
6. **InputSanitization** — XSS + SQL injection scanning
7. **CORS** — Locked to explicit origins

## Testing

```bash
# Backend unit/integration tests
pytest tests/ -v

# Frontend E2E (Playwright)
cd frontend && npx playwright test

# TypeScript check
cd frontend && npx tsc --noEmit
```

## Deployment

```bash
# Production build
docker compose -f docker-compose.prod.yml up -d

# SSL certs go in nginx/certs/
# fullchain.pem + privkey.pem
```

See `.env.example` for all configuration options.

## License

Proprietary — All rights reserved.
