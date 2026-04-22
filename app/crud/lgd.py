from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lgd import LgdComputation
from app.schemas.lgd import ExcelInput, LgdMethod
from app.services.lgd import average_lgd


def create_computation(
    db: Session,
    *,
    method: LgdMethod,
    inputs: list[ExcelInput],
    results: list[dict[str, Any]],
) -> LgdComputation:
    computation = LgdComputation(
        method=method.value,
        count=len(results),
        average_lgd=average_lgd(results),
        input_json=[r.model_dump() for r in inputs],
        result_json=results,
    )
    db.add(computation)
    db.commit()
    db.refresh(computation)
    return computation


def get_computation(db: Session, computation_id: int) -> LgdComputation | None:
    return db.get(LgdComputation, computation_id)


def list_computations(
    db: Session,
    *,
    method: LgdMethod | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[LgdComputation]:
    stmt = select(LgdComputation).order_by(LgdComputation.created_at.desc())
    if method is not None:
        stmt = stmt.where(LgdComputation.method == method.value)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())
