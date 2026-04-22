from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import db_session
from app.schemas.lgd import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Liveness and DB probe.")
def health(db: Session = Depends(db_session)) -> HealthResponse:
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_status = "unavailable"
    return HealthResponse(status="ok", version=__version__, database=db_status)
