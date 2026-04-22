from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import db_session, get_calculator
from app.core.config import Settings, get_settings
from app.crud import lgd as lgd_crud
from app.schemas.lgd import (
    ExcelInput,
    LgdComputationResponse,
    LgdComputationSummary,
    LgdMethod,
)
from app.services.lgd import LgdCalculator

router = APIRouter()


def _validate_batch(rows: list[ExcelInput], settings: Settings) -> None:
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Input list must contain at least one record.",
        )
    if len(rows) > settings.max_batch_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Batch size {len(rows)} exceeds the configured maximum of "
                f"{settings.max_batch_size}."
            ),
        )


def _run_and_persist(
    rows: list[ExcelInput],
    method: LgdMethod,
    calculator: LgdCalculator,
    db: Session,
) -> LgdComputationResponse:
    results = calculator.compute_batch(rows, method)
    computation = lgd_crud.create_computation(db, method=method, results=results)
    return LgdComputationResponse(
        computation_id=computation.id,
        method=method,
        created_at=computation.created_at,
        count=computation.count,
        average_lgd=computation.average_lgd,
        results=results,
    )


@router.post(
    "/fully-unsecured",
    response_model=LgdComputationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Compute LGD assuming a fully unsecured exposure.",
)
def compute_fully_unsecured(
    payload: list[ExcelInput],
    db: Annotated[Session, Depends(db_session)],
    calculator: Annotated[LgdCalculator, Depends(get_calculator)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LgdComputationResponse:
    _validate_batch(payload, settings)
    return _run_and_persist(payload, LgdMethod.FULLY_UNSECURED, calculator, db)


@router.post(
    "/partially-unsecured",
    response_model=LgdComputationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Compute LGD assuming a partially secured (collateralised) exposure.",
)
def compute_partially_unsecured(
    payload: list[ExcelInput],
    db: Annotated[Session, Depends(db_session)],
    calculator: Annotated[LgdCalculator, Depends(get_calculator)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LgdComputationResponse:
    _validate_batch(payload, settings)
    return _run_and_persist(payload, LgdMethod.PARTIALLY_UNSECURED, calculator, db)


@router.get(
    "/history",
    response_model=list[LgdComputationSummary],
    summary="List past LGD computations with pagination.",
)
def list_history(
    db: Annotated[Session, Depends(db_session)],
    method: LgdMethod | None = Query(default=None, description="Filter by method."),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[LgdComputationSummary]:
    computations = lgd_crud.list_computations(
        db, method=method, limit=limit, offset=offset
    )
    return [LgdComputationSummary.model_validate(c) for c in computations]


@router.get(
    "/history/{computation_id}",
    response_model=LgdComputationResponse,
    summary="Fetch a single computation (with per-row results).",
)
def get_history_item(
    computation_id: int,
    db: Annotated[Session, Depends(db_session)],
) -> LgdComputationResponse:
    computation = lgd_crud.get_computation(db, computation_id)
    if computation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Computation {computation_id} not found.",
        )
    results = [
        {
            "Year": item.year,
            "Year_proj": item.year_proj,
            "Shif": item.shif,
            "gov_eur_10y_raw": item.gov_eur_10y_raw,
            "dji_index_Var_lag_fut": item.dji_index_var_lag_fut,
            "lgd": item.lgd,
            "recovery_rate": item.recovery_rate,
        }
        for item in computation.items
    ]
    return LgdComputationResponse(
        computation_id=computation.id,
        method=LgdMethod(computation.method),
        created_at=computation.created_at,
        count=computation.count,
        average_lgd=computation.average_lgd,
        results=results,  # type: ignore[arg-type]
    )
