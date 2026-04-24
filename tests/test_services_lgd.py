from __future__ import annotations

import math

import pandas as pd
import pytest

from app.schemas.lgd import ExcelInput, LgdMethod, MacroVar
from app.services.lgd import (
    LgdService,
    average_lgd,
    dataframe_to_records,
    rows_to_dataframe,
)
from app.services.lgd_forward_looking import (
    LgdForwardLookingAdapter,
    LgdForwardLookingError,
)


@pytest.fixture()
def rows() -> list[ExcelInput]:
    return [
        ExcelInput(
            Year=2023,
            Year_proj=2024,
            Shif=1,
            macro_vars=[
                MacroVar(name="gov_eur_10y_raw", value=3.25),
                MacroVar(name="dji_index_Var_lag_fut", value=0.015),
            ],
        ),
        ExcelInput(
            Year=2023,
            Year_proj=2025,
            Shif=2,
            macro_vars=[
                MacroVar(name="gov_eur_10y_raw", value=4.10),
                MacroVar(name="dji_index_Var_lag_fut", value=-0.03),
            ],
        ),
    ]


def test_rows_to_dataframe_shape(rows) -> None:
    df = rows_to_dataframe(rows)
    assert set(df.columns) == {
        "Year",
        "Year_proj",
        "Shif",
        "gov_eur_10y_raw",
        "dji_index_Var_lag_fut",
    }
    assert len(df) == len(rows)
    assert df["gov_eur_10y_raw"].tolist() == [3.25, 4.10]


def test_rows_to_dataframe_fills_missing_macro_vars_with_nan() -> None:
    import math

    heterogeneous = [
        ExcelInput(
            Year=2023,
            Year_proj=2024,
            Shif=0,
            macro_vars=[MacroVar(name="a", value=1.0)],
        ),
        ExcelInput(
            Year=2023,
            Year_proj=2024,
            Shif=0,
            macro_vars=[MacroVar(name="b", value=2.0)],
        ),
    ]
    df = rows_to_dataframe(heterogeneous)
    assert math.isnan(df.loc[0, "b"])
    assert math.isnan(df.loc[1, "a"])


def test_excel_input_rejects_duplicate_macro_vars() -> None:
    with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError
        ExcelInput(
            Year=2023,
            Year_proj=2024,
            Shif=0,
            macro_vars=[
                MacroVar(name="x", value=1.0),
                MacroVar(name="x", value=2.0),
            ],
        )


def test_excel_input_rejects_empty_macro_vars() -> None:
    with pytest.raises(Exception):  # noqa: B017
        ExcelInput(Year=2023, Year_proj=2024, Shif=0, macro_vars=[])


def test_dataframe_to_records_preserves_values() -> None:
    df = pd.DataFrame([{"a": 1, "b": 2.5}, {"a": 2, "b": 3.5}])
    assert dataframe_to_records(df) == [{"a": 1, "b": 2.5}, {"a": 2, "b": 3.5}]


def test_dataframe_to_records_coerces_nan_to_none() -> None:
    df = pd.DataFrame([{"a": 1, "b": None}, {"a": float("nan"), "b": "x"}])
    recs = dataframe_to_records(df)
    assert recs[0]["b"] is None
    assert recs[1]["a"] is None


def test_service_fully_unsecured_calls_library(service, rows) -> None:
    results = service.compute(rows, LgdMethod.FULLY_UNSECURED)
    assert len(results) == len(rows)
    assert all(r["lgd"] == 0.6 for r in results)
    assert all(math.isclose(r["recovery_rate"], 0.4) for r in results)


def test_service_partially_unsecured_calls_library(service, rows) -> None:
    results = service.compute(rows, LgdMethod.PARTIALLY_UNSECURED)
    assert all(r["lgd"] == 0.3 for r in results)


def test_service_torsion_factors_calls_library(service, rows) -> None:
    results = service.compute(rows, LgdMethod.TORSION_FACTORS)
    assert [r["torsion_factor"] for r in results] == [0.1, 0.2]
    assert "lgd" not in results[0]


def test_service_dispatch_unknown_method(service, rows) -> None:
    with pytest.raises(LgdForwardLookingError):
        service.compute(rows, method="bogus")  # type: ignore[arg-type]


def test_adapter_raises_when_library_returns_non_dataframe(rows) -> None:
    class _Bad:
        def compute_lgd_fully_unsecured(self, df):  # noqa: ARG002
            return {"not": "a df"}

        def compute_lgd_partially_unsecured(self, df):  # noqa: ARG002
            return pd.DataFrame()

        def compute_torsion_factors(self, df):  # noqa: ARG002
            return pd.DataFrame()

    adapter = LgdForwardLookingAdapter(module=_Bad())
    svc = LgdService(adapter=adapter)
    with pytest.raises(LgdForwardLookingError):
        svc.compute(rows, LgdMethod.FULLY_UNSECURED)


def test_adapter_wraps_library_exceptions(rows) -> None:
    class _Boom:
        def compute_lgd_fully_unsecured(self, df):  # noqa: ARG002
            raise RuntimeError("kaboom")

        def compute_lgd_partially_unsecured(self, df):  # noqa: ARG002
            return pd.DataFrame()

        def compute_torsion_factors(self, df):  # noqa: ARG002
            return pd.DataFrame()

    adapter = LgdForwardLookingAdapter(module=_Boom())
    svc = LgdService(adapter=adapter)
    with pytest.raises(LgdForwardLookingError):
        svc.compute(rows, LgdMethod.FULLY_UNSECURED)


def test_adapter_rejects_missing_method(rows) -> None:
    class _Incomplete:
        pass

    adapter = LgdForwardLookingAdapter(module=_Incomplete())
    with pytest.raises(LgdForwardLookingError):
        adapter.compute_fully_unsecured(rows_to_dataframe(rows))


def test_average_lgd_returns_mean_when_present() -> None:
    assert math.isclose(
        average_lgd([{"lgd": 0.2}, {"lgd": 0.4}]), 0.3
    )


def test_average_lgd_returns_none_without_lgd_column() -> None:
    assert average_lgd([{"torsion_factor": 0.1}]) is None


def test_average_lgd_returns_none_for_empty_input() -> None:
    assert average_lgd([]) is None
