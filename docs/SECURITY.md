# Security Self-Assessment

## Authentication & Authorization
| Control | Status | Notes |
|---------|--------|-------|
| JWT verification (JWKS) | ✅ | Clerk JWKS with signature validation |
| Role-based access control | ✅ | `require_role()` decorator on sensitive endpoints |
| Session timeout | ✅ | Configurable via `SESSION_TIMEOUT_MINUTES` |
| Webhook signature verification | ✅ | HMAC SHA-256 on Clerk webhooks |
| User access revocation | ✅ | Auto-revoke on `user.deleted` webhook |

## Data Protection
| Control | Status | Notes |
|---------|--------|-------|
| Encryption at rest | ⚠️ | `EncryptedStorageBackend` available; requires `ENCRYPTION_KEY` |
| HTTPS only | ✅ | Nginx HTTP→HTTPS redirect + HSTS |
| CORS lockdown | ✅ | Explicit origins only (no wildcards) |
| File upload scanning | ⚠️ | Size limit enforced (20GB); content scanning not yet implemented |
| Sensitive data masking | ⚠️ | Not yet in logs; PII may appear in debug logging |

## Input Validation
| Control | Status | Notes |
|---------|--------|-------|
| XSS prevention | ✅ | `InputSanitizationMiddleware` scans all JSON bodies |
| SQL injection prevention | ✅ | Parameterized queries (SQLAlchemy) + input scanning |
| Command injection | ✅ | No shell execution in request handlers |
| Upload size limits | ✅ | 20GB at Nginx + application layer |
| Rate limiting | ✅ | Per-IP sliding window (120/min default) |

## Infrastructure
| Control | Status | Notes |
|---------|--------|-------|
| Security headers | ✅ | X-Frame-Options, X-Content-Type-Options, HSTS, CSP |
| Non-root containers | ✅ | Frontend runs as `nextjs:1001` user |
| No exposed DB port | ✅ | Postgres only on internal Docker network |
| Audit logging | ✅ | All mutations logged with user, timestamp, action |
| Request tracing | ✅ | `X-Request-ID` header on all responses |

## Compliance
| Control | Status | Notes |
|---------|--------|-------|
| Conflict of interest checks | ✅ | Cross-reference CRM + all case parties |
| Statute of limitations tracking | ✅ | Auto-deadline calculation + email alerts |
| Audit trail | ✅ | Immutable audit log for all CRUD operations |
| Data retention policy | ⚠️ | Not yet implemented — cases are soft-deleted |
| GDPR data export | ⚠️ | Not yet implemented |

## Outstanding Items
1. **Content scanning for uploads** — Malware/virus scanning on uploaded files
2. **PII masking in logs** — Structured logging should redact sensitive fields
3. **Data retention automation** — Auto-purge stale data per retention policy
4. **GDPR data export** — Client data portability endpoint
5. **2FA enforcement** — Clerk supports it but not yet enforced for attorney accounts

---

*Last reviewed: February 2026*
