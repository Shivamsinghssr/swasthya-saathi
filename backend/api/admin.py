"""
api/admin.py

Admin dashboard API routes.

All routes require Bearer token authentication.
Token = ADMIN_PASSWORD env var (set in .env and Railway Variables).

Routes:
    GET  /admin/stats        — dashboard summary stats
    GET  /admin/logs         — recent query logs
    GET  /admin/tools        — tool usage breakdown
    POST /admin/eval/run     — trigger evaluation harness
    GET  /admin/eval/latest  — get latest eval results
    GET  /admin/health       — system health (Redis, memory, indexes)
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from memory.query_logger import get_query_logger

router   = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBearer()


# ── Auth ──────────────────────────────────────────────────────────────────────

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify Bearer token against ADMIN_PASSWORD env var."""
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if not admin_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_PASSWORD not configured on server."
        )
    if credentials.credentials != admin_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(_: bool = Depends(verify_token)):
    """
    Dashboard summary:
    - total queries, avg latency, top tool, success rate
    - tool usage counts
    - last 50 query logs
    """
    logger = get_query_logger()
    return logger.get_stats()


@router.get("/logs")
async def get_logs(
    limit: int = 50,
    _: bool = Depends(verify_token)
):
    """Get recent query logs (most recent first)."""
    logger = get_query_logger()
    logs = logger.get_recent_logs(min(limit, 200))
    return {"logs": logs, "count": len(logs)}


@router.get("/tools")
async def get_tool_stats(_: bool = Depends(verify_token)):
    """Get tool usage breakdown."""
    logger = get_query_logger()
    counts = logger.get_tool_counts()
    total  = sum(counts.values())
    breakdown = [
        {
            "tool": tool,
            "count": count,
            "percentage": round(count / total * 100, 1) if total > 0 else 0,
        }
        for tool, count in sorted(counts.items(), key=lambda x: -x[1])
    ]
    return {"total_tool_calls": total, "breakdown": breakdown}


@router.get("/eval/latest")
async def get_latest_eval(_: bool = Depends(verify_token)):
    """
    Get the most recent evaluation harness results.
    Reads from eval/results/ directory.
    """
    results_dir = Path("eval/results")
    if not results_dir.exists():
        return {"error": "No eval results found. Run eval first.", "results": None}

    result_files = sorted(results_dir.glob("eval_*.json"), reverse=True)
    if not result_files:
        return {"error": "No eval results found. Run eval first.", "results": None}

    latest = result_files[0]
    try:
        with open(latest, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "file": latest.name,
            "results": data,
        }
    except Exception as e:
        return {"error": str(e), "results": None}


@router.post("/eval/run")
async def run_eval(_: bool = Depends(verify_token)):
    """
    Trigger evaluation harness asynchronously.
    Returns immediately — check /eval/latest after ~2 minutes.
    NOTE: Uses Groq API — will consume rate limits.
    """
    try:
        # Run eval in background — non-blocking
        subprocess.Popen(
            [sys.executable, "eval/evaluate.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {
            "status": "started",
            "message": "Evaluation running in background. Check /admin/eval/latest in ~2 minutes."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system")
async def system_health(_: bool = Depends(verify_token)):
    """System health check for admin."""
    from memory.session_store import get_session_store
    from memory.query_logger import get_query_logger

    store  = get_session_store()
    logger = get_query_logger()

    # Check indexes
    indexes_ok = (
        Path("indexes/symptoms.faiss").exists() and
        Path("indexes/medicines.faiss").exists() and
        Path("indexes/schemes.faiss").exists()
    )

    return {
        "session_store_backend": store.backend,
        "query_logger_backend":  logger.backend,
        "indexes_built":         indexes_ok,
        "total_queries_logged":  logger.get_total_queries(),
        "admin_password_set":    bool(os.getenv("ADMIN_PASSWORD", "")),
        "groq_key_set":          bool(os.getenv("GROQ_API_KEY", "")),
        "sarvam_key_set":        bool(os.getenv("SARVAM_API_KEY", "")),
        "redis_url_set":         bool(os.getenv("REDIS_URL", "")),
    }
