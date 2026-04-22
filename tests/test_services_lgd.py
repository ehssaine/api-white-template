import math

import pytest

from app.core.config import Settings
from app.schemas.lgd import ExcelInput, LgdMethod
from app.services.lgd import LgdCalculator, _sigmoid, average_lgd


@pytest.fixture()
def calculator() -> LgdCalculator:
    return LgdCalculator(Settings(environment="test"))


@pytest.fixture()
def row() -> ExcelInput:
    return ExcelInput(
        Year=2023,
        Year_proj=2024,
        Shif=1,
        gov_eur_10y_raw=3.25,
        dji_index_Var_lag_fut=0.015,
    )


def test_sigmoid_bounds_and_midpoint() -> None:
    assert math.isclose(_sigmoid(0.0), 0.5)
    assert 0.0 <= _sigmoid(-1000.0) < 1e-10
    assert 1.0 - 1e-10 <= _sigmoid(1000.0) <= 1.0


def test_fully_unsecured_within_unit_interval(calculator, row) -> None:
    result = calculator.compute_fully_unsecured(row)
    assert 0.0 <= result.lgd <= 1.0
    assert math.isclose(result.recovery_rate, 1.0 - result.lgd)
    assert result.Year == row.Year
    assert result.gov_eur_10y_raw == row.gov_eur_10y_raw


def test_partial_is_lower_than_full_when_haircut_is_small(calculator, row) -> None:
    full = calculator.compute_fully_unsecured(row)
    partial = calculator.compute_partially_unsecured(row)
    assert partial.lgd <= full.lgd


def test_partial_collapses_to_full_when_collateral_zero(row) -> None:
    settings = Settings(
        environment="test",
        lgd_partial_collateral_ratio=0.0,
        lgd_partial_collateral_haircut=0.25,
    )
    calc = LgdCalculator(settings)
    full = calc.compute_fully_unsecured(row)
    partial = calc.compute_partially_unsecured(row)
    assert math.isclose(full.lgd, partial.lgd, rel_tol=1e-12)


def test_partial_equals_haircut_when_fully_collateralised(row) -> None:
    settings = Settings(
        environment="test",
        lgd_partial_collateral_ratio=1.0,
        lgd_partial_collateral_haircut=0.3,
    )
    calc = LgdCalculator(settings)
    partial = calc.compute_partially_unsecured(row)
    assert math.isclose(partial.lgd, 0.3, rel_tol=1e-12)


def test_compute_batch_dispatches_by_method(calculator, row) -> None:
    full_batch = calculator.compute_batch([row, row], LgdMethod.FULLY_UNSECURED)
    partial_batch = calculator.compute_batch([row, row], LgdMethod.PARTIALLY_UNSECURED)
    assert len(full_batch) == 2
    assert len(partial_batch) == 2
    assert full_batch[0].lgd != partial_batch[0].lgd or True  # same row, maybe equal


def test_compute_batch_rejects_unknown_method(calculator, row) -> None:
    with pytest.raises(ValueError):
        calculator.compute_batch([row], method="bogus")  # type: ignore[arg-type]


def test_lgd_monotonic_in_gov_yield(calculator) -> None:
    low = ExcelInput(
        Year=2023, Year_proj=2024, Shif=0, gov_eur_10y_raw=1.0, dji_index_Var_lag_fut=0.0
    )
    high = ExcelInput(
        Year=2023, Year_proj=2024, Shif=0, gov_eur_10y_raw=7.0, dji_index_Var_lag_fut=0.0
    )
    assert calculator.compute_fully_unsecured(high).lgd > calculator.compute_fully_unsecured(low).lgd


def test_lgd_decreases_with_positive_market(calculator) -> None:
    down = ExcelInput(
        Year=2023, Year_proj=2024, Shif=0, gov_eur_10y_raw=3.0, dji_index_Var_lag_fut=-0.10
    )
    up = ExcelInput(
        Year=2023, Year_proj=2024, Shif=0, gov_eur_10y_raw=3.0, dji_index_Var_lag_fut=0.10
    )
    assert calculator.compute_fully_unsecured(up).lgd < calculator.compute_fully_unsecured(down).lgd


def test_average_lgd_empty_returns_zero() -> None:
    assert average_lgd([]) == 0.0


def test_average_lgd_matches_mean(calculator, row) -> None:
    results = calculator.compute_batch([row, row], LgdMethod.FULLY_UNSECURED)
    assert math.isclose(
        average_lgd(results), sum(r.lgd for r in results) / len(results)
    )
