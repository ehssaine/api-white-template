from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class LgdMethod(str, Enum):
    FULLY_UNSECURED = "fully_unsecured"
    PARTIALLY_UNSECURED = "partially_unsecured"


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


class LgdItemResult(BaseModel):
    """LGD computation result for a single input record."""

    model_config = ConfigDict(from_attributes=True)

    Year: int
    Year_proj: int
    Shif: int
    gov_eur_10y_raw: float
    dji_index_Var_lag_fut: float
    lgd: float = Field(ge=0.0, le=1.0, description="Loss Given Default in [0, 1].")
    recovery_rate: float = Field(ge=0.0, le=1.0)


class LgdComputationResponse(BaseModel):
    """Response wrapping a full LGD computation batch."""

    computation_id: int
    method: LgdMethod
    created_at: datetime
    count: int
    average_lgd: float
    results: list[LgdItemResult]


class LgdComputationSummary(BaseModel):
    """History summary entry (no per-row detail)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    method: LgdMethod
    count: int
    average_lgd: float
    created_at: datetime


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
