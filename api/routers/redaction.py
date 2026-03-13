# ---- AI Document Redaction Router ------------------------------------------
# Endpoints for scanning case documents for PII, applying redactions,
# and managing redaction reports for discovery compliance.

import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import require_role, get_current_user
from api.deps import get_case_manager, get_data_dir

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/cases/{case_id}/redaction",
    tags=["Redaction"],
)


# ---- Request Models -------------------------------------------------------

class ScanRequest(BaseModel):
    """Request to scan document(s) for PII."""
    categories: Optional[List[str]] = None  # None = use defaults
    use_llm: bool = True
    filename: Optional[str] = None  # Scan specific file, or all if None


class ApplyRedactionRequest(BaseModel):
    """Request to apply redactions to a document."""
    filename: str = Field(..., min_length=1, max_length=500)
    categories: Optional[List[str]] = None
    redaction_style: str = "category"  # blackout | category | placeholder
    use_llm: bool = True


# ---- Helpers --------------------------------------------------------------

def _load_state_or_404(case_id: str, prep_id: str) -> dict:
    """Load preparation state or raise 404."""
    cm = get_case_manager()
    state = cm.load_prep_state(case_id, prep_id)
    if state is None:
        meta = cm.get_case_metadata(case_id)
        if not meta:
            raise HTTPException(status_code=404, detail="Case not found")
        raise HTTPException(status_code=404, detail="Preparation not found")
    return state


def _validate_case_exists(case_id: str) -> None:
    """Ensure the case exists or raise 404."""
    cm = get_case_manager()
    meta = cm.get_case_metadata(case_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Case not found")


# ---- POST /scan  — Scan file(s) for PII ----------------------------------

@router.post("/scan")
async def scan_for_pii(
    case_id: str,
    body: ScanRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Scan case documents for PII, privileged, and sensitive content.

    If ``filename`` is provided, scans that specific file's OCR text.
    If omitted, scans all files in the case using the OCR cache.
    Returns findings grouped by file with category summaries.
    """
    _validate_case_exists(case_id)

    from core.redaction import (
        REDACTION_CATEGORIES,
        scan_document_for_pii,
        batch_scan_case_files,
        generate_redaction_log,
        save_redaction_report,
    )
    from core.ingest import OCRCache

    data_dir = get_data_dir()

    # Validate categories
    if body.categories:
        invalid = [c for c in body.categories if c not in REDACTION_CATEGORIES]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid categories: {', '.join(invalid)}. "
                       f"Valid: {', '.join(REDACTION_CATEGORIES.keys())}",
            )

    try:
        if body.filename:
            # Scan a specific file using OCR cache
            case_dir = f"{data_dir}/cases/{case_id}"
            ocr_cache = OCRCache(case_dir)
            manifest = ocr_cache._load_manifest()

            # Find the file in manifest
            file_text = None
            for file_key, meta in manifest.items():
                fname = meta.get("filename", file_key)
                if fname == body.filename or file_key == body.filename:
                    if meta.get("status") == "done":
                        file_text = ocr_cache.get_text(file_key)
                    break

            if not file_text:
                raise HTTPException(
                    status_code=404,
                    detail=f"File '{body.filename}' not found in OCR cache or not yet processed",
                )

            result = await asyncio.to_thread(
                scan_document_for_pii,
                text=file_text,
                categories=body.categories,
                use_llm=body.use_llm,
            )

            # Generate and save redaction log
            redaction_log = generate_redaction_log(
                result["findings"], body.filename
            )

            if result["findings"]:
                report = {
                    "scan_type": "single_file",
                    "filename": body.filename,
                    **redaction_log,
                    "findings": result["findings"],
                }
                save_redaction_report(data_dir, case_id, report)

            return {
                "status": "success",
                "filename": body.filename,
                "findings_count": len(result["findings"]),
                "summary": result["summary"],
                "findings": result["findings"],
                "redaction_log": redaction_log,
            }

        else:
            # Batch scan all files
            # We need a state dict for LLM config — build a minimal one
            cm = get_case_manager()
            # Try to find the latest prep for state; fall back to minimal state
            preps = cm.list_preparations(case_id)
            state: dict = {}
            if preps:
                latest_prep = sorted(preps, key=lambda p: p.get("created_at", ""), reverse=True)[0]
                loaded = cm.load_prep_state(case_id, latest_prep.get("id", ""))
                if loaded:
                    state = loaded

            result = await asyncio.to_thread(
                batch_scan_case_files,
                case_id=case_id,
                prep_id="",
                categories=body.categories or [],
                state=state,
                data_dir=data_dir,
            )

            # Save aggregate report
            if result["total_findings"] > 0:
                report = {
                    "scan_type": "batch",
                    "total_findings": result["total_findings"],
                    "summary": result["summary"],
                    "files_scanned": len(result["files"]),
                    "per_file_summary": {
                        fname: {
                            "findings_count": len(fdata.get("findings", [])),
                            "summary": fdata.get("summary", {}),
                        }
                        for fname, fdata in result["files"].items()
                    },
                }
                save_redaction_report(data_dir, case_id, report)

            return {
                "status": "success",
                "files_scanned": len(result["files"]),
                "total_findings": result["total_findings"],
                "summary": result["summary"],
                "files": {
                    fname: {
                        "findings_count": len(fdata.get("findings", [])),
                        "summary": fdata.get("summary", {}),
                        "findings": fdata.get("findings", []),
                    }
                    for fname, fdata in result["files"].items()
                },
            }

    except HTTPException:
        raise
    except Exception:
        logger.exception("PII scan failed for case %s", case_id)
        raise HTTPException(status_code=500, detail="PII scan failed")


# ---- GET /reports  — List redaction reports --------------------------------

@router.get("/reports")
def list_reports(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """List saved redaction reports for a case (metadata only)."""
    _validate_case_exists(case_id)

    try:
        from core.redaction import load_redaction_reports

        data_dir = get_data_dir()
        reports = load_redaction_reports(data_dir, case_id)
        return {"reports": reports}
    except Exception:
        logger.exception("Failed to list redaction reports")
        return {"reports": []}


# ---- GET /reports/{report_id}  — Get full report --------------------------

@router.get("/reports/{report_id}")
def get_report(
    case_id: str,
    report_id: str,
    user: dict = Depends(get_current_user),
):
    """Get a full redaction report by ID."""
    _validate_case_exists(case_id)

    from core.redaction import load_redaction_report

    data_dir = get_data_dir()
    report = load_redaction_report(data_dir, case_id, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Redaction report not found")
    return report


# ---- POST /apply  — Apply redactions to a file ----------------------------

@router.post("/apply")
async def apply_redactions_to_file(
    case_id: str,
    body: ApplyRedactionRequest,
    user: dict = Depends(require_role("admin", "attorney")),
):
    """Scan and apply redactions to a specific file's text.

    Returns the redacted text and a redaction log.
    This does NOT modify the original file — it returns the redacted
    version for the attorney to review and export.
    """
    _validate_case_exists(case_id)

    from core.redaction import (
        REDACTION_CATEGORIES,
        scan_document_for_pii,
        apply_redactions,
        generate_redaction_log,
        save_redaction_report,
    )
    from core.ingest import OCRCache

    data_dir = get_data_dir()

    # Validate redaction style
    valid_styles = ("blackout", "category", "placeholder")
    if body.redaction_style not in valid_styles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid redaction_style '{body.redaction_style}'. "
                   f"Must be one of: {', '.join(valid_styles)}",
        )

    try:
        # Get file text from OCR cache
        case_dir = f"{data_dir}/cases/{case_id}"
        ocr_cache = OCRCache(case_dir)
        manifest = ocr_cache._load_manifest()

        file_text = None
        for file_key, meta in manifest.items():
            fname = meta.get("filename", file_key)
            if fname == body.filename or file_key == body.filename:
                if meta.get("status") == "done":
                    file_text = ocr_cache.get_text(file_key)
                break

        if not file_text:
            raise HTTPException(
                status_code=404,
                detail=f"File '{body.filename}' not found in OCR cache or not yet processed",
            )

        # Scan
        scan_result = await asyncio.to_thread(
            scan_document_for_pii,
            text=file_text,
            categories=body.categories,
            use_llm=body.use_llm,
        )

        findings = scan_result["findings"]

        # Apply redactions
        redacted_text = apply_redactions(
            text=file_text,
            findings=findings,
            redaction_style=body.redaction_style,
        )

        # Generate log
        redaction_log = generate_redaction_log(findings, body.filename)

        # Save report
        report = {
            "scan_type": "apply",
            "filename": body.filename,
            "redaction_style": body.redaction_style,
            **redaction_log,
        }
        save_redaction_report(data_dir, case_id, report)

        return {
            "status": "success",
            "filename": body.filename,
            "original_length": len(file_text),
            "redacted_length": len(redacted_text),
            "findings_count": len(findings),
            "summary": scan_result["summary"],
            "redacted_text": redacted_text,
            "redaction_log": redaction_log,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Redaction apply failed for case %s file %s", case_id, body.filename)
        raise HTTPException(status_code=500, detail="Redaction apply failed")


# ---- GET /categories  — List available categories -------------------------

@router.get("/categories")
def list_categories(
    case_id: str,
    user: dict = Depends(get_current_user),
):
    """List all available PII/redaction categories with their defaults."""
    from core.redaction import REDACTION_CATEGORIES

    return {
        "categories": [
            {
                "key": key,
                "label": info["label"],
                "has_pattern": info["pattern"] is not None,
                "requires_llm": info["pattern"] is None,
                "default": info["default"],
            }
            for key, info in REDACTION_CATEGORIES.items()
        ]
    }
