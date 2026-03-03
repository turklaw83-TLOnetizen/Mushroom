"""Tenant management API router."""

import uuid
from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user, require_role
from core.tenant_billing import TenantBilling
from core.tenant_theming import get_theme, apply_theme, TenantTheme

router = APIRouter(prefix="/tenants", tags=["Tenants"])
billing = TenantBilling()


@router.post("")
def create_tenant(body: dict, user=Depends(require_role("admin"))):
    name = body.get("name", "")
    slug = body.get("slug", "")
    plan = body.get("plan", "starter")
    if not name or not slug:
        raise HTTPException(400, "name and slug required")
    tenant = {
        "id": uuid.uuid4().hex[:12],
        "name": name, "slug": slug, "plan": plan,
        "max_users": body.get("max_users", 5),
        "max_cases": body.get("max_cases", 50),
    }
    return tenant


@router.get("/{tenant_id}")
def get_tenant(tenant_id: str, user=Depends(get_current_user)):
    return {"id": tenant_id, "status": "active"}


@router.get("/{tenant_id}/usage")
def get_usage(tenant_id: str, user=Depends(get_current_user)):
    return billing.get_billing_summary(tenant_id)


@router.put("/{tenant_id}/branding")
def update_branding(tenant_id: str, body: dict, user=Depends(require_role("admin"))):
    theme = TenantTheme(**{k: v for k, v in body.items() if hasattr(TenantTheme, k)})
    apply_theme(tenant_id, theme)
    return {"status": "updated"}


@router.get("/{tenant_id}/branding")
def get_branding(tenant_id: str, user=Depends(get_current_user)):
    from dataclasses import asdict
    return asdict(get_theme(tenant_id))
