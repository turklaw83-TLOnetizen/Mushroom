"""DLP (Data Loss Prevention) API router."""

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user, require_role
from core.dlp_rules import DLPEngine

router = APIRouter(prefix="/dlp", tags=["DLP"])
engine = DLPEngine()


@router.get("/rules")
def list_rules(user=Depends(get_current_user)):
    return {"rules": engine.get_rules()}


@router.post("/rules")
def create_rule(body: dict, user=Depends(require_role("admin"))):
    return engine.create_rule(body)


@router.put("/rules/{rule_id}")
def update_rule(rule_id: str, body: dict, user=Depends(require_role("admin"))):
    result = engine.update_rule(rule_id, body)
    if result is None:
        raise HTTPException(404, "Rule not found")
    return result


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, user=Depends(require_role("admin"))):
    if not engine.delete_rule(rule_id):
        raise HTTPException(404, "Rule not found")
    return {"status": "deleted"}


@router.get("/audit-log")
def get_audit_log(limit: int = 100, user_id: str = "", user=Depends(require_role("admin"))):
    return {"entries": engine.get_audit_log(limit=limit, user_id=user_id or None)}


@router.post("/check")
def check_action(body: dict, user=Depends(get_current_user)):
    action = body.get("action", "download")
    if action == "download":
        return engine.check_download(user["id"], user.get("role", "attorney"), body.get("filename", ""))
    elif action == "export":
        return engine.check_export(user["id"], user.get("role", "attorney"), body.get("case_id", ""), body.get("export_type", ""))
    return {"allowed": True}
