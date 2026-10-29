from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

router = APIRouter(tags=["salud"])


@router.get("/health")
def health():
    return {"status": "ok", "version": settings.app_version}


@router.get("/health/db")
def health_db():
    try:
        with engine.connect() as conn:
            version = conn.execute(text("select postgis_version()")).scalar_one()
    except Exception as exc:  # la base no responde o falta PostGIS
        raise HTTPException(status_code=503, detail=f"Base de datos no disponible: {exc}") from exc
    return {"status": "ok", "postgis": version}
