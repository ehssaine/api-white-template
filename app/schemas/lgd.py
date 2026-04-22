from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class LgdMethod(str, Enum):
    FULLY_UNSECURED = "fully_unsecured"
    PARTIALLY_UNSECURED = "partially_unsecured"
    TORSION_FACTORS = "torsion_factors"


class ExcelInput(BaseModel):
    """Input record matching the Excel ingestion schema."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    Year: Annotated[int, Field(ge=1900, le=2100, description="Observation year.")]
    Year_proj: Annotated[int, Field(ge=1900, le=2100, description="Projection year.")]
    Shif: Annotated[int, Field(description="Shift offset applied to the scenario.")]
    gov_eur_10y_raw: Annotated[
        float,
        Field(description="10-year EUR government bond yield (raw percentage, e.g. 3.25)."),
    ]
    dji_index_Var_lag_fut: Annotated[
        float,
        Field(description="Lagged future variation of the DJI index (as a decimal)."),
    ]


class ComputationResponse(BaseModel):
    """Response wrapping a full computation batch (DataFrame-as-records)."""

    computation_id: int
    method: LgdMethod
    created_at: datetime
    count: int
    average_lgd: float | None = Field(
        default=None,
        description="Mean of the 'lgd' column when present in the result.",
    )
    results: list[dict[str, Any]] = Field(
        description="The library's DataFrame output, converted to records."
    )


class ComputationSummary(BaseModel):
    """History summary entry (no per-row detail)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    method: LgdMethod
    count: int
    average_lgd: float | None
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
