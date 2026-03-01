# Launch Checklist

## Pre-Launch (1 week before)

### Infrastructure
- [ ] Production server provisioned (4+ cores, 16GB+ RAM for 20GB uploads)
- [ ] PostgreSQL 16 installed/configured with connection pooling
- [ ] SSL certificates obtained (Let's Encrypt or similar)
- [ ] Domain DNS configured (A/CNAME records)
- [ ] Docker + Docker Compose installed on production

### Security
- [ ] Generate production `ENCRYPTION_KEY` (256-bit: `openssl rand -hex 32`)
- [ ] Set production `CLERK_SECRET_KEY` + `CLERK_WEBHOOK_SECRET`
- [ ] Lock `CORS_ORIGINS` to production domain only
- [ ] Remove all `*` wildcards from env vars
- [ ] Verify Nginx security headers are set
- [ ] Test rate limiting works (burst test)

### Database
- [ ] Run Alembic migrations: `alembic upgrade head`
- [ ] Verify indexes are created: `\di` in psql
- [ ] Test backup + restore procedure
- [ ] Configure automated daily backups

### Environment
- [ ] All `.env.example` vars set in production `.env`
- [ ] SMTP configured for deadline alert emails
- [ ] LLM API keys set (Anthropic/OpenAI)
- [ ] Clerk webhook URL registered in Clerk dashboard

---

## Launch Day

### Deploy
- [ ] `docker compose -f docker-compose.prod.yml build`
- [ ] `docker compose -f docker-compose.prod.yml up -d`
- [ ] Verify all containers running: `docker ps`

### Verify
- [ ] Health check passes: `curl https://yourdomain.com/api/v1/health`
- [ ] Frontend loads: `https://yourdomain.com`
- [ ] Sign-in works via Clerk
- [ ] Create a test case
- [ ] Upload a test file
- [ ] Run AI analysis on test case
- [ ] Run conflict check
- [ ] Verify SOL deadline calculation
- [ ] Check analytics page renders

### Monitor
- [ ] Check Docker logs for errors
- [ ] Verify request IDs appear in responses
- [ ] Test rate limiting doesn't block legitimate use
- [ ] Confirm email alerts fire for test deadline

---

## Post-Launch (first week)

- [ ] Monitor error rates in logs
- [ ] Verify backup job runs daily
- [ ] Check disk space (20GB uploads add up fast)
- [ ] Review audit log for anomalies
- [ ] Collect user feedback
- [ ] Plan Phase 16+ based on production learnings
