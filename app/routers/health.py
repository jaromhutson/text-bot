from fastapi import APIRouter

from app.config import settings
from app.database import get_db

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready():
    """Readiness check — verifies DB connection and critical config."""
    checks = {}

    # DB check
    try:
        db = await get_db()
        row = await db.execute_fetchall("SELECT 1 as ok")
        checks["database"] = "ok" if row else "fail"
    except Exception as e:
        checks["database"] = f"fail: {e}"

    # Config check
    checks["anthropic_api_key"] = "set" if settings.anthropic_api_key else "missing"
    checks["admin_api_key"] = "set" if settings.admin_api_key else "missing"

    all_ok = checks["database"] == "ok" and checks["anthropic_api_key"] == "set"
    status_code = 200 if all_ok else 503

    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
        status_code=status_code,
    )
