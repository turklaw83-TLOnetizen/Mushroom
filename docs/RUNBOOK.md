# Admin Runbook

## Daily Operations

### Health Check
```bash
curl https://yourdomain.com/api/v1/health
# Expected: {"status": "healthy", "database": "connected", ...}
```

### View Logs
```bash
# Docker logs
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f frontend

# Last 100 lines
docker compose -f docker-compose.prod.yml logs --tail=100 api
```

---

## Common Issues

### 502 Bad Gateway
1. Check if API container is running: `docker ps`
2. Check API logs: `docker logs mushroom-cloud-api`
3. Restart: `docker compose restart api`

### Database Connection Errors
1. Verify DB is running: `docker ps | grep postgres`
2. Check connection: `docker exec mushroom-cloud-db pg_isready`
3. Restart DB: `docker compose restart db`
4. ⚠️ Wait 30s for health check before restarting API

### Rate Limiting (429 Errors)
- Default: 120 requests/minute per IP
- Adjust: `RATE_LIMIT_REQUESTS` env var
- Admin endpoints are exempt

### File Upload Failures
- Max size: 20GB (set via `MAX_UPLOAD_SIZE_BYTES`)
- Check Nginx: `client_max_body_size 20G` in nginx.conf
- Check API: `UploadSizeMiddleware` in main.py
- Large uploads require `proxy_request_buffering off` in Nginx

---

## Backup & Restore

### Manual Backup
```bash
# Database
docker exec mushroom-cloud-db pg_dump -U mushroom mushroom_cloud > backup_$(date +%Y%m%d).sql

# Application data
docker cp mushroom-cloud-api:/app/data ./backup_data_$(date +%Y%m%d)
```

### Restore
```bash
docker exec -i mushroom-cloud-db psql -U mushroom mushroom_cloud < backup_20260228.sql
```

---

## Database Maintenance

### Run Migrations
```bash
docker exec mushroom-cloud-api alembic upgrade head
```

### Create New Migration
```bash
alembic revision --autogenerate -m "description"
```

### Vacuum (Weekly)
```bash
docker exec mushroom-cloud-db vacuumdb -U mushroom --analyze mushroom_cloud
```

---

## SSL Certificate Renewal

Certs are in `nginx/certs/`:
```bash
# Using certbot
certbot renew
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/certs/
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/certs/
docker compose restart nginx
```

---

## Scaling

### Horizontal API Scaling
Adjust workers in docker-compose.prod.yml:
```yaml
command: uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 8
```

### Database Scaling
- Add read replicas for heavy read workloads
- Enable connection pooling with PgBouncer
- Monitor with `pg_stat_statements`

---

## Security Checklist (Monthly)
- [ ] Verify encryption-at-rest is active (`/api/v1/health` → encryption status)
- [ ] Review audit logs for anomalies
- [ ] Check for outdated dependencies (`npm audit`, `pip audit`)
- [ ] Verify CORS origins match production domain
- [ ] Confirm rate limiting is working (test with `curl` loop)
- [ ] Rotate ENCRYPTION_KEY if compromised
- [ ] Review Clerk user list for stale accounts
