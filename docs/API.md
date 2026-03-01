# API Documentation

## Base URL
```
Production: https://yourdomain.com/api/v1
Development: http://localhost:8000/api/v1
```

## Authentication
All endpoints require a Clerk JWT in the `Authorization: Bearer <token>` header.
Admin-only endpoints require `role: admin` in the Clerk user metadata.

---

## Core Endpoints

### Cases
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cases` | List all cases (paginated) |
| POST | `/cases` | Create new case |
| GET | `/cases/{id}` | Get case details |
| PUT | `/cases/{id}` | Update case |
| DELETE | `/cases/{id}` | Archive case |

### Case Sub-Resources
| Prefix | Resources |
|--------|-----------|
| `/cases/{id}/files` | File uploads + management |
| `/cases/{id}/analysis` | AI analysis + drafts |
| `/cases/{id}/witnesses` | Witness CRUD |
| `/cases/{id}/evidence` | Evidence chain of custody |
| `/cases/{id}/strategy` | Legal strategy notes |
| `/cases/{id}/billing` | Time entries + invoices |
| `/cases/{id}/calendar` | Events + deadlines |
| `/cases/{id}/compliance` | Compliance checks |
| `/cases/{id}/documents` | Document assembly |
| `/cases/{id}/sol` | Statute of limitations |
| `/cases/{id}/ai` | AI summaries + deposition prep |

### CRM
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/crm/clients` | List clients |
| POST | `/crm/clients` | Add client |
| GET | `/crm/clients/{id}` | Client detail |

### Tasks
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cases/{id}/tasks` | List tasks for case |
| POST | `/cases/{id}/tasks` | Create task |
| PUT | `/tasks/{id}` | Update task |
| POST | `/tasks/{id}/complete` | Mark complete |

### Conflicts
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/conflicts/check` | Run conflict check |
| GET | `/conflicts/history` | Check history (audit) |

### Email
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/email/queue` | List pending emails |
| POST | `/email/classify` | Classify to case |
| POST | `/email/dismiss` | Dismiss email |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health + DB status |
| GET | `/admin/health` | Admin dashboard data |
| POST | `/webhooks/clerk` | Clerk webhook receiver |

---

## Response Formats

### Paginated List
```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "page_size": 50,
  "total_pages": 1,
  "has_next": false,
  "has_prev": false
}
```

### Error
```json
{
  "detail": "Error description",
  "request_id": "uuid",
  "status_code": 400
}
```

### Rate Limit Headers
```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 115
X-RateLimit-Reset: <timestamp>
Retry-After: 5  (only on 429)
```

---

## Upload Limits
- Maximum file size: **20GB**
- Enforced at both Nginx and application layer
- Use `Content-Length` header for pre-flight validation
