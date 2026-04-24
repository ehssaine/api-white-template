"""LGD computation service.

The service itself contains no financial logic: all three computations
(fully unsecured LGD, partially unsecured LGD and torsion factors) are
delegated to the ``lgd_forward_looking`` library, which expects and
returns ``pandas.DataFrame``. This module is the JSON <-> DataFrame
boundary.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.schemas.lgd import ExcelInput, LgdMethod
from app.services.lgd_forward_looking import (
    LgdForwardLookingAdapter,
    LgdForwardLookingError,
)


def rows_to_dataframe(rows: list[ExcelInput]) -> pd.DataFrame:
    """Convert the incoming JSON payload into the DataFrame the library expects.

    ``macro_vars`` entries are flattened into one column per variable name.
    Rows that omit a given macro variable get ``NaN`` for that column, which
    matches the convention most pandas-based models use to signal "missing".
    """
    records: list[dict[str, Any]] = []
    for row in rows:
        record: dict[str, Any] = {
            "Year": row.Year,
            "Year_proj": row.Year_proj,
            "Shif": row.Shif,
        }
        for mv in row.macro_vars:
            record[mv.name] = mv.value
        records.append(record)
    return pd.DataFrame(records)


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert the library's DataFrame output into JSON-serialisable records.

    ``NaN`` / ``NaT`` are coerced to ``None`` so the payload is valid JSON.
    """
    if df.empty:
        return []
    records = df.to_dict(orient="records")
    return [
        {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in rec.items()}
        for rec in records
    ]


class LgdService:
    """Orchestrates JSON <-> DataFrame conversion around the library calls."""

    def __init__(self, adapter: LgdForwardLookingAdapter | None = None) -> None:
        self._adapter = adapter or LgdForwardLookingAdapter()

    def compute(
        self, rows: list[ExcelInput], method: LgdMethod
    ) -> list[dict[str, Any]]:
        df_input = rows_to_dataframe(rows)
        df_result = self._dispatch(df_input, method)
        return dataframe_to_records(df_result)

    def _dispatch(self, df: pd.DataFrame, method: LgdMethod) -> pd.DataFrame:
        if method is LgdMethod.FULLY_UNSECURED:
            return self._adapter.compute_fully_unsecured(df)
        if method is LgdMethod.PARTIALLY_UNSECURED:
            return self._adapter.compute_partially_unsecured(df)
        if method is LgdMethod.TORSION_FACTORS:
            return self._adapter.compute_torsion_factors(df)
        raise LgdForwardLookingError(f"Unsupported method: {method}")


def average_lgd(results: list[dict[str, Any]]) -> float | None:
    """Return the mean ``lgd`` across records, or ``None`` if unavailable."""
    values = [r["lgd"] for r in results if isinstance(r.get("lgd"), (int, float))]
    if not values:
        return None
    return sum(values) / len(values)
