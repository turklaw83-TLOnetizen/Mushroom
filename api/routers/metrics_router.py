"""Metrics API router — web vitals + performance summary."""

import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Request

router = APIRouter(prefix="/metrics", tags=["Metrics"])
logger = logging.getLogger(__name__)

# In-memory web vitals storage (recent 1000 entries)
_web_vitals: list[dict] = []
MAX_VITALS = 1000


@router.post("/web-vitals")
async def receive_web_vitals(body: dict, request: Request):
    """Receive frontend Web Vitals metrics."""
    entry = {
        "timestamp": time.time(),
        "lcp": body.get("lcp"),
        "fid": body.get("fid"),
        "cls": body.get("cls"),
        "ttfb": body.get("ttfb"),
        "inp": body.get("inp"),
        "pathname": body.get("pathname", ""),
        "user_agent": request.headers.get("user-agent", "")[:100],
    }
    _web_vitals.append(entry)
    if len(_web_vitals) > MAX_VITALS:
        _web_vitals.pop(0)
    return {"status": "recorded"}


@router.get("/web-vitals/summary")
def web_vitals_summary():
    """Aggregate Web Vitals summary."""
    if not _web_vitals:
        return {"message": "No data collected yet"}

    metrics = {}
    for key in ("lcp", "fid", "cls", "ttfb", "inp"):
        values = [e[key] for e in _web_vitals if e.get(key) is not None]
        if values:
            values.sort()
            metrics[key] = {
                "count": len(values),
                "p50": values[len(values) // 2],
                "p75": values[int(len(values) * 0.75)],
                "p95": values[int(len(values) * 0.95)],
                "avg": round(sum(values) / len(values), 2),
            }
    return {"vitals": metrics, "sample_count": len(_web_vitals)}
