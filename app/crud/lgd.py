from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lgd import LgdComputation, LgdComputationItem
from app.schemas.lgd import LgdItemResult, LgdMethod
from app.services.lgd import average_lgd


def create_computation(
    db: Session,
    *,
    method: LgdMethod,
    results: list[LgdItemResult],
) -> LgdComputation:
    computation = LgdComputation(
        method=method.value,
        count=len(results),
        average_lgd=average_lgd(results),
        items=[
            LgdComputationItem(
                year=r.Year,
                year_proj=r.Year_proj,
                shif=r.Shif,
                gov_eur_10y_raw=r.gov_eur_10y_raw,
                dji_index_var_lag_fut=r.dji_index_Var_lag_fut,
                lgd=r.lgd,
                recovery_rate=r.recovery_rate,
            )
            for r in results
        ],
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
