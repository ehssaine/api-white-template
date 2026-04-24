from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LgdMethod(str, Enum):
    FULLY_UNSECURED = "fully_unsecured"
    PARTIALLY_UNSECURED = "partially_unsecured"
    TORSION_FACTORS = "torsion_factors"


class MacroVar(BaseModel):
    """A single macro-economic variable fed into the LGD library."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=128,
            description="Column name exposed to the lgd_forward_looking library.",
        ),
    ]
    value: Annotated[float, Field(description="Numeric value of the variable.")]


class ExcelInput(BaseModel):
    """Input record matching the Excel ingestion schema."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    Year: Annotated[int, Field(ge=1900, le=2100, description="Observation year.")]
    Year_proj: Annotated[int, Field(ge=1900, le=2100, description="Projection year.")]
    Shif: Annotated[int, Field(description="Shift offset applied to the scenario.")]
    macro_vars: Annotated[
        list[MacroVar],
        Field(
            min_length=1,
            description="Macro-economic variables (e.g. gov_eur_10y_raw, dji_index_Var_lag_fut).",
        ),
    ]

    @model_validator(mode="after")
    def _reject_duplicate_macro_names(self) -> "ExcelInput":
        seen: set[str] = set()
        duplicates: set[str] = set()
        for m in self.macro_vars:
            if m.name in seen:
                duplicates.add(m.name)
            seen.add(m.name)
        if duplicates:
            raise ValueError(
                f"macro_vars names must be unique per record; duplicates: {sorted(duplicates)}"
            )
        return self


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
