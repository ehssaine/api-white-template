from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import db_session, get_lgd_service
from app.core.config import Settings, get_settings
from app.crud import lgd as lgd_crud
from app.schemas.lgd import (
    ComputationResponse,
    ComputationSummary,
    ExcelInput,
    LgdMethod,
)
from app.services.excel_parser import ExcelParsingError, parse_excel_bytes
from app.services.lgd import LgdService, average_lgd
from app.services.lgd_forward_looking import LgdForwardLookingError

router = APIRouter()

_XLSX_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/octet-stream",  # some clients (e.g. curl) default to this
}


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


async def _rows_from_upload(file: UploadFile) -> list[ExcelInput]:
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only .xlsx files are accepted.",
        )
    if file.content_type and file.content_type not in _XLSX_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type: {file.content_type}.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )

    try:
        return parse_excel_bytes(data)
    except ExcelParsingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


def _run_and_persist(
    rows: list[ExcelInput],
    method: LgdMethod,
    service: LgdService,
    db: Session,
) -> ComputationResponse:
    try:
        results = service.compute(rows, method)
    except LgdForwardLookingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    computation = lgd_crud.create_computation(
        db, method=method, inputs=rows, results=results
    )
    return ComputationResponse(
        computation_id=computation.id,
        method=method,
        created_at=computation.created_at,
        count=computation.count,
        average_lgd=computation.average_lgd,
        results=results,
    )


@router.post(
    "/fully-unsecured",
    response_model=ComputationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Compute LGD from an XLSX scenario file (fully unsecured exposure).",
)
async def compute_fully_unsecured(
    db: Annotated[Session, Depends(db_session)],
    service: Annotated[LgdService, Depends(get_lgd_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File(description="XLSX file with MS01, MS02 ... sheets.")],
) -> ComputationResponse:
    rows = await _rows_from_upload(file)
    _validate_batch(rows, settings)
    return _run_and_persist(rows, LgdMethod.FULLY_UNSECURED, service, db)


@router.post(
    "/partially-unsecured",
    response_model=ComputationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Compute LGD from an XLSX scenario file (partially secured exposure).",
)
async def compute_partially_unsecured(
    db: Annotated[Session, Depends(db_session)],
    service: Annotated[LgdService, Depends(get_lgd_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File(description="XLSX file with MS01, MS02 ... sheets.")],
) -> ComputationResponse:
    rows = await _rows_from_upload(file)
    _validate_batch(rows, settings)
    return _run_and_persist(rows, LgdMethod.PARTIALLY_UNSECURED, service, db)


@router.post(
    "/torsion-factors",
    response_model=ComputationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Compute torsion factors from a JSON payload.",
)
def compute_torsion_factors(
    payload: list[ExcelInput],
    db: Annotated[Session, Depends(db_session)],
    service: Annotated[LgdService, Depends(get_lgd_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ComputationResponse:
    _validate_batch(payload, settings)
    return _run_and_persist(payload, LgdMethod.TORSION_FACTORS, service, db)


@router.get(
    "/history",
    response_model=list[ComputationSummary],
    summary="List past computations with pagination.",
)
def list_history(
    db: Annotated[Session, Depends(db_session)],
    method: LgdMethod | None = Query(default=None, description="Filter by method."),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ComputationSummary]:
    computations = lgd_crud.list_computations(
        db, method=method, limit=limit, offset=offset
    )
    return [ComputationSummary.model_validate(c) for c in computations]


@router.get(
    "/history/{computation_id}",
    response_model=ComputationResponse,
    summary="Fetch a single computation (with the DataFrame-as-JSON results).",
)
def get_history_item(
    computation_id: int,
    db: Annotated[Session, Depends(db_session)],
) -> ComputationResponse:
    computation = lgd_crud.get_computation(db, computation_id)
    if computation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Computation {computation_id} not found.",
        )
    results = list(computation.result_json or [])
    return ComputationResponse(
        computation_id=computation.id,
        method=LgdMethod(computation.method),
        created_at=computation.created_at,
        count=computation.count,
        average_lgd=computation.average_lgd
        if computation.average_lgd is not None
        else average_lgd(results),
        results=results,
    )
