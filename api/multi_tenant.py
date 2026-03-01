# ---- Multi-Tenant Isolation -----------------------------------------------
# Tenant-aware data access layer for SaaS deployment.

import logging
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# Current tenant context (set per-request by middleware)
_current_tenant: ContextVar[str | None] = ContextVar("current_tenant", default=None)


def get_current_tenant() -> str | None:
    """Get the current tenant ID from request context."""
    return _current_tenant.get()


def set_current_tenant(tenant_id: str):
    """Set the current tenant ID (called by middleware)."""
    _current_tenant.set(tenant_id)


class TenantMiddleware:
    """
    Middleware that extracts tenant ID from the request and sets it in context.

    Tenant ID can come from:
    1. Clerk organization ID (primary)
    2. X-Tenant-ID header (API keys)
    3. Subdomain (multi-domain deployment)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            tenant_id = None

            # Try X-Tenant-ID header
            tenant_header = headers.get(b"x-tenant-id", b"").decode()
            if tenant_header:
                tenant_id = tenant_header

            # Try subdomain
            host = headers.get(b"host", b"").decode()
            if not tenant_id and "." in host:
                subdomain = host.split(".")[0]
                if subdomain not in ("www", "api", "localhost"):
                    tenant_id = subdomain

            # Default: single-tenant mode (turklaylaw)
            if not tenant_id:
                tenant_id = "turklaylaw"

            set_current_tenant(tenant_id)

        await self.app(scope, receive, send)


def tenant_filter(query, tenant_column="tenant_id"):
    """
    SQLAlchemy query filter for tenant isolation.

    Usage:
        query = session.query(Case)
        query = tenant_filter(query)
    """
    tenant_id = get_current_tenant()
    if tenant_id:
        return query.filter_by(**{tenant_column: tenant_id})
    return query
